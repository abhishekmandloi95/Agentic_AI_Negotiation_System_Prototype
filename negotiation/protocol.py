"""Explicit proposal/approval protocol; no execution inferred from prose."""
import json
import random
from datetime import datetime, timezone
from uuid import uuid4
from agents.base_agent import LLMNegotiationAgent
from negotiation.trades import Proposal, Transfer, execute_proposal, validate_proposal
from negotiation.loop_trader import find_trade_loops, loop_proposal, detect_and_execute_loops
from metrics.evaluation import summarize_run
from utils.paths import project_path

CONFIRM_KEYWORD = "deal accepted"
SHOW_MARKET_SYSTEM_LINES = False

class Conversation(list):
    def __init__(self):
        super().__init__()
        self.events = []
        self.metrics = {}
        self.run_id = uuid4().hex

def clean_text(reply, agent_id=None):
    text = str(getattr(reply, "content", reply)).strip()
    if agent_id is not None:
        text = text.removeprefix(f"{agent_id}:").lstrip()
    return text

def parse_decision(raw, proposal_id, agent_id=None):
    if not isinstance(raw, dict):
        try:
            raw = json.loads(clean_text(raw, agent_id))
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("Decision must be a JSON object.") from exc
    required = {"proposal_id", "action", "reason"}
    if not isinstance(raw, dict) or not required.issubset(raw) or set(raw) - required - {"transfers"}:
        raise ValueError("Decision requires proposal_id, action, reason and optional counter transfers.")
    if raw["proposal_id"] != proposal_id or raw["action"] not in ("accept", "reject", "counter"):
        raise ValueError("Wrong proposal ID or action.")
    if not isinstance(raw["reason"], str):
        raise ValueError("Decision reason must be text.")
    transfers = raw.get("transfers", [])
    if raw["action"] == "counter":
        if not isinstance(transfers, list) or len(transfers) != 2:
            raise ValueError("A bilateral counteroffer requires both transfer legs.")
        for transfer in transfers:
            if not isinstance(transfer, dict) or set(transfer) != {"giver", "receiver", "resource", "quantity"}:
                raise ValueError("Counteroffer transfer fields are invalid.")
            if any(not isinstance(transfer[k], str) or not transfer[k] for k in ("giver", "receiver", "resource")):
                raise ValueError("Counteroffer participants and resources must be named.")
            if type(transfer["quantity"]) is not int or transfer["quantity"] <= 0:
                raise ValueError("Counteroffer quantities must be positive integers.")
    elif transfers != []:
        raise ValueError("An acceptance or rejection cannot change the proposed transfers.")
    return dict(raw)

def load_agents(yaml_path="data/profiles.yaml", **agent_options):
    import yaml
    with project_path(yaml_path).open() as f:
        data = yaml.safe_load(f)
    agents = [LLMNegotiationAgent(a["id"], a.get("style", "neutral"),
                                 a["inventory"], a["needs"], **agent_options)
              for a in data["agents"]]
    if len({a.agent_id for a in agents}) != len(agents):
        raise ValueError("Agent IDs must be unique.")
    return agents

def offer_within_tolerance(need, offer, tolerance=0.10):
    return need > 0 and offer > 0 and 0 <= tolerance <= 1 and abs(offer - need) <= tolerance * need

def _event(conversation, kind, **details):
    if hasattr(conversation, "events"):
        conversation.events.append({"kind": kind, **details})

def _terms_message(proposal, speaker):
    outgoing = [t for t in proposal.transfers if t.giver == speaker]
    incoming = [t for t in proposal.transfers if t.receiver == speaker]
    def describe(transfers):
        return " and ".join(f"{t.quantity} units of {t.resource.replace('_', ' ')}" for t in transfers)
    return f"I can offer {describe(outgoing)} in exchange for {describe(incoming)}."

def _approve(proposal, agents_by_id, conversation, *, counteroffers=None, proposer=None):

    validate_proposal(proposal, agents_by_id)
    conversation.append("SYSTEM: Proposed " + json.dumps(proposal.to_dict(), sort_keys=True))
    _event(conversation, "proposal", proposal=proposal.to_dict(), agent=proposer,
           message=_terms_message(proposal, proposer) if proposer else "Let's consider this multilateral exchange.")
    approvals = {}
    order = list(proposal.participants)
    if proposer in order:
        order.remove(proposer)
        order.insert(0, proposer)
    for aid in order:
        agent = agents_by_id[aid]
        incoming = [t for t in proposal.transfers if t.receiver == aid]
        try:
            if agent.auto_accept and incoming and all(
                offer_within_tolerance(agent.needs.get(t.resource, 0), t.quantity) for t in incoming
            ):
                decision = {"proposal_id": proposal.proposal_id, "action": "accept",
                            "reason": "This meets my needs within the tolerance I am willing to accept."}
            else:
                participants = {key: {"inventory": value.inventory, "needs": value.needs}
                                for key, value in agents_by_id.items() if key in proposal.participants}
                decision = parse_decision(agent.decide(proposal, conversation, participants=participants),
                                          proposal.proposal_id, aid)
            if decision["action"] == "counter":
                if proposal.kind != "bilateral" or counteroffers is None:
                    raise ValueError("Counteroffers are supported for bilateral negotiations only.")
                counter = Proposal.create([Transfer(**t) for t in decision["transfers"]])
                if set(counter.participants) != set(proposal.participants):
                    raise ValueError("Counteroffer must involve the same two agents.")
                validate_proposal(counter, agents_by_id)
                counteroffers.append((counter, aid))
                conversation.append("SYSTEM: Counteroffer " + json.dumps(counter.to_dict(), sort_keys=True))
                conversation.append(f"{aid}: counter {proposal.proposal_id} — {decision['reason']}")
                _event(conversation, "decision", agent=aid, **decision)
                _event(conversation, "counteroffer", agent=aid, proposal=counter.to_dict(),
                       message=_terms_message(counter, aid))
                # Original approvals cannot carry across changed terms.
                return {}
            conversation.append(f"{aid}: {decision['action']} {proposal.proposal_id} — {decision['reason']}")
            _event(conversation, "decision", agent=aid, **decision)
            if decision["action"] == "accept":
                approvals[aid] = proposal.proposal_id
        except Exception as exc:
            conversation.append(f"SYSTEM: Decision failed for {aid}: {type(exc).__name__}: {exc}")
            _event(conversation, "error", agent=aid, error=str(exc), category="invalid_response" if isinstance(exc, ValueError) else "provider_error")
    return approvals

def _remember(proposal, agents_by_id, accepted, conversation):
    for aid in proposal.participants:
        try:
            agents_by_id[aid].remember(proposal, accepted)
        except Exception as exc:
            conversation.append(f"SYSTEM: Memory failed for {aid}: {type(exc).__name__}: {exc}")
            _event(conversation, "memory_error", agent=aid, error=str(exc))

def _attempt(proposal, agents_by_id, conversation, records, *, counteroffers=None, proposer=None):
    try:
        approvals = _approve(proposal, agents_by_id, conversation, counteroffers=counteroffers, proposer=proposer)
        if set(approvals) != set(proposal.participants):
            _remember(proposal, agents_by_id, False, conversation)
            return False
        record = execute_proposal(proposal, agents_by_id, approvals)
    except ValueError as exc:
        conversation.append(f"SYSTEM: Proposal not executed: {exc}")
        _event(conversation, "invalid", error=str(exc))
        return False
    records.append(record)
    conversation.append(f"SYSTEM: Executed {proposal.kind} {proposal.proposal_id}")
    _event(conversation, "executed", proposal_id=proposal.proposal_id)
    _remember(proposal, agents_by_id, True, conversation)
    return True

def negotiate_pair(initiator, partner, confirmed_pairs, max_bilateral_rounds, contract_metadata,
                   *, conversation=None):
    conversation = Conversation() if conversation is None else conversation
    by_id = {a.agent_id: a for a in (initiator, partner)}
    if len(by_id) != 2:
        raise ValueError("Cannot negotiate with self.")
    start_count = len(contract_metadata)
    rounds_used = 0
    pending = None
    unavailable = False
    for turn in range(max_bilateral_rounds):
        if pending is not None:
            proposal, proposer = pending
            pending = None
        else:
            speaker, other = (initiator, partner) if turn % 2 == 0 else (partner, initiator)
            deal = speaker.propose_trade(other, fraction=min(1, 0.5 + turn * 0.1))
            if deal is None:
                unavailable = True
                break
            proposal = Proposal.create(
                [Transfer(speaker.agent_id, other.agent_id, r, q) for r, q in deal["offer"].items()] +
                [Transfer(other.agent_id, speaker.agent_id, r, q) for r, q in deal["request"].items()])
            proposer = speaker.agent_id
        rounds_used += 1
        counteroffers = []
        if _attempt(proposal, by_id, conversation, contract_metadata,
                    counteroffers=counteroffers, proposer=proposer):
            confirmed_pairs.add(tuple(sorted(by_id)))
            break
        if counteroffers:
            pending = counteroffers[-1]
    if len(contract_metadata) == start_count:
        _event(conversation, "not_agreed", message=("No compatible bilateral trade is available with the current inventories and needs." if unavailable else "No agreement was reached within the proposal limit. Check individual replies for rejections or invalid responses."))
    _event(conversation, "negotiation", rounds=rounds_used,
           agreed=len(contract_metadata) > start_count, negotiation_kind="bilateral")
    return conversation

def one_random_initiator_round(agents, confirmed_pairs, max_bilateral_rounds, contract_metadata,
                               *, rng=None, conversation=None):
    conversation = Conversation() if conversation is None else conversation
    candidates = [(a, b) for a in agents for b in agents
                  if a.agent_id < b.agent_id and a.can_request_from(b) and a.can_offer_to(b)
                  and tuple(sorted((a.agent_id, b.agent_id))) not in confirmed_pairs]
    if candidates:
        a, b = (rng or random).choice(candidates)
        negotiate_pair(a, b, confirmed_pairs, max_bilateral_rounds, contract_metadata,
                       conversation=conversation)
    return conversation

def run_negotiation_simulation(loop_ids=None, agents=None, yaml_path="data/profiles.yaml", rounds=3,
                               max_cycle_length=None, max_bilateral_rounds=3, *,
                               seed=0, record_on_chain=False, recorder=None, persist=False):
    if rounds < 0 or max_bilateral_rounds < 0:
        raise ValueError("Round limits must be nonnegative.")
    agents = load_agents(yaml_path) if agents is None else list(agents)
    if len({a.agent_id for a in agents}) != len(agents):
        raise ValueError("Agent IDs must be unique.")
    if loop_ids:
        missing = set(loop_ids) - {a.agent_id for a in agents}
        if missing:
            raise ValueError(f"Unknown selected agents: {sorted(missing)}")
        agents = [a for a in agents if a.agent_id in loop_ids]
    by_id = {a.agent_id: a for a in agents}
    conversation, records, pairs = Conversation(), [], set()
    before = {a.agent_id: a.get_utility() for a in agents}
    remaining_before = sum(sum(a.needs.values()) for a in agents)
    rng = random.Random(seed)
    for _ in range(rounds):
        one_random_initiator_round(agents, pairs, max_bilateral_rounds, records,
                                   rng=rng, conversation=conversation)
    # Bilateral results never authorise a cycle. Build and approve fresh terms.
    for loop in find_trade_loops(agents, max_cycle_length):
        proposal = loop_proposal(loop, by_id)
        if proposal is None:
            continue
        agreed = _attempt(proposal, by_id, conversation, records)
        _event(conversation, "negotiation", rounds=1, agreed=agreed, negotiation_kind="loop")
    for record in records:
        record["run_id"] = conversation.run_id
        record["timestamp"] = datetime.now(timezone.utc).isoformat()
        if record_on_chain:
            try:
                if recorder is None:
                    from blockchain.contract_manager import record_trade
                    recorder = record_trade
                record["contract_address"] = recorder(record)
                record["blockchain_status"] = "recorded"
            except Exception as exc:
                # Off-chain execution stands; recording failure never executes again.
                record["blockchain_status"] = "failed"
                record["blockchain_error"] = f"{type(exc).__name__}: {exc}"
                conversation.append(f"SYSTEM: Blockchain recording failed for {record['proposal_id']}: {exc}")
                _event(conversation, "recording_error", message="The trade completed, but its blockchain record could not be saved.")
        if persist:
            from utils.history_store import save_trade_to_history
            try:
                save_trade_to_history(record)
            except Exception as exc:
                record["persistence_error"] = str(exc)
                conversation.append(f"SYSTEM: Could not persist trade: {exc}")
    conversation.metrics = summarize_run(agents, before, remaining_before, conversation.events, records)
    conversation.metrics["run_id"] = conversation.run_id
    return conversation, records
