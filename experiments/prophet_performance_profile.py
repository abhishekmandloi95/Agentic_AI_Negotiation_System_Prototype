import time
import tracemalloc
from agents.base_agent import LLMNegotiationAgent
from negotiation.protocol import run_negotiation_simulation
from market.service import service as market_insights

def run_simulation(use_prophet: bool):
    market_insights.set_use_prophet(use_prophet)

    agents = [
        LLMNegotiationAgent("A", "strategic", {"gold": 3}, {"wood": 2}),
        LLMNegotiationAgent("B", "strategic", {"wood": 3}, {"gold": 2}),
    ]

    start_time = time.time()
    tracemalloc.start()

    # ✅ Removed yaml_path to avoid overwriting hardcoded agents
    run_negotiation_simulation(loop_ids=None, agents=agents)

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    end_time = time.time()

    latency = end_time - start_time
    memory_usage_kb = peak / 1024
    return latency, memory_usage_kb

if __name__ == "__main__":
    for use_prophet in [True, False]:
        label = "With Prophet" if use_prophet else "Without Prophet"
        latency, memory_kb = run_simulation(use_prophet)
        print(f"{label} — Latency: {latency:.2f}s, Peak Memory: {memory_kb:.2f} KB")