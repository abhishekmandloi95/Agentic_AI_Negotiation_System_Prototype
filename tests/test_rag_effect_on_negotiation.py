from agents.base_agent import RuleDecisionClient
from negotiation.protocol import negotiate_pair

class Memory:
    def __init__(self):
        self.rows = []
    def retrieve(self, *args):
        return ["Previously accepted 2 wood for 2 gold"]
    def add_snippet(self, *args):
        self.rows.append(args)

class Capture(RuleDecisionClient):
    def __init__(self): self.inputs = []
    def invoke(self, inputs):
        self.inputs.append(inputs)
        return super().invoke(inputs)

def test_rag_reaches_prompt_and_stores_outcome(make_agent):
    memory, client = Memory(), Capture()
    a = make_agent("A", {"gold": 4}, {"wood": 4}, memory_enabled=True, memory=memory, decision_client=client)
    b = make_agent("B", {"wood": 4}, {"gold": 4})
    records = []
    negotiate_pair(a, b, set(), 1, records)
    assert "Previously accepted" in client.inputs[0]["prompt"]
    assert len(memory.rows) == 1 and '"outcome": "executed"' in memory.rows[0][2]
    assert len(records) == 1

def test_disabled_memory_is_not_used(make_agent):
    memory, client = Memory(), Capture()
    a = make_agent("A", {"gold": 4}, {"wood": 4}, memory=memory, decision_client=client)
    b = make_agent("B", {"wood": 4}, {"gold": 4})
    negotiate_pair(a, b, set(), 1, [])
    assert client.inputs[0]["retrieved_memory"] == [] and memory.rows == []
