import os
import pytest

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
    convo = negotiate_pair(A, B, confirmed_pairs, max_bilateral_rounds=1)

    assert any("deal accepted" in line.lower() for line in convo)