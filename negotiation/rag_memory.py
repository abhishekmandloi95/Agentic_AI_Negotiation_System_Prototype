from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

class NegotiationRAGMemory:
    def __init__(self, model_name="all-MiniLM-L6-v2"):
        # Load embedding model
        self.embedder = SentenceTransformer(model_name)
        self.dimension = self.embedder.get_sentence_embedding_dimension()

        # Create FAISS index for L2 distance search
        self.index = faiss.IndexFlatL2(self.dimension)

        # Dictionary to store memory per (agentA, agentB) pair
        self.memories = {}  # key: tuple(sorted(agent_ids)), value: (snippets list, FAISS index)

    def _get_pair_key(self, agentA, agentB):
        return tuple(sorted([agentA, agentB]))

    def add_snippet(self, agentA, agentB, text):
        pair_key = self._get_pair_key(agentA, agentB)

        # If this pair is new, initialize FAISS index & snippet list
        if pair_key not in self.memories:
            idx = faiss.IndexFlatL2(self.dimension)
            self.memories[pair_key] = ([], idx)

        snippets, idx = self.memories[pair_key]

        # Store text & embedding
        emb = self.embedder.encode([text])
        idx.add(np.array(emb, dtype=np.float32))
        snippets.append(text)

    def retrieve(self, agentA, agentB, query, top_k=3):
        pair_key = self._get_pair_key(agentA, agentB)

        if pair_key not in self.memories:
            return []

        snippets, idx = self.memories[pair_key]

        if len(snippets) == 0:
            return []

        # Embed query & search
        q_emb = self.embedder.encode([query])
        D, I = idx.search(np.array(q_emb, dtype=np.float32), top_k)
        return [snippets[i] for i in I[0] if i < len(snippets)]