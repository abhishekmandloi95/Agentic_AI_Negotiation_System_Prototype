from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

class NegotiationRAGMemory:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        # Load embedding model
        self.embedder = SentenceTransformer(model_name)
        self.dimension = int(self.embedder.get_sentence_embedding_dimension())

        # Per-pair memories: key -> (snippets: list[str], index: faiss.IndexFlatL2)
        self.memories: dict[tuple[str, str], tuple[list[str], faiss.Index]] = {}

    def _get_pair_key(self, agentA: str, agentB: str) -> tuple[str, str]:
        return tuple(sorted([agentA, agentB]))

    def add_snippet(self, agentA: str, agentB: str, text: str) -> None:
        pair_key = self._get_pair_key(agentA, agentB)

        # Initialize per-pair state if new
        if pair_key not in self.memories:
            idx = faiss.IndexFlatL2(self.dimension)
            self.memories[pair_key] = ([], idx)

        snippets, idx = self.memories[pair_key]

        # Encode -> float32, contiguous (what FAISS expects)
        emb = self.embedder.encode([text], convert_to_numpy=True)
        emb = np.ascontiguousarray(emb.astype(np.float32))  # shape (1, d)

        idx.add(emb)
        snippets.append(text)

    def retrieve(self, agentA: str, agentB: str, query: str, top_k: int = 3) -> list[str]:
        pair_key = self._get_pair_key(agentA, agentB)

        if pair_key not in self.memories:
            return []

        snippets, idx = self.memories[pair_key]
        if not snippets:
            return []

        # Clamp k to available items to avoid -1s (still keep robust filter below)
        k = min(top_k, len(snippets))

        q_emb = self.embedder.encode([query], convert_to_numpy=True)
        q_emb = np.ascontiguousarray(q_emb.astype(np.float32))  # shape (1, d)

        D, I = idx.search(q_emb, k)  # I shape (1, k)
        return [snippets[i] for i in I[0] if i != -1 and 0 <= i < len(snippets)]
