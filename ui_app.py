import streamlit as st
import yaml
from negotiation.loop_trader import find_trade_loops
from negotiation.protocol import run_negotiation_simulation
from agents.base_agent import LLMNegotiationAgent
import networkx as nx
from blockchain.contract_manager import DEPLOY_LOGS
from market.service import service as market_insights
import requests
from utils.history_store import load_trade_history
from web3 import Web3
import json
import pandas as pd
import copy
from metrics.evaluation import evaluate
from utils.history_store import create_conversation_log, append_conversation_line

with st.expander("📜 View Trade Contracts"):
    st.header("📜 Deployed Trade Contracts")

    show_history = st.toggle("Include historical trades", value=False)

    contracts_to_render = []

    if show_history:
        contracts_to_render = load_trade_history()
    else:
        in_progress = st.session_state.get("in_progress_contracts", [])
        current = st.session_state.get("current_contracts", [])
        live_contracts = [c for c in current if c.get("source") == "live"]
        contracts_to_render = in_progress + live_contracts

    contracts_to_render = [c for c in contracts_to_render if c]  # remove None/empty

    if not contracts_to_render:
        st.info("No contracts to show.")
    else:
        for i, trade in enumerate(contracts_to_render):
            if not trade.get("contract_address"):
                st.subheader(f"📝 Simulated Contract {i+1}")
                st.markdown(f"""
                - **Initiator**: {trade['initiator']}
                - **Responder**: {trade['responder']}
                - **Service Given**: {trade['service_given']} ({trade['quantity_given']})
                - **Service Received**: {trade['service_received']} ({trade['quantity_received']})
                """)
                continue
            st.subheader(f"🔗 Trade {i+1}: {trade['contract_address']}")
            st.markdown(f"""
            - **Initiator**: {trade['initiator']}
            - **Responder**: {trade['responder']}
            - **Service Given**: {trade['service_given']} ({trade['quantity_given']})
            - **Service Received**: {trade['service_received']} ({trade['quantity_received']})
            """)
            # Try live contract read
            try:
                contract = web3.eth.contract(address=trade['contract_address'], abi=abi)
                service = contract.functions.serviceGiven().call()
                st.success(f"✅ Contract live — service given: {service}")
            except Exception as e:
                st.warning(f"⚠️ Contract not readable (might be expired): {e}")
    
def render_agents_table():
    agents_data = []
    for agent in st.session_state.get("agents", []):
        inventory_str = "\n".join([f"{k}: {v}" for k, v in agent.inventory.items()])
        needs_str = "\n".join([f"{k}: {v}" for k, v in agent.needs.items()])
        agents_data.append({
            "Agent": agent.agent_id,
            "Inventory": inventory_str,
            "Needs": needs_str
        })
    df = pd.DataFrame(agents_data)
    agents_table_container.markdown("### 📌 Agent Inventory and Needs")
    agents_table_container.dataframe(df, use_container_width=True)

if "current_contracts" not in st.session_state:
    st.session_state.current_contracts = []

# --- Load agent profiles ---
with open("data/profiles.yaml") as f:
    agent_profiles = yaml.safe_load(f)["agents"]

with open("blockchain/TradeAgreement.json") as f:
    abi = json.load(f)["abi"]

web3 = Web3(Web3.HTTPProvider("http://127.0.0.1:7545"))

agent_ids = [agent["id"] for agent in agent_profiles]

if "agents" not in st.session_state:
    agents_by_id = {
        p["id"]: LLMNegotiationAgent(
            agent_id  = p["id"],
            style     = p.get("style", "neutral"),
            inventory = p["inventory"].copy(),
            needs     = p["needs"].copy()
        )
        for p in agent_profiles
    }
    st.session_state["agents"] = list(agents_by_id.values())


st.title(" Multi-Agent Negotiation Viewer")

# Sidebar refresh control
with st.sidebar:
    agents_table_container = st.container()  # ✅ Move here to show sidebar table
    ganache_status = False
    def is_ganache_running(url="http://127.0.0.1:7545"):
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "web3_clientVersion",
                "params": [],
                "id": 1
            }
            response = requests.post(url, json=payload, timeout=1)
            if response.status_code == 200 and "result" in response.json():
                return True
            return False
        except requests.exceptions.RequestException:
            return False

    ganache_status = is_ganache_running()
    ganache_html = f"""
        <div style="
            position: fixed;
            top: 10px;
            left: 10px;
            background-color: {'#22c55e' if ganache_status else '#ef4444'};
            color: white;
            padding: 6px 12px;
            border-radius: 6px;
            font-weight: bold;
            z-index: 9999;
            box-shadow: 0px 2px 6px rgba(0,0,0,0.2);
        ">
            {'🟢 Ganache: Online' if ganache_status else '🔴 Ganache: Offline'}
        </div>
    """
    st.markdown(ganache_html, unsafe_allow_html=True)

    st.markdown("### Agent Controls")
    refresh_clicked = st.checkbox("🔄 Show updated Agent Table", key="refresh_agents_table_checkbox")
    if refresh_clicked:
        render_agents_table()

    st.markdown("### Available Agents:")
    st.write(", ".join(agent_ids))

    if st.sidebar.button("🧹 Clear Conversation Log"):
        st.session_state["conversation_log"] = []


    # Commented out to avoid double rendering on refresh
    # if st.session_state.get("refresh_agents_table"):
    #     render_agents_table()
    #     st.session_state["refresh_agents_table"] = False

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

# --- Create LLM Agent instances (using session state only once) ---
def build_agents_by_id(profiles):
    if "agents" not in st.session_state:
        st.session_state["agents"] = [
            LLMNegotiationAgent(
                agent_id=p["id"],
                style=p.get("style", "neutral"),
                inventory=p["inventory"].copy(),
                needs=p["needs"].copy()
            )
            for p in profiles
        ]
    
    # ✅ Build and return mapping from existing session-state agents
    return {agent.agent_id: agent for agent in st.session_state["agents"]}

# --- Automatic Loop Run ---
mode = st.radio("Select Negotiation Mode:", ["Run each loop separately", "Run one large negotiation"])

#1️Add two sliders before the button
n_rounds     = st.slider("How many bilateral rounds?", 1, len(agent_ids), len(agent_ids))
max_loop_len = st.slider("Max agents in a loop?",    2, len(agent_ids), len(agent_ids))

max_bilateral_rounds = n_rounds

if st.button("Start Negotiation"):
    st.session_state["start_negotiation"] = True

if st.session_state.get("start_negotiation"):
    if not is_ganache_running():
        st.error("⚠️ Ganache is offline. Please start Ganache first.")
        st.session_state["start_negotiation"] = False  # ✅ reset trigger
        st.stop()

    # Conversation log file creation
    log_path = create_conversation_log()
    st.session_state["conversation_log_path"] = log_path
    if "conversation_log" in st.session_state:
        del st.session_state["conversation_log"]

    all_agents = st.session_state["agents"]
    agents_by_id = {agent.agent_id: agent for agent in all_agents}

    # --- Market configuration (dynamic, no hardcoded resources)
    all_resources = set()
    for a in all_agents:
        all_resources.update(a.inventory.keys())
        all_resources.update(a.needs.keys())

    market_insights.configure(all_resources)
    market_insights.update_market()  # advance one step this run

    if mode == "Run each loop separately":
        loops = find_trade_loops(all_agents, max_cycle_length=max_loop_len)
        if not loops:
            st.error("No valid negotiation loops found.")
        else:
            for loop in loops:
                ids_in_loop = [edge[0] for edge in loop]
                cycle_banner = " → ".join(ids_in_loop + [ids_in_loop[0]])
                st.success(f"Running negotiation for loop: {cycle_banner}")
                market_insights.update_market()
                conversation, contract_metadata = run_negotiation_simulation(
                    loop_ids=ids_in_loop,
                    agents=all_agents,
                    rounds=n_rounds,
                    max_cycle_length=max_loop_len,
                    max_bilateral_rounds=n_rounds
                )
                if "in_progress_contracts" not in st.session_state:
                    st.session_state["in_progress_contracts"] = []
                st.session_state["in_progress_contracts"].extend(contract_metadata)
                if "current_contracts" not in st.session_state:
                    st.session_state["current_contracts"] = []
                for item in contract_metadata:
                    item["source"] = "live"
                st.session_state["current_contracts"].extend(contract_metadata)

                if "conversation_log" not in st.session_state:
                    st.session_state["conversation_log"] = []

                for line in conversation:
                    if "Running negotiation for loop:" in line:
                        st.success(line)
                    else:
                        st.markdown(line)
                    st.session_state["conversation_log"].append(line)
                    # Try extracting metadata for structured logging
                    try:
                        if ": " in line:
                            agent, msg = line.split(": ", 1)
                            exchange_details = None
                            if "⇄" in msg or "exchange" in msg.lower():
                                exchange_details = msg
                            append_conversation_line(agent, msg, exchange_details, path=st.session_state.get("conversation_log_path"))
                    except Exception as e:
                        print("Logging error:", e)
                st.markdown("---")
    else:
        st.success("Running one large negotiation with all agents.")
        market_insights.update_market()
        conversation, contract_metadata = run_negotiation_simulation(
            loop_ids=[],
            agents=all_agents,
            rounds=n_rounds,
            max_cycle_length=max_loop_len,
            max_bilateral_rounds=n_rounds
        )
        if "in_progress_contracts" not in st.session_state:
            st.session_state["in_progress_contracts"] = []
        st.session_state["in_progress_contracts"].extend(contract_metadata)
        if "current_contracts" not in st.session_state:
            st.session_state["current_contracts"] = []
        for item in contract_metadata:
            item["source"] = "live"
        st.session_state["current_contracts"].extend(contract_metadata)

        if "conversation_log" not in st.session_state:
            st.session_state["conversation_log"] = []

        for line in conversation:
            if "Running negotiation for loop:" in line:
                st.success(line)
            else:
                st.markdown(line)
            st.session_state["conversation_log"].append(line)
            # Try extracting metadata for structured logging
            try:
                if ": " in line:
                    agent, msg = line.split(": ", 1)
                    exchange_details = None
                    if "⇄" in msg or "exchange" in msg.lower():
                        exchange_details = msg
                    append_conversation_line(agent, msg, exchange_details, path=st.session_state.get("conversation_log_path"))
            except Exception as e:
                print("Logging error:", e)

    st.markdown("### 💬 Agent Conversations")
    for line in st.session_state.get("conversation_log", []):
        if "Running negotiation for loop:" in line:
            st.success(line)
        else:
            st.markdown(line)

    # st.markdown("### 📦 Updated Inventories After Negotiation")
    # for agent in all_agents:
    #     st.write(f"**{agent.agent_id}** → {agent.inventory}")
    st.session_state["start_negotiation"] = False  # ✅ reset trigger
    st.session_state["in_progress_contracts"] = []


# ❌ Moved negotiation block to respond to st.session_state["start_negotiation"]
# to prevent loss during rerun (e.g. from sidebar table refresh)

# if st.button("Start Negotiation"):

#     if not is_ganache_running():
#         st.error("⚠️ Ganache is offline. Please start Ganache first.")
#         st.stop()

#     all_agents = st.session_state["agents"]
#     agents_by_id = {agent.agent_id: agent for agent in all_agents}

#     # --- Market configuration (dynamic, no hardcoded resources)
#     all_resources = set()
#     for a in all_agents:
#         all_resources.update(a.inventory.keys())
#         all_resources.update(a.needs.keys())

#     market_insights.configure(all_resources)
#     market_insights.update_market()  # advance one step this run
    
#     if mode == "Run each loop separately":
#         loops = find_trade_loops(all_agents, max_cycle_length=max_loop_len)
#         if not loops:
#             st.error("No valid negotiation loops found.")
#         else:
#             for loop in loops:
#                  # 1) extract the unique IDs in this loop
#                  ids_in_loop = [edge[0] for edge in loop]

#                  # 2) display the full cycle once
#                  cycle_banner = " → ".join(ids_in_loop + [ids_in_loop[0]])
#                  st.success(f"Running negotiation for loop: {cycle_banner}")
 
#                  # 3) run negotiation *only* among those agents
#                  market_insights.update_market()
#                  conversation = run_negotiation_simulation(
#                     loop_ids=ids_in_loop,
#                     agents=all_agents,  # ✅ pass live agents
#                     rounds=n_rounds,
#                     max_cycle_length=max_loop_len,
#                     max_bilateral_rounds=max_bilateral_rounds
#                 )
#                  for line in conversation:
#                      st.markdown(line)
                
#                  # Removed render_agents_table calls here
#                  # if st.session_state.refresh_agents_table:
#                  #    render_agents_table()
#                  #    st.session_state.refresh_agents_table = False

#                  st.markdown("---")
            
#     else:
#         # Run one large negotiation
#         st.success("Running one large negotiation with all agents.")
        
#         market_insights.update_market()
#         conversation = run_negotiation_simulation(
#             loop_ids=[],
#             agents=all_agents,  # ✅ pass live agents
#             rounds=n_rounds,
#             max_cycle_length=max_loop_len,
#             max_bilateral_rounds=max_bilateral_rounds
#         )
#         for line in conversation:
#             st.markdown(line)
        
#         # Removed render_agents_table calls here
#         # if st.session_state.refresh_agents_table:
#         #     render_agents_table()
#         #     st.session_state.refresh_agents_table = False

#     st.markdown("### 📦 Updated Inventories After Negotiation")
#     for agent in all_agents:
#         st.write(f"**{agent.agent_id}** → {agent.inventory}")

# # --- Manual Loop (Debugging Mode) ---
# with st.expander("🛠️ Manually Select Agents"):
#     selected_agents = st.multiselect("Choose agent IDs:", agent_ids)
#     if st.button("▶️ Run Manual Negotiation"):
#         if len(selected_agents) < 2:
#             st.warning("Please select at least 2 agents.")
#         else:
#             st.success(f"Running manual negotiation: {' → '.join(selected_agents)}")
            
#             market_insights.update_market()
#             conversation = run_negotiation_simulation(selected_agents)
#             for line in conversation:
#                 if ": " in line:
#                     agent, msg = line.split(": ", 1)
#                     st.markdown(msg)
#                 else:
#                     st.markdown(line)

# if DEPLOY_LOGS:
#     st.subheader("Contracts deployed in this run")
#     for addr, human in DEPLOY_LOGS.items():
#         st.code(f"{human}   ({addr})") #shows the address as well

metrics = evaluate(total_possible_utility=100.0)

with st.expander("📊 Evaluation Metrics"):
    for k, v in metrics.items():
        st.write(f"**{k}**: {v}")