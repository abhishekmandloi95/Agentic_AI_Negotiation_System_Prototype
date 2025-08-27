from negotiation.protocol import run_negotiation_simulation
from agents.base_agent import LLMNegotiationAgent

def test_rag_enables_better_negotiation():

    # Agent setup
    agents_with_rag = [
        LLMNegotiationAgent("A", "strategic", {"gold": 3}, {"wood": 2}, memory_enabled=True),
        LLMNegotiationAgent("B", "strategic", {"wood": 3}, {"gold": 2}, memory_enabled=True),
    ]
    agents_without_rag = [
        LLMNegotiationAgent("A", "strategic", {"gold": 3}, {"wood": 2}, memory_enabled=False),
        LLMNegotiationAgent("B", "strategic", {"wood": 3}, {"gold": 2}, memory_enabled=False),
    ]

    # Run with RAG
    _, contracts_rag = run_negotiation_simulation(
        loop_ids=["A", "B"],
        agents=agents_with_rag,
        rounds=5,
        max_cycle_length=2,
        max_bilateral_rounds=5
    )

    # Run without RAG
    _, contracts_no_rag = run_negotiation_simulation(
        loop_ids=["A", "B"],
        agents=agents_without_rag,
        rounds=5,
        max_cycle_length=2,
        max_bilateral_rounds=5
    )

    # Assert: RAG does not reduce number of contracts
    assert len(contracts_rag) >= len(contracts_no_rag)