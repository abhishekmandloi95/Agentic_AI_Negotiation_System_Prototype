import numpy as np
import pytest
from negotiation.rag_memory import NegotiationRAGMemory, chunk_conversation

class TinyEmbedder:
    def encode(self, texts, **kwargs):
        return np.array([[text.lower().count("wood"), text.lower().count("gold")] for text in texts], dtype=np.float32)

@pytest.mark.ragheavy
def test_pair_isolation_and_ranking():
    pytest.importorskip("faiss")
    memory = NegotiationRAGMemory(embedder=TinyEmbedder(), max_snippets=2)
    memory.add_snippet("A", "B", "wood wood")
    memory.add_snippet("A", "B", "gold gold")
    memory.add_snippet("A", "C", "gold private")
    assert memory.retrieve("B", "A", "wood wood", 1) == ["wood wood"]
    assert memory.retrieve("A", "D", "wood") == []
    assert memory.retrieve("A", "B", "gold", 0) == []
    memory.add_snippet("A", "B", "new wood")
    assert len(memory.memories[("A", "B")][0]) == 2

def test_empty_memory_does_not_load_model():
    memory = NegotiationRAGMemory()
    assert memory.retrieve("A", "B", "query") == []
    assert memory._embedder is None

@pytest.mark.parametrize("size, overlap", [(0,0), (10,10), (10,-1)])
def test_invalid_chunking(size, overlap):
    with pytest.raises(ValueError):
        chunk_conversation("example", size, overlap)

def test_chunks_overlap():
    chunks = chunk_conversation("abcdefghij" * 10, 20, 5)
    assert all(a[-5:] == b[:5] for a,b in zip(chunks,chunks[1:]))
