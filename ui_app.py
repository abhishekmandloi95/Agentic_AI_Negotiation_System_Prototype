import streamlit as st
import yaml
from negotiation.loop_trader import find_trade_loops
from negotiation.protocol import run_negotiation_simulation
from agents.base_agent import LLMNegotiationAgent
import networkx as nx
from blockchain.contract_manager import DEPLOY_LOGS

# --- Load agent profiles ---
with open("data/profiles.yaml") as f:
    agent_profiles = yaml.safe_load(f)["agents"]

agent_ids = [agent["id"] for agent in agent_profiles]

st.title(" Multi-Agent Negotiation Viewer")

st.markdown("### Available Agents:")
st.write(", ".join(agent_ids))


# --- Build graph based on inventory and needs ---
def build_graph(agents):
    G = nx.DiGraph()
    for agent in agents:
        for need in agent["needs"]:
            for supplier in agents:
                if agent["id"] != supplier["id"] and need in supplier["inventory"]:
                    if supplier["inventory"][need] >= agent["needs"][need]:
                        G.add_edge(agent["id"], supplier["id"])
    return G


# --- Create LLM Agent instances ---
def build_agents_by_id(profiles):
    return {
        p["id"]: LLMNegotiationAgent(
            agent_id  = p["id"],
            style     = p.get("style", "neutral"),
            inventory = p["inventory"].copy(),
            needs     = p["needs"].copy()
        )
        for p in profiles
    }


# --- Automatic Loop Run ---
mode = st.radio("Select Negotiation Mode:", ["Run each loop separately", "Run one large negotiation"])

#1️Add two sliders before the button
n_rounds     = st.slider("How many bilateral rounds?", 1, len(agent_ids), len(agent_ids))
max_loop_len = st.slider("Max agents in a loop?",    2, len(agent_ids), len(agent_ids))

max_bilateral_rounds = n_rounds

if st.button("Start Negotiation"):
    agents_by_id = build_agents_by_id(agent_profiles)
    agents = list(agents_by_id.values())
    
    if mode == "Run each loop separately":
        loops = find_trade_loops(agents, max_cycle_length=max_loop_len)
        if not loops:
            st.error("No valid negotiation loops found.")
        else:
            for loop in loops:
                 # 1) extract the unique IDs in this loop
                 ids_in_loop = [edge[0] for edge in loop]

                 # 2) display the full cycle once
                 cycle_banner = " → ".join(ids_in_loop + [ids_in_loop[0]])
                 st.success(f"Running negotiation for loop: {cycle_banner}")
 
                 # 3) run negotiation *only* among those agents
                 conversation = run_negotiation_simulation(
                 ids_in_loop,
                 "data/profiles.yaml",
                 rounds=n_rounds, 
                 max_cycle_length=max_loop_len,
                 max_bilateral_rounds=max_bilateral_rounds
                 )
                 for line in conversation:
                     st.markdown(line)
                 st.markdown("---")
    else:
        # Run one large negotiation
        st.success("Running one large negotiation with all agents.")
        
        conversation = run_negotiation_simulation(
             [], 
             "data/profiles.yaml",
             rounds=n_rounds,
             max_cycle_length=max_loop_len,
             max_bilateral_rounds=max_bilateral_rounds
         )
        for line in conversation:
            st.markdown(line)

# --- Manual Loop (Debugging Mode) ---
with st.expander("🛠️ Manually Select Agents"):
    selected_agents = st.multiselect("Choose agent IDs:", agent_ids)
    if st.button("▶️ Run Manual Negotiation"):
        if len(selected_agents) < 2:
            st.warning("Please select at least 2 agents.")
        else:
            st.success(f"Running manual negotiation: {' → '.join(selected_agents)}")
            conversation = run_negotiation_simulation(selected_agents)
            for line in conversation:
                if ": " in line:
                    agent, msg = line.split(": ", 1)
                    st.markdown(msg)
                else:
                    st.markdown(line)

if DEPLOY_LOGS:
    st.subheader("Contracts deployed in this run")
    for addr, human in DEPLOY_LOGS.items():
        st.code(f"{human}   ({addr})") #shows the address as well