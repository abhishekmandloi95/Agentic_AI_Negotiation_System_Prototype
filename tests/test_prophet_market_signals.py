from negotiation.protocol import run_negotiation_simulation
from agents.base_agent import LLMNegotiationAgent
from market.service import service as market_insights

def test_prophet_improves_trade_throughput():

    # Agent setup
    agents = [
        LLMNegotiationAgent("A", "strategic", {"gold": 3}, {"wood": 2}),
        LLMNegotiationAgent("B", "strategic", {"wood": 3}, {"gold": 2}),
    ]

    # Run with Prophet
    market_insights.set_use_prophet(True)
    _, contracts_with_prophet = run_negotiation_simulation(
        loop_ids=["A", "B"],
        agents=agents,
        rounds=5,
        max_cycle_length=2,
        max_bilateral_rounds=5
    )

    # Reset agents and rerun without Prophet
    agents = [
        LLMNegotiationAgent("A", "strategic", {"gold": 3}, {"wood": 2}),
        LLMNegotiationAgent("B", "strategic", {"wood": 3}, {"gold": 2}),
    ]
    market_insights.set_use_prophet(False)
    _, contracts_without_prophet = run_negotiation_simulation(
        loop_ids=["A", "B"],
        agents=agents,
        rounds=5,
        max_cycle_length=2,
        max_bilateral_rounds=5
    )

    assert len(contracts_with_prophet) >= len(contracts_without_prophet)