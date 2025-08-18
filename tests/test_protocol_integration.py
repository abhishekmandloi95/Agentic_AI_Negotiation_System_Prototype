import os
import pytest
from negotiation.loop_trader import find_trade_loops
from negotiation.protocol import detect_and_execute_loops
from agents.base_agent import LLMNegotiationAgent


needs_ganache = pytest.mark.skipif(
    os.environ.get("GANACHE_OK") != "1",
    reason="Set GANACHE_OK=1 when local Ganache is running"
)

@needs_ganache
def test_negotiate_pair_minimal(monkeypatch):
    from agents.base_agent import LLMNegotiationAgent, _MARKET
    from negotiation.protocol import negotiate_pair

    # Market config (dynamic)
    _MARKET.configure(['data_service', 'ux_research'])
    _MARKET.update_market()

    # Build two small agents
    A = LLMNegotiationAgent(
        agent_id="A",
        style="neutral",
        inventory={"data_service": 100},
        needs={"ux_research": 20},
    )
    B = LLMNegotiationAgent(
        agent_id="B",
        style="neutral",
        inventory={"ux_research": 30},
        needs={"data_service": 10},
    )

    # Avoid real blockchain deploys
    monkeypatch.setattr('blockchain.contract_manager.deploy_contract', lambda *a, **k: None, raising=False)

    # If your agent’s .chain hits a real LLM, stub it deterministically:
    class DummyChain:
        def invoke(self, input_data):
            return f"{input_data.get('agent_id','A')}: deal accepted"
    A.chain = DummyChain()
    B.chain = DummyChain()

    confirmed_pairs = set()
    contract_metadata = []
    convo = negotiate_pair(A, B, confirmed_pairs, contract_metadata=contract_metadata, max_bilateral_rounds=1)

    assert any("deal accepted" in line.lower() for line in convo)

def test_detect_and_execute_loops_with_missing_confirmations(sample_agent_config):
    agent_definitions = [
        {"agent_id": "A", "inventory": {"x": 5}, "needs": {"y": 5}},
        {"agent_id": "B", "inventory": {"y": 5}, "needs": {"z": 5}},
        {"agent_id": "C", "inventory": {"z": 5}, "needs": {"x": 5}},
    ]
    agents = [LLMNegotiationAgent(**a, style="neutral") for a in agent_definitions]

    # Simulate a case where agents could form a loop but no confirmations given
    result = detect_and_execute_loops(agents, confirmed_pairs=[])
    assert len(result) > 0
    assert isinstance(result[0], tuple)
    assert "verbal confirmations" in result[0][2].lower()