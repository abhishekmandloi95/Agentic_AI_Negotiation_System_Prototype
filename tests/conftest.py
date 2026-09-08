import pytest
from agents.base_agent import LLMNegotiationAgent, RuleDecisionClient
from market.service import MarketInsightsService

@pytest.fixture
def market():
    value = MarketInsightsService(seed=42)
    value.set_use_prophet(False)
    return value

@pytest.fixture
def make_agent(market):
    def make(aid, inventory, needs, **kwargs):
        return LLMNegotiationAgent(aid, "neutral", inventory, needs,
            memory_enabled=kwargs.pop("memory_enabled", False), market=market,
            decision_client=kwargs.pop("decision_client", RuleDecisionClient()), **kwargs)
    return make
