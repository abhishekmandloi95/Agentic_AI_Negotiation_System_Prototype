import random
from collections import Counter
import pytest
from negotiation.protocol import run_negotiation_simulation
from negotiation.loop_trader import find_trade_loops, detect_and_execute_loops

def cycle(make_agent):
    return [make_agent("A", {"x": 5}, {"z": 5}), make_agent("B", {"y": 5}, {"x": 5}),
            make_agent("C", {"z": 5}, {"y": 5})]

def test_directed_cycle_preserves_real_edges(make_agent):
    agents = cycle(make_agent)
    assert find_trade_loops(agents) == [[("A", "B", "x"), ("B", "C", "y"), ("C", "A", "z")]]
    assert find_trade_loops(agents, 2) == []

def test_bilateral_confirmations_do_not_authorize_cycle(make_agent):
    agents = cycle(make_agent)
    result = detect_and_execute_loops(agents, confirmed_pairs={("A","B"), ("B","C"), ("A","C")})
    assert result[0][1] == 0
    assert all(a.get_utility() == 0 for a in agents)

def test_cycle_records_all_transfers_and_full_utility(make_agent):
    agents = cycle(make_agent)
    c, records = run_negotiation_simulation(agents=agents, rounds=0)
    assert len(records) == 1 and len(records[0]["transfers"]) == 3
    assert records[0]["kind"] == "loop"
    assert all(a.get_utility() == 5 for a in agents)
    assert c.metrics["normalized_utility_gain"] == 1
    c2, records2 = run_negotiation_simulation(agents=agents)
    assert records2 == [] and c2.metrics["joint_utility_gain"] == 0

def test_blockchain_failure_does_not_undo_or_repeat_trade(make_agent):
    def fail(record): raise ConnectionError("offline")
    agents = cycle(make_agent)
    c, records = run_negotiation_simulation(agents=agents, rounds=0, record_on_chain=True, recorder=fail)
    assert records[0]["status"] == "executed"
    assert records[0]["blockchain_status"] == "failed"
    assert c.metrics["blockchain_failures"] == 1
    assert all(len(a.executed_proposals) == 1 for a in agents)

@pytest.mark.parametrize("seed", range(10))
def test_random_scenarios_conserve_resources(make_agent, seed):
    rng = random.Random(seed)
    agents = [make_agent(str(i), {r: rng.randrange(7) for r in "xyz"},
                         {r: rng.randrange(7) for r in "xyz"}) for i in range(4)]
    def total():
        out = Counter()
        for a in agents: out.update(a.inventory)
        return out
    before = total()
    c, records = run_negotiation_simulation(agents=agents, max_cycle_length=4, seed=seed)
    assert total() == before
    assert all(q >= 0 for a in agents for q in a.inventory.values())
    assert all(q >= 0 for a in agents for q in a.needs.values())
    assert 0 <= c.metrics["normalized_utility_gain"] <= 1
    assert all(set(r["approvals"].values()) == {r["proposal_id"]} for r in records)
