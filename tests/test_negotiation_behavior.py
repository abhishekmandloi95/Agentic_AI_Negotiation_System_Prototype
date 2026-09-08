import json
import pytest
from negotiation.protocol import negotiate_pair, parse_decision, clean_text
from negotiation.trades import Proposal, Transfer, execute_proposal

class Reject:
    def invoke(self, inputs):
        return {"proposal_id": inputs["proposal"]["proposal_id"], "action": "reject", "reason": "No"}

def test_executed_terms_equal_approved_terms(make_agent):
    a = make_agent("A", {"gold": 10}, {"wood": 6})
    b = make_agent("B", {"wood": 8}, {"gold": 5})
    pairs, records = set(), []
    c = negotiate_pair(a, b, pairs, 2, records)
    assert len(records) == 1
    record = records[0]
    approved = [e["proposal"] for e in c.events if e["kind"] == "proposal"][0]
    assert record["transfers"] == approved["transfers"]
    assert set(record["approvals"]) == {"A", "B"}
    assert sum(a.inventory.values()) + sum(b.inventory.values()) == 18
    assert a.get_utility() == 4 and b.get_utility() == 5

def test_rejection_does_not_execute(make_agent):
    a = make_agent("A", {"gold": 4}, {"wood": 4})
    b = make_agent("B", {"wood": 4}, {"gold": 4}, decision_client=Reject())
    records = []
    negotiate_pair(a, b, set(), 2, records)
    assert records == [] and a.get_utility() == 0
    assert a.inventory == {"gold": 4}

@pytest.mark.parametrize("raw", ['no deal accepted', 'deal accepted',
    '{"proposal_id":"wrong","action":"accept","reason":"yes"}',
    '{"proposal_id":"p","action":"accept","reason":"yes","offer":{}}'])
def test_prose_and_wrong_ids_are_not_consent(raw):
    with pytest.raises(ValueError):
        parse_decision(raw, "p")

def test_exact_prefix_removal():
    assert clean_text("A: Accept", "A") == "Accept"
    assert clean_text("Accept", "A") == "Accept"
    assert clean_text("Given inventory", "A") == "Given inventory"

def test_tolerance_requires_other_party_consent(make_agent):
    a = make_agent("A", {"gold": 4}, {"wood": 2}, auto_accept=True)
    b = make_agent("B", {"wood": 4}, {"gold": 2}, decision_client=Reject())
    records = []
    negotiate_pair(a, b, set(), 1, records)
    assert not records
    b.auto_accept = True
    negotiate_pair(a, b, set(), 1, records)
    assert len(records) == 1

def test_replay_and_stale_approvals_fail(make_agent):
    a = make_agent("A", {"gold": 4}, {"wood": 4})
    b = make_agent("B", {"wood": 4}, {"gold": 4})
    p = Proposal.create([Transfer("A", "B", "gold", 1), Transfer("B", "A", "wood", 1)])
    with pytest.raises(ValueError, match="exact"):
        execute_proposal(p, {"A": a, "B": b}, {"A": p.proposal_id, "B": "old"})
    approvals = {aid: p.proposal_id for aid in ("A", "B")}
    execute_proposal(p, {"A": a, "B": b}, approvals)
    with pytest.raises(ValueError, match="already"):
        execute_proposal(p, {"A": a, "B": b}, approvals)
