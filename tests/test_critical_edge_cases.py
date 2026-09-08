from copy import deepcopy
import pytest
from negotiation.trades import Proposal, Transfer, execute_proposal
from negotiation.loop_trader import find_trade_loops, loop_proposal
from negotiation.protocol import run_negotiation_simulation

@pytest.mark.parametrize("quantity", [-1, 0, 1.5, True, 999])
def test_invalid_quantity_cannot_mutate_either_party(make_agent, quantity):
    a = make_agent("A", {"gold": 5}, {"wood": 5})
    b = make_agent("B", {"wood": 5}, {"gold": 5})
    before = deepcopy((a.inventory, a.needs, b.inventory, b.needs))
    proposal = Proposal.create([Transfer("A", "B", "gold", quantity), Transfer("B", "A", "wood", 1)])
    with pytest.raises(ValueError):
        execute_proposal(proposal, {"A": a, "B": b}, {x: proposal.proposal_id for x in ("A", "B")})
    assert (a.inventory, a.needs, b.inventory, b.needs) == before
    assert not a.history and not b.history

def test_aggregate_outgoing_prevents_double_spend(make_agent):
    agents = {a.agent_id: a for a in [make_agent("A", {"x": 5}, {"y": 4}),
        make_agent("B", {"y": 2}, {"x": 4}), make_agent("C", {"y": 2}, {"x": 4})]}
    p = Proposal.create([Transfer("A", "B", "x", 4), Transfer("A", "C", "x", 4),
                         Transfer("B", "A", "y", 2), Transfer("C", "A", "y", 2)], "loop")
    with pytest.raises(ValueError, match="insufficient"):
        execute_proposal(p, agents, {aid: p.proposal_id for aid in agents})
    assert agents["A"].inventory["x"] == 5

def test_duplicate_agents_and_empty_simulation(make_agent):
    a = make_agent("A", {}, {})
    with pytest.raises(ValueError, match="unique"):
        run_negotiation_simulation(agents=[a, a])
    c, records = run_negotiation_simulation(agents=[])
    assert records == [] and c.metrics["agreement_rate"] == 0

def test_no_supply_has_no_loops(make_agent):
    agents = [make_agent("A", {"wood": 0}, {"gold": 2}), make_agent("B", {"gold": 0}, {"wood": 2})]
    assert find_trade_loops(agents) == []

def test_needs_and_inventory_inputs_are_copied_and_validated(make_agent):
    inventory, needs = {"x": 3}, {"y": 2}
    a = make_agent("A", inventory, needs)
    a.inventory["x"] = 1
    assert inventory["x"] == 3 and needs["y"] == 2
    with pytest.raises(ValueError):
        make_agent("B", {"x": -1}, {})
