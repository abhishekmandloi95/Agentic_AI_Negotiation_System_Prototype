import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import yaml
import json
from agents.seller_agent import SellerAgent
from negotiation.protocol import multilateral_cycle_negotiation

def load_agents():
    with open("data/profiles.yaml", "r") as f:
        profiles = yaml.safe_load(f)["agents"]
    return [SellerAgent(p["id"], p) for p in profiles], profiles


def generate_contract(chain):
    contract = {
        "type": "MultilateralAgreement",
        "agents": [a.agent_id for a in chain],
        "flow": " → ".join([a.agent_id for a in chain] + [chain[0].agent_id]),
        "offers": []
    }
    for i in range(len(chain)):
        sender = chain[i]
        receiver = chain[(i + 1) % len(chain)]
        offer = sender.make_offer(receiver)
        contract["offers"].append({
            "from": sender.agent_id,
            "to": receiver.agent_id,
            "item": offer["item"],
            "price": offer["price"]
        })
    return contract


st.set_page_config(page_title="Agentic Exchange UI", layout="centered")
st.title("Agentic AI Multilateral Negotiation UI")


agents, raw_profiles = load_agents()
st.subheader("Loaded Agents")
st.json(raw_profiles)


if st.button("Run Multilateral Negotiation"):
    with st.spinner("Running multilateral loop logic..."):
        from negotiation.protocol import find_valid_cycles, is_valid_chain

        valid_cycles = find_valid_cycles(agents)
        if not valid_cycles:
            st.error(" No valid chain found.")
        else:
            selected_chain = valid_cycles[0]
            st.success("Valid chain found:")
            st.markdown(" → ".join(a.agent_id for a in selected_chain) + f" → {selected_chain[0].agent_id}")

            st.subheader("Smart Contract")
            contract = generate_contract(selected_chain)
            st.json(contract)