from agents.base_agent import OllamaDecisionClient
from negotiation.trades import Proposal, Transfer

def test_ollama_request_is_structured_and_bounded(monkeypatch):
    import requests
    seen = {}
    class Response:
        def raise_for_status(self): pass
        def json(self): return {"response": '{"proposal_id":"p","action":"reject","reason":"no"}'}
    def post(url, **kwargs):
        seen.update(url=url, **kwargs)
        return Response()
    monkeypatch.setattr(requests, "post", post)
    client = OllamaDecisionClient(model="test", seed=9)
    assert "reject" in client.invoke({"prompt": "check"})
    assert seen["json"]["format"]["required"] == ["proposal_id", "action", "reason"]
    assert seen["json"]["options"]["seed"] == 9
    assert seen["timeout"] == (5, 120)

def test_invalid_decision_retries_once(make_agent):
    class Client:
        count = 0
        def invoke(self, inputs):
            self.count += 1
            if self.count == 1: return "no deal accepted"
            return {"proposal_id": inputs["proposal"]["proposal_id"], "action": "accept", "reason": "ok"}
    client = Client()
    a = make_agent("A", {"x": 2}, {"y": 2}, decision_client=client)
    p = Proposal.create([Transfer("A","B","x",1), Transfer("B","A","y",1)])
    assert a.decide(p)["action"] == "accept"
    assert client.count == 2
