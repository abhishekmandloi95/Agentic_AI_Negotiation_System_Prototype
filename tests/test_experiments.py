from experiments.benchmark import run_benchmark

def test_baseline_repeats_outcomes_with_same_seed():
    a = run_benchmark(runs=2)
    b = run_benchmark(runs=2)
    for left, right in zip(a["runs"], b["runs"]):
        assert left["executed_trades"] == right["executed_trades"]
        assert left["joint_utility_gain"] == right["joint_utility_gain"]
        assert left["decision_errors"] == 0
        assert left["memory_errors"] == 0
        assert left["latency_seconds"] >= 0
