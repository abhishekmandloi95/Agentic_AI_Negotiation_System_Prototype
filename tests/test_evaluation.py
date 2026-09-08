from metrics.evaluation import evaluate, fairness
from negotiation.protocol import run_negotiation_simulation

def test_full_fulfillment_has_positive_utility(make_agent):
    a = make_agent("A", {"x": 2}, {"y": 1})
    b = make_agent("B", {"y": 2}, {"x": 1})
    c, records = run_negotiation_simulation(agents=[a,b], rounds=1)
    assert a.get_utility() == b.get_utility() == 1
    assert c.metrics["normalized_utility_gain"] == 1
    assert c.metrics["messages"] == 2
    assert c.metrics["proposal_rounds"] == 1
    assert evaluate([c.metrics])["Executed trades"] == 1
    assert evaluate() == {}

def test_zero_fulfillment_is_not_perfect_fairness():
    assert fairness([0,0]) == 0
    assert fairness([2,2]) == 1
