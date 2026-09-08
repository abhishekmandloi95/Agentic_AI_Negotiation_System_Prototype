import os
import pytest

@pytest.mark.embeddings
def test_real_embedding_memory():
    if os.getenv("EMBEDDINGS_OK") != "1":
        pytest.skip("Set EMBEDDINGS_OK=1 to load/download the embedding model.")
    from negotiation.rag_memory import NegotiationRAGMemory
    a, b = NegotiationRAGMemory(), NegotiationRAGMemory()
    assert a.embedder is b.embedder
    a.add_snippet("A", "B", "Exchanged wood for gold.")
    assert a.retrieve("B", "A", "wood") == ["Exchanged wood for gold."]

@pytest.mark.llm
def test_live_ollama_decision(make_agent):
    if os.getenv("OLLAMA_OK") != "1":
        pytest.skip("Set OLLAMA_OK=1 to call the local model.")
    from agents.base_agent import OllamaDecisionClient
    from negotiation.trades import Proposal, Transfer
    a = make_agent("A", {"gold": 2}, {"wood": 2}, decision_client=OllamaDecisionClient())
    p = Proposal.create([Transfer("A", "B", "gold", 1), Transfer("B", "A", "wood", 1)])
    decision = a.decide(p)
    assert decision["proposal_id"] == p.proposal_id
    assert decision["action"] in ("accept", "reject")
