from negotiation.protocol import run_negotiation_simulation
from agents.base_agent import LLMNegotiationAgent

def test_negotiation_fails_with_invalid_agents():

    agent_a = LLMNegotiationAgent("A", "cooperative", inventory={}, needs={"gold": 2})
    agent_b = LLMNegotiationAgent("B", "cooperative", inventory={"gold": 2}, needs={})

    agents = [agent_a, agent_b]
    conversation, contract_metadata = run_negotiation_simulation(
        loop_ids=["A", "B"],
        agents=agents,
        rounds=5,
        max_cycle_length=2,
        max_bilateral_rounds=5
    )

    print("Conversation:")
    for msg in conversation:
        print(msg)

    assert len(contract_metadata) == 0, "No contracts should be created"

    
def test_aggressive_agent_gains_more_than_cooperative():

    agent_a = LLMNegotiationAgent("A", "cooperative", inventory={"gold": 3}, needs={"wood": 2})
    agent_b = LLMNegotiationAgent("B", "aggressive", inventory={"wood": 3}, needs={"gold": 2})

    agents = [agent_a, agent_b]
    conversation, contract_metadata = run_negotiation_simulation(
        loop_ids=["A", "B"],
        agents=agents,
        rounds=5,
        max_cycle_length=2,
        max_bilateral_rounds=5
    )

    util_a = agent_a.get_utility()
    util_b = agent_b.get_utility()

    print("Conversation:")
    for msg in conversation:
        print(msg)

    print(f"A's Utility: {util_a}, B's Utility: {util_b}")

    assert len(contract_metadata) >= 0, "Contracts may or may not be created"
    assert util_b >= util_a, "Aggressive agent should gain equal or more utility"