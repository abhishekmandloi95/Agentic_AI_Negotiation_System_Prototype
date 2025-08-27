from market.service import service as market_insights
from negotiation.protocol import run_negotiation_simulation
from agents.base_agent import LLMNegotiationAgent
from negotiation.loop_trader import detect_and_execute_loops
from agents.base_agent import LLMNegotiationAgent
from negotiation.loop_trader import find_trade_loops
from agents.base_agent import LLMNegotiationAgent

def test_loop_fails_with_zero_transferable_quantity():    

    a1 = LLMNegotiationAgent("A", "neutral", {"gold": 0}, {"wood": 1})
    a2 = LLMNegotiationAgent("B", "neutral", {"wood": 0}, {"gold": 1})

    loops = detect_and_execute_loops([a1, a2], max_cycle_length=2)

    assert all("invalid" in reason for _, _, reason in loops), \
        "Loop should fail due to zero transferable quantity"


def test_all_agents_want_same_resource():
   

    agents = [
        LLMNegotiationAgent("A", "neutral", {"wood": 2}, {"gold": 1}),
        LLMNegotiationAgent("B", "neutral", {"stone": 2}, {"gold": 1}),
        LLMNegotiationAgent("C", "neutral", {"silver": 2}, {"gold": 1})
    ]

    loops = find_trade_loops(agents, max_cycle_length=3)

    assert len(loops) == 0, \
        "No loops should form when all agents want same resource and none have it"


def test_market_signal_missing_behavior():

    # Simulate empty market state
    market_insights._history = []

    a1 = LLMNegotiationAgent("A", "neutral", {"gold": 2}, {"wood": 1})
    a2 = LLMNegotiationAgent("B", "neutral", {"wood": 2}, {"gold": 1})

    conversation, contract_metadata = run_negotiation_simulation(
        loop_ids=["A", "B"],
        agents=[a1, a2],
        rounds=3,
        max_cycle_length=2,
        max_bilateral_rounds=3
    )

    assert isinstance(conversation, list), "Conversation should be a list even with no market data"
    assert isinstance(contract_metadata, list), "Contracts should still be created or attempted"