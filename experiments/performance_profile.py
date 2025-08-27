import time
import tracemalloc
from agents.base_agent import LLMNegotiationAgent
from negotiation.protocol import run_negotiation_simulation

def profile_negotiation(memory_enabled=True, rounds=3):
    agents = [
        LLMNegotiationAgent("A", "strategic", {"gold": 5}, {"wood": 3}, memory_enabled=memory_enabled),
        LLMNegotiationAgent("B", "strategic", {"wood": 5}, {"gold": 3}, memory_enabled=memory_enabled),
    ]

    tracemalloc.start()
    start_time = time.perf_counter()
    for _ in range(rounds):
        # ✅ Don't override agents by passing yaml_path
        run_negotiation_simulation(loop_ids=None, agents=agents)
    end_time = time.perf_counter()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return {
        "memory_enabled": memory_enabled,
        "rounds": rounds,
        "latency_seconds": round(end_time - start_time, 4),
        "peak_memory_kb": peak // 1024
    }

if __name__ == "__main__":
    print("Performance with RAG memory:")
    print(profile_negotiation(memory_enabled=True))

    print("\nPerformance without RAG memory:")
    print(profile_negotiation(memory_enabled=False))