import random
import yaml
import re
from web3 import Web3
from negotiation.rag_memory import NegotiationRAGMemory
from agents.base_agent import LLMNegotiationAgent
from negotiation.loop_trader import detect_and_execute_loops
from blockchain.contract_manager import deploy_contract
from market.service import service as market_insights
from metrics.evaluation import log_conversation

SHOW_MARKET_SYSTEM_LINES = False

# Web3 connection
# _w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:7545"))
# if not _w3.is_connected():
#     raise ConnectionError("Start Ganache (port 7545) before running.")

# ✅ Lazy connection
def get_w3():
    w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:7545"))
    if not w3.is_connected():
        raise ConnectionError("Start Ganache (port 7545) before running.")
    return w3

AGENT_ADDR: dict[str, str] = {}
rag_memory = NegotiationRAGMemory()

CONFIRM_KEYWORD = "deal accepted"

def clean_text(reply: str) -> str:
    """Fix common tokenization typos."""
    reply = reply.replace("iven ", "Given ")
    reply = reply.replace("I: 'm", "I'm")
    return reply

def _deploy_from_deal(deal: dict, from_id: str, to_id: str, note: str, loop_ids=None):
    service_given, qty_given = next(iter(deal["offer"].items()))
    service_recvd, qty_recvd = next(iter(deal["request"].items()))

    if from_id == to_id:
        human_note = (f"{' → '.join(loop_ids)}  |  "
                      f"{qty_given} {service_given} ⇄ {qty_recvd} {service_recvd}")
    else:
        human_note = (f"{from_id} → {to_id} : "
                      f"{qty_given} {service_given} ⇄ {qty_recvd} {service_recvd}")

    deploy_contract(
        party_from=AGENT_ADDR[from_id],
        party_to=AGENT_ADDR[to_id],
        service_given=service_given,
        service_received=service_recvd,
        qty_given=qty_given,
        qty_received=qty_recvd,
        note=human_note
    )

def load_agents(yaml_path: str):
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    return [
        LLMNegotiationAgent(
            agent_id=a["id"],
            style=a.get("style", "neutral"),
            inventory=a["inventory"].copy(),
            needs=a["needs"].copy(),
        ) for a in data["agents"]
    ]

def offer_within_tolerance(need, offer, tolerance=0.10):
    return abs(offer - need) <= tolerance * need

def negotiate_pair(initiator, partner, confirmed_pairs, max_bilateral_rounds, contract_metadata):
    convo = []

    # Lock service from the initiator's first proposed trade
    first_deal = initiator.propose_trade(partner)
    locked_service = None
    if first_deal:
        locked_service = next(iter(first_deal["offer"].keys()))

    # Market context for initiator
    if SHOW_MARKET_SYSTEM_LINES:
        for res in getattr(initiator, "needs", {}) or {}:
            trend = market_insights.get_trend(res)
            convo.append(f"SYSTEM: Forecast indicates '{res}' market is trending {trend}.")

    # First message
    if hasattr(raw_msg := initiator.open_negotiation(partner, max_rounds=max_bilateral_rounds), "content"):
        raw_msg = raw_msg.content
    clean_msg = clean_text(str(raw_msg).lstrip(f"{initiator.agent_id}: ").lstrip())
    convo.append(f"{initiator.agent_id}: {clean_msg}")

    last_speaker = initiator.agent_id

    for turn in range(max_bilateral_rounds):
        # Alternate speaker
        speaker, other = (partner, initiator) if last_speaker == initiator.agent_id else (initiator, partner)

        # Market context for current speaker
        if SHOW_MARKET_SYSTEM_LINES:
            for res in getattr(speaker, "needs", {}) or {}:
                trend = market_insights.get_trend(res)
                convo.append(f"SYSTEM: Forecast indicates '{res}' market is trending {trend}.")

        raw_reply = speaker.respond(other, clean_msg, convo, last_speaker, max_rounds=max_bilateral_rounds)
        if hasattr(raw_reply, "content"):
            raw_reply = raw_reply.content
        clean_reply = clean_text(str(raw_reply).lstrip(f"{speaker.agent_id}: ").lstrip())

        # --- Auto-accept tolerance ---
        if CONFIRM_KEYWORD not in clean_reply.lower():
            try:
                deal = speaker.propose_trade(other)
                if deal:
                    service_given, offered_quantity = next(iter(deal["offer"].items()))
                    agent_need = other.needs.get(service_given, 0)

                    if offer_within_tolerance(agent_need, offered_quantity):
                        # Explain why accepting
                        pct = abs(offered_quantity - agent_need) / max(1e-9, agent_need) * 100
                        clean_reply = (
                            f"This offer for {service_given} is within 10% of my desired quantity "
                            f"({offered_quantity} vs need {agent_need}), so I accept the deal.\n"
                            f"{CONFIRM_KEYWORD}"
                        )
                        # Append immediately and confirm without counting this as a normal turn
                        convo.append(f"{speaker.agent_id}: {clean_reply}")
                        confirmed_pairs.add(tuple(sorted([initiator.agent_id, partner.agent_id])))

                        # Immediate inventory update
                        # Apply both legs of the accepted deal atomically
                        speaker.execute_trade(other, deal["offer"], deal["request"])


                        return convo  # ✅ End negotiation immediately
            except Exception:
                pass

        # Append normal response
        convo.append(f"{speaker.agent_id}: {clean_reply}")
        clean_msg = clean_reply
        last_speaker = speaker.agent_id

        # If confirmed → record and update inventory now
        if CONFIRM_KEYWORD in clean_reply.lower():
            confirmed_pairs.add(tuple(sorted([initiator.agent_id, partner.agent_id])))
            deal = speaker.propose_trade(other)
            if deal:
                speaker.execute_trade(other, deal["offer"], deal["request"])
                contract_metadata.append({
                    "initiator": speaker.agent_id,
                    "responder": other.agent_id,
                    "service_given": next(iter(deal["offer"])),
                    "quantity_given": next(iter(deal["offer"].values())),
                    "service_received": next(iter(deal["request"])),
                    "quantity_received": next(iter(deal["request"].values())),
                    "contract_address": None  # to be filled by UI or deploy_contract
                })
            break

    # After negotiation loop (no deal reached)
    if not any(tok in clean_msg.lower() for tok in [CONFIRM_KEYWORD]):
        if not locked_service:
            reason = "[No deal closed: no common valid service found]"
        else:
            reason = '[No deal closed: no "deal accepted" from LLM]'
        convo.append(reason)

    return convo

def one_random_initiator_round(agents, confirmed_pairs, max_bilateral_rounds, contract_metadata):
    initiator = random.choice(agents)
    for partner in agents:
        if initiator.agent_id == partner.agent_id:
            continue
        if not initiator.can_request_from(partner):
            continue
        if tuple(sorted([initiator.agent_id, partner.agent_id])) in confirmed_pairs:
            continue  # Skip if already dealt
        return negotiate_pair(initiator, partner, confirmed_pairs, max_bilateral_rounds, contract_metadata)
    return []

def run_negotiation_simulation(loop_ids, agents=None, yaml_path="profiles.yaml", rounds=3,
                               max_cycle_length=None, max_bilateral_rounds=3):
    if agents is None:
        agents = load_agents(yaml_path)
    confirmed_pairs = set()

    unmapped = [a for a in agents if a.agent_id not in AGENT_ADDR]
    for i, agent in enumerate(unmapped, start=len(AGENT_ADDR)):
        # AGENT_ADDR[agent.agent_id] = _w3.eth.accounts[i]
        AGENT_ADDR[agent.agent_id] = get_w3().eth.accounts[i]

    if loop_ids:
        loop_agents = [a for a in agents if a.agent_id in loop_ids]
    else:
        loop_agents = agents

    contract_metadata = []
    conversation = []
    for _ in range(rounds):
        conversation.extend(one_random_initiator_round(loop_agents, confirmed_pairs, max_bilateral_rounds, contract_metadata))

    loops = detect_and_execute_loops(
        loop_agents,
        max_cycle_length=max_cycle_length,
        confirmed_pairs=confirmed_pairs
    )

    for loop_entry in loops:
        # Allow detect_and_execute_loops() to optionally return a reason
        if len(loop_entry) == 3:
            loop, qty, reason = loop_entry
        else:
            loop, qty = loop_entry
            reason = ""

        path = " → ".join(f"{f}->{t}({r})" for f, t, r in loop)
        status = "[VALID]" if qty > 0 else "[INVALID]"

        # Append reason to conversation so it shows in Streamlit
        if reason:
            conversation.append(f"Loop: {path} | qty each: {qty} {status} {reason}")
        else:
            conversation.append(f"Loop: {path} | qty each: {qty} {status}")

        if qty > 0:
            first_from, _, out_resource = loop[0]
            in_edge = next(edge for edge in loop if edge[1] == first_from)
            _, in_from, in_resource = in_edge
            loop_deal = {
                "offer": {out_resource: qty},
                "request": {in_resource: qty},
            }
            loop_ids = [edge[0] for edge in loop]
            _deploy_from_deal(
                loop_deal,
                first_from,
                in_from,
                note="multilateral loop",
                loop_ids=loop_ids
            )
            
    log_conversation([a.agent_id for a in loop_agents], {a.agent_id: a for a in loop_agents}, conversation)

    return conversation, contract_metadata