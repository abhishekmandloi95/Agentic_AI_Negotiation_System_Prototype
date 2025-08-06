import random
import yaml
import re
from web3 import Web3
from negotiation.rag_memory import NegotiationRAGMemory
from agents.base_agent import LLMNegotiationAgent
from negotiation.loop_trader import detect_and_execute_loops
from blockchain.contract_manager import deploy_contract

# Web3 connection
_w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:7545"))
if not _w3.is_connected():
    raise ConnectionError("Start Ganache (port 7545) before running.")

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

def negotiate_pair(initiator, partner, confirmed_pairs, max_bilateral_rounds):
    convo = []

    # Lock service from the initiator's first proposed trade
    first_deal = initiator.propose_trade(partner)
    locked_service = None
    if first_deal:
        locked_service = next(iter(first_deal["offer"].keys()))

    # First message
    raw_msg = initiator.open_negotiation(partner, max_rounds=max_bilateral_rounds)
    clean_msg = clean_text(raw_msg.lstrip(f"{initiator.agent_id}: ").lstrip())
    convo.append(f"{initiator.agent_id}: {clean_msg}")

    last_speaker = initiator.agent_id

    for turn in range(max_bilateral_rounds):
        # Alternate speaker
        speaker, other = (partner, initiator) if last_speaker == initiator.agent_id else (initiator, partner)

        raw_reply = speaker.respond(other, clean_msg, convo, last_speaker, max_rounds=max_bilateral_rounds)
        clean_reply = clean_text(raw_reply.lstrip(f"{speaker.agent_id}: ").lstrip())

        # --- Auto-accept tolerance ---
        if CONFIRM_KEYWORD not in clean_reply.lower():
            try:
                deal = speaker.propose_trade(other)
                if deal:
                    service_given, offered_quantity = next(iter(deal["offer"].items()))
                    agent_need = other.needs.get(service_given, 0)

                    if offer_within_tolerance(agent_need, offered_quantity):
                        # Explain why accepting
                        clean_reply = (
                            f"This offer is within 10% of my desired quantity "
                            f"({offered_quantity} vs need {agent_need}), so I accept the deal.\n"
                            f"{CONFIRM_KEYWORD}"
                        )
                        # Append immediately and confirm without counting this as a normal turn
                        convo.append(f"{speaker.agent_id}: {clean_reply}")
                        confirmed_pairs.add(tuple(sorted([initiator.agent_id, partner.agent_id])))

                        # Immediate inventory update
                        service_given, qty_given = next(iter(deal["offer"].items()))
                        service_recvd, qty_recvd = next(iter(deal["request"].items()))
                        if service_given not in speaker.inventory:
                            speaker.inventory[service_given] = 0
                        if service_given not in other.inventory:
                            other.inventory[service_given] = 0
                        speaker.inventory[service_given] -= qty_given
                        other.inventory[service_given] += qty_given
                        other.needs[service_given] = max(0, other.needs.get(service_given, 0) - qty_given)

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
                service_given, qty_given = next(iter(deal["offer"].items()))
                service_recvd, qty_recvd = next(iter(deal["request"].items()))
                if service_given not in speaker.inventory:
                    speaker.inventory[service_given] = 0
                if service_given not in other.inventory:
                    other.inventory[service_given] = 0
                speaker.inventory[service_given] -= qty_given
                other.inventory[service_given] += qty_given
                other.needs[service_given] = max(0, other.needs.get(service_given, 0) - qty_given)
            break

    # After negotiation loop (no deal reached)
    if not any(tok in clean_msg.lower() for tok in [CONFIRM_KEYWORD]):
        if not locked_service:
            reason = "[No deal closed: no common valid service found]"
        else:
            reason = '[No deal closed: no "deal accepted" from LLM]'
        convo.append(reason)

    return convo

def one_random_initiator_round(agents, confirmed_pairs, max_bilateral_rounds):
    initiator = random.choice(agents)
    for partner in agents:
        if initiator.agent_id == partner.agent_id:
            continue
        if not initiator.can_request_from(partner):
            continue
        return negotiate_pair(initiator, partner, confirmed_pairs, max_bilateral_rounds)
    return []

# def run_negotiation_simulation(loop_ids, yaml_path="profiles.yaml", rounds=3,
#                                max_cycle_length=None, max_bilateral_rounds=3):
#     agents = load_agents(yaml_path)
#     confirmed_pairs = set()

#     unmapped = [a for a in agents if a.agent_id not in AGENT_ADDR]
#     for i, agent in enumerate(unmapped, start=len(AGENT_ADDR)):
#         AGENT_ADDR[agent.agent_id] = _w3.eth.accounts[i]

#     if loop_ids:
#         agents = [a for a in agents if a.agent_id in loop_ids]

#     conversation = []
#     for _ in range(rounds):
#         conversation.extend(one_random_initiator_round(agents, confirmed_pairs, max_bilateral_rounds))

#     loops = detect_and_execute_loops(agents, max_cycle_length=max_cycle_length, confirmed_pairs=confirmed_pairs)

#     for loop, qty in loops:
#         path = " → ".join(f"{f}->{t}({r})" for f, t, r in loop)
#         status = "[VALID]" if qty > 0 else "[INVALID]"
#         conversation.append(f"Loop: {path} | qty each: {qty} {status}")
#         if qty > 0:
#             first_from, _, out_resource = loop[0]
#             in_edge = next(edge for edge in loop if edge[1] == first_from)
#             _, in_from, in_resource = in_edge
#             loop_deal = {
#                 "offer": {out_resource: qty},
#                 "request": {in_resource: qty},
#             }
#             loop_ids = [edge[0] for edge in loop]
#             _deploy_from_deal(loop_deal, first_from, in_from, note="multilateral loop", loop_ids=loop_ids)

#     return conversation

def run_negotiation_simulation(loop_ids, yaml_path="profiles.yaml", rounds=3,
                               max_cycle_length=None, max_bilateral_rounds=3):
    agents = load_agents(yaml_path)
    confirmed_pairs = set()

    unmapped = [a for a in agents if a.agent_id not in AGENT_ADDR]
    for i, agent in enumerate(unmapped, start=len(AGENT_ADDR)):
        AGENT_ADDR[agent.agent_id] = _w3.eth.accounts[i]

    if loop_ids:
        agents = [a for a in agents if a.agent_id in loop_ids]

    conversation = []
    for _ in range(rounds):
        conversation.extend(one_random_initiator_round(agents, confirmed_pairs, max_bilateral_rounds))

    # Now detect loops, with optional reasons from detect_and_execute_loops()
    loops = detect_and_execute_loops(
        agents,
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

    return conversation