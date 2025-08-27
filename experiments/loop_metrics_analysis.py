import matplotlib.pyplot as plt
from agents.base_agent import LLMNegotiationAgent
from negotiation.protocol import run_negotiation_simulation
from market.service import service as market_insights

def run_simulation(memory_enabled=True, prophet_enabled=True, runs=10):
    results = []
    market_insights.set_use_prophet(prophet_enabled)

    for _ in range(runs):
        # ✅ Define static agents inline (bypasses YAML completely)
        agents = [
            LLMNegotiationAgent("A", "strategic", {"gold": 3}, {"wood": 2}, memory_enabled=memory_enabled),
            LLMNegotiationAgent("B", "strategic", {"wood": 3}, {"gold": 2}, memory_enabled=memory_enabled)
        ]
        # ✅ Don't pass `yaml_path` — this will override your agents!
        trades = run_negotiation_simulation(loop_ids=None, agents=agents)
        results.append(len(trades))

    return results

if __name__ == "__main__":
    rag_on = run_simulation(memory_enabled=True, prophet_enabled=False)
    rag_off = run_simulation(memory_enabled=False, prophet_enabled=False)

    plt.boxplot([rag_on, rag_off], labels=["RAG On", "RAG Off"])
    plt.title("Trade Loop Count with vs without RAG")
    plt.ylabel("Successful Trades per Iteration")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("experiments/figures/rag_loop_comparison.png")
    plt.show()