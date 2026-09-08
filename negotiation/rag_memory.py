"""Pair-specific FAISS memory with lazy, process-shared sentence embeddings."""
from functools import lru_cache
from threading import RLock
import numpy as np

_MODEL_LOCK = RLock()

@lru_cache(maxsize=2)
def _load_embedder(model_name):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(model_name)

class NegotiationRAGMemory:
    def __init__(self, model_name="all-MiniLM-L6-v2", *, embedder=None, max_snippets=200):
        if max_snippets < 1:
            raise ValueError("max_snippets must be positive")
        self.model_name, self._embedder = model_name, embedder
        self.max_snippets = max_snippets
        self.memories = {}
        self._lock = RLock()

    @property
    def embedder(self):
        with _MODEL_LOCK:
            if self._embedder is None:
                self._embedder = _load_embedder(self.model_name)
            return self._embedder

    def _encode(self, texts):
        with _MODEL_LOCK:
            return np.ascontiguousarray(self.embedder.encode(texts, convert_to_numpy=True), dtype=np.float32)

    def add_snippet(self, agentA, agentB, text):
        import faiss
        key = tuple(sorted((agentA, agentB)))
        with self._lock:
            snippets = list(self.memories.get(key, ([], None))[0])
            if text in snippets:
                return
            snippets = (snippets + [text])[-self.max_snippets:]
            embeddings = self._encode(snippets)
            index = faiss.IndexFlatL2(embeddings.shape[1])
            index.add(embeddings)
            self.memories[key] = snippets, index

    def retrieve(self, agentA, agentB, query, top_k=3):
        if top_k <= 0:
            return []
        with self._lock:
            snippets, index = self.memories.get(tuple(sorted((agentA, agentB))), ([], None))
            if not snippets:
                return []
            _, ids = index.search(self._encode([query]), min(top_k, len(snippets)))
            return [snippets[i] for i in ids[0] if 0 <= i < len(snippets)]

def chunk_conversation(text, chunk_size=100, overlap=20):
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("Require chunk_size > 0 and 0 <= overlap < chunk_size.")
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size - overlap)]
