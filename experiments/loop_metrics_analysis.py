"""RAG comparison; raw paired runs are saved alongside the chart."""
import json
from experiments.benchmark import run_benchmark
from utils.paths import ROOT

def run_simulation(memory_enabled=True, prophet_enabled=True, runs=10, engine="ollama"):
    result = run_benchmark(runs, memory_enabled, prophet_enabled, engine)
    return [row["executed_trades"] for row in result["runs"]]

if __name__ == "__main__":
    import matplotlib.pyplot as plt
    results = {label: run_benchmark(memory_enabled=enabled, engine="ollama")
               for label, enabled in [("RAG On", True), ("RAG Off", False)]}
    target = ROOT / "experiments/results"
    target.mkdir(parents=True, exist_ok=True)
    (target / "rag_comparison.json").write_text(json.dumps(results, indent=2))
    plt.boxplot([[row["executed_trades"] for row in result["runs"]] for result in results.values()],
                tick_labels=list(results))
    plt.title("Executed trades with and without RAG")
    plt.ylabel("Executed agreements per measured run")
    plt.tight_layout()
    plt.savefig(target / "rag_comparison.png")
