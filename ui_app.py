
import json
import os
import streamlit as st
from agents.base_agent import LLMNegotiationAgent, RuleDecisionClient, OllamaDecisionClient, OpenAIDecisionClient
from blockchain.contract_manager import read_record
from market.service import MarketInsightsService
from metrics.evaluation import evaluate
from negotiation.loop_trader import find_trade_loops
from negotiation.protocol import load_agents, run_negotiation_simulation
from utils.history_store import (load_trade_history, create_conversation_log,
                                 append_conversation_line)
from utils.paths import ROOT
from utils.chat_view import render_conversation

st.set_page_config(page_title="Multi-Agent Negotiation", layout="wide")
st.title("Multi-Agent Negotiation Viewer")

with st.sidebar:
    st.header("Simulation settings")
    engine = st.selectbox("Decision engine", ["Ollama / Mistral", "OpenAI / GPT", "Deterministic baseline"])
    model = ""
    api_key = ""
    if engine == "Ollama / Mistral":
        model = st.text_input("Ollama model", value=os.getenv("OLLAMA_MODEL", "mistral"), key="ollama_model").strip()
    elif engine == "OpenAI / GPT":
        model = st.text_input("OpenAI model", value=os.getenv("OPENAI_MODEL", "gpt-5"), key="openai_model").strip()
        api_key = st.text_input("OpenAI API key", type="password", key="openai_api_key",
                                help="Leave blank to use OPENAI_API_KEY from your environment.").strip() or os.getenv("OPENAI_API_KEY", "")
        st.caption("Starting a negotiation sends its context to OpenAI and uses your API account.")
    st.caption("Changing the provider or model resets inventories and memory.")
    memory_enabled = st.checkbox("Use RAG memory", value=False)
    prophet_enabled = st.checkbox("Use Prophet forecasting", value=False)
    auto_accept = st.checkbox("Allow automatic acceptance within 10% of needs", value=False)
    record_on_chain = st.checkbox("Record executed trades on Ganache", value=False)
    seed = st.number_input("Random seed", min_value=0, value=42, step=1)
    n_rounds = st.slider("Bilateral negotiation attempts", 0, 20, 3)
    reply_rounds = st.slider("Proposal rounds per bilateral negotiation", 1, 10, 3)
    max_loop_len = st.slider("Maximum agents per cycle", 2, 9, 4)
    mode = st.radio("Scope", ["All agents", "Each candidate cycle separately"])
    reset = st.button("Reset inventories and memory")
    st.caption("Reset starts a fresh experiment. Continuing preserves current inventories and memory.")
    st.caption("RAG requires optional embedding dependencies. The baseline tests mechanics; it does not measure LLM or RAG quality.")

settings = (engine, model, memory_enabled, seed)
if reset or st.session_state.get("agent_settings") != settings:
    market = MarketInsightsService(seed=seed)
    client = (RuleDecisionClient() if engine == "Deterministic baseline" else
              OpenAIDecisionClient(model=model, api_key=api_key) if engine == "OpenAI / GPT" else
              OllamaDecisionClient(model=model, seed=seed))
    agents = load_agents(
        market=market, memory_enabled=memory_enabled, seed=seed,
        decision_client=client)
    market.configure({r for a in agents for r in set(a.inventory) | set(a.needs)})
    st.session_state.update(agents=agents, market=market, agent_settings=settings,
                            current_contracts=[], conversation_log=[], conversation_events=[], metrics=[], has_run=False)
st.session_state.setdefault("conversation_events", [])
agents = st.session_state.agents
market = st.session_state.market
market.set_use_prophet(prophet_enabled)
for agent in agents:
    agent.auto_accept = auto_accept
    if engine == "OpenAI / GPT":
        agent.chain.api_key = api_key

st.dataframe([{"Agent": a.agent_id, "Style": a.style,
               "Inventory": json.dumps(a.inventory), "Remaining needs": json.dumps(a.needs),
               "Fulfilled units": a.get_utility()} for a in agents], use_container_width=True)

ready = engine == "Deterministic baseline" or bool(model and (engine != "OpenAI / GPT" or api_key))
if not ready:
    st.info("Enter a model name and, for OpenAI, an API key before starting.")
st.session_state.setdefault("has_run", bool(st.session_state.get("metrics")))
run_label = "Continue negotiation" if st.session_state.has_run else "Start negotiation"
if st.button(run_label, key="run_negotiation", disabled=not ready):
    st.session_state.has_run = True
    st.session_state.current_contracts = []
    st.session_state.conversation_log = []
    st.session_state.conversation_events = []
    st.session_state.metrics = []
    log_path = create_conversation_log()
    st.session_state.conversation_log_path = str(log_path)
    market.update_market()
    if mode == "All agents":
        groups = [None]
    else:
        cycles = find_trade_loops(agents, max_loop_len)
        groups = [list(ids) for ids in dict.fromkeys(tuple(sorted(f for f, _, _ in loop)) for loop in cycles)]
    if not groups:
        st.info("No candidate cycles are available with the current inventories.")
    with st.spinner("Negotiating exact proposals…"):
        for index, ids in enumerate(groups):
            try:
                conversation, records = run_negotiation_simulation(
                    ids, agents=agents, rounds=n_rounds, max_cycle_length=max_loop_len,
                    max_bilateral_rounds=reply_rounds, seed=seed + index,
                    record_on_chain=record_on_chain, persist=True)
                
                st.session_state.current_contracts.extend(records)
                st.session_state.metrics.append(conversation.metrics)
                st.session_state.conversation_log.extend(conversation)
                st.session_state.conversation_events.extend(conversation.events)
                for line in conversation:
                    agent, separator, message = line.partition(":")
                    append_conversation_line(agent if separator else "SYSTEM",
                                             message.strip() if separator else line, path=log_path)
            except Exception as exc:
                st.error(f"Simulation or logging failed: {type(exc).__name__}: {exc}")
    st.rerun()

with st.expander("Agent conversations", expanded=True):
    render_conversation(st.session_state.conversation_events)

with st.expander("Technical log", expanded=False):
    for line in st.session_state.conversation_log:
        st.text(line)

with st.expander("Trade records", expanded=True):
    show_history = st.toggle("Include historical trades", value=False)
    try:
        records = load_trade_history() if show_history else st.session_state.current_contracts
    except (ValueError, OSError) as exc:
        st.error(f"History could not be loaded: {exc}")
        records = []
    if not records:
        st.info("No executed trades to show.")
    for index, record in enumerate(records):
        st.markdown(f"**Trade {index + 1} — {record.get('kind', 'legacy')}**")
        if "transfers" in record:
            st.dataframe(record["transfers"], use_container_width=True)
            st.caption(f"Proposal: {record['proposal_id']} | Execution: {record['status']} | Blockchain: {record['blockchain_status']}")
        else:
            st.json(record)
        if record.get("blockchain_error"):
            st.warning(record["blockchain_error"])
        address = record.get("contract_address")
        if address:
            st.code(address)
            if st.button("Verify on-chain record", key=f"verify-{index}-{address}"):
                try:
                    if "transfers" in record:
                        st.json(read_record(address))
                    else:
                        from blockchain.contract_manager import get_w3
                        abi = json.loads((ROOT / "blockchain/TradeAgreement.json").read_text())["abi"]
                        legacy = get_w3().eth.contract(address=address, abi=abi)
                        st.write(legacy.functions.serviceGiven().call())
                except Exception as exc:
                    st.warning(f"On-chain record is not readable: {exc}")

with st.expander("Evaluation metrics", expanded=True):
    st.json(evaluate(st.session_state.metrics))
    st.caption("Metrics cover the most recent button run. Fulfillment measures units of outstanding demand satisfied, not monetary profit.")
