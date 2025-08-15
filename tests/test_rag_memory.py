# tests/test_rag_memory.py
import pytest

def test_add_and_retrieve_per_pair():
    from negotiation.rag_memory import NegotiationRAGMemory

    rag = NegotiationRAGMemory()

    # Store per agent-pair
    rag.add_snippet("A", "B", "A offered 30 design_service for 20 ux_research")
    rag.add_snippet("A", "C", "A accepted 40 data_service for 50 product_service")
    rag.add_snippet("B", "C", "B asked for legal_service")

    # Queries are per pair
    res_ab = rag.retrieve("A", "B", "ux research trade", top_k=2)
    text = " ".join(res_ab).lower() if isinstance(res_ab, (list, tuple)) else str(res_ab).lower()
    assert "ux" in text and "research" in text

    res_ac = rag.retrieve("A", "C", "data service", top_k=1)
    assert any("data_service" in s for s in res_ac)