import random
import yaml
from web3 import Web3

from agents.base_agent import LLMNegotiationAgent
from negotiation.loop_trader import detect_and_execute_loops
from blockchain.contract_manager import deploy_contract

# ────────────────────────────────────────────────────────────────
# Web3 connection & address map
# ────────────────────────────────────────────────────────────────
_w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:7545"))
if not _w3.is_connected():
    raise ConnectionError("Start Ganache (port 7545) before running.")

AGENT_ADDR: dict[str, str] = {}          # agent-ID ➜ 0x address


# ────────────────────────────────────────────────────────────────
# Helper: translate a deal object into deploy_contract parameters
# ────────────────────────────────────────────────────────────────
def _deploy_from_deal(deal: dict, from_id: str, to_id: str, note: str, loop_ids: list[str] | None = None) -> None:
    """
    deal shape:
      {
        "offer":   {"data_service": 30},
        "request": {"ux_research": 30}
      }
    """
    service_given,  qty_given  = next(iter(deal["offer"].items()))
    service_recvd, qty_recvd  = next(iter(deal["request"].items()))

    if from_id == to_id:
        human_note = (f"{' → '.join(loop_ids)}  |  "
                  f"{qty_given} {service_given} ⇄ "
                  f"{qty_recvd} {service_recvd}")
    else:
        human_note = (f"{from_id} → {to_id} : "
                  f"{qty_given} {service_given} ⇄ {qty_recvd} {service_recvd}")


    deploy_contract(
        party_from       = AGENT_ADDR[from_id],
        party_to         = AGENT_ADDR[to_id],
        service_given    = service_given,
        service_received = service_recvd,
        qty_given        = qty_given,
        qty_received     = qty_recvd,
        note             = human_note
    )


# ────────────────────────────────────────────────────────────────
# Agent loading
# ────────────────────────────────────────────────────────────────
def load_agents(yaml_path: str):
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    agents = [
        LLMNegotiationAgent(
            agent_id=a["id"],
            style=a.get("style", "neutral"),
            inventory=a["inventory"].copy(),
            needs=a["needs"].copy(),
        )
        for a in data["agents"]
    ]
    return agents


# ────────────────────────────────────────────────────────────────
# Bilateral negotiation
# ────────────────────────────────────────────────────────────────
def negotiate_pair(initiator, partner):
    convo = []

    # 1) Opening offer
    raw_msg = initiator.open_negotiation(partner)
    clean_msg = raw_msg.lstrip(f"{initiator.agent_id}: ").lstrip()
    convo.append(f"{initiator.agent_id}: {clean_msg}")

    last_speaker = initiator.agent_id
    accept_tokens = ["deal accepted"]

    # 2) Back-and-forth (max 6 replies)
    for _ in range(6):
        speaker, other = (
            (partner, initiator)
            if last_speaker == initiator.agent_id
            else (initiator, partner)
        )

        raw_reply = speaker.respond(other, clean_msg, convo, last_speaker)
        clean_reply = raw_reply.lstrip(f"{speaker.agent_id}: ").lstrip()
        convo.append(f"{speaker.agent_id}: {clean_reply}")

        last_speaker, clean_msg = speaker.agent_id, clean_reply

        # 3) Agreement?
        if any(tok in clean_reply.lower() for tok in accept_tokens):
            deal = initiator.propose_trade(partner)
            if deal and partner.can_request_from(initiator):
                initiator.execute_trade(partner, deal["offer"], deal["request"])
                convo.append(
                    f"{initiator.agent_id}⇆{partner.agent_id}: "
                    f"{deal['offer']} for {deal['request']}"
                )

                _deploy_from_deal(
                    deal,
                    initiator.agent_id,
                    partner.agent_id,
                    note="bilateral",
                )
            break

    return convo


def one_random_initiator_round(agents):
    initiator = random.choice(agents)
    for partner in agents:
        if initiator.agent_id == partner.agent_id:
            continue
        if not initiator.can_request_from(partner):
            continue
        return negotiate_pair(initiator, partner)
    return []


# ────────────────────────────────────────────────────────────────
# Top-level simulation
# ────────────────────────────────────────────────────────────────
def run_negotiation_simulation(
    loop_ids,
    yaml_path="profiles.yaml",
    rounds=3,
    max_cycle_length=None,
):
    """
    Returns a flat list of every message plus any loop summaries.
    """

    agents = load_agents(yaml_path)

    # Map Ganache dev accounts to agent IDs (once per process)
    unmapped = [a for a in agents if a.agent_id not in AGENT_ADDR]
    for i, agent in enumerate(unmapped, start=len(AGENT_ADDR)):
        AGENT_ADDR[agent.agent_id] = _w3.eth.accounts[i]

    # keep only agents in the requested loop, if provided
    if loop_ids:
        agents = [a for a in agents if a.agent_id in loop_ids]

    conversation = []

    # 1) Bilateral rounds
    for _ in range(rounds):
        conversation.extend(one_random_initiator_round(agents))

    # 2) Detect & settle multilateral loops
    loops = detect_and_execute_loops(agents, max_cycle_length)
    for loop, qty in loops:
        path = " → ".join(f"{f}->{t}({r})" for f, t, r in loop)
        status = "[VALID]" if qty > 0 else "[INVALID]"
        conversation.append(f"Loop: {path} | qty each: {qty} {status}")

        if qty > 0:
            first_from, _, out_resource = loop[0]
            in_edge = next(edge for edge in loop if edge[1] == first_from)
            _, in_from, in_resource = in_edge

            loop_deal = {
                "offer":   {out_resource: qty},
                "request": {in_resource:  qty},
            }
            # _deploy_from_deal(
            #     loop_deal,
            #     first_from,
            #     in_from,
            #     note="multilateral loop",
            # )

            loop_ids = [edge[0] for edge in loop] 
            
            _deploy_from_deal(loop_deal, first_from, in_from,
                  note="multilateral loop",
                  loop_ids=loop_ids)

    return conversation