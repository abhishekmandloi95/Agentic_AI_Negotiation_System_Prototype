
import argparse
import json
import platform
from pathlib import Path
from datetime import datetime
from statistics import mean, stdev
from time import perf_counter
import tracemalloc
from agents.base_agent import LLMNegotiationAgent, RuleDecisionClient, OllamaDecisionClient
from market.service import MarketInsightsService
from negotiation.protocol import run_negotiation_simulation
from utils.paths import ROOT

def scenario(seed, memory_enabled=False, prophet_enabled=False, engine="baseline", memories=None):
    market = MarketInsightsService(seed=seed, as_of=datetime(2025, 1, 1))
    market.configure(["gold", "wood"])
    market.set_use_prophet(prophet_enabled)
    agents = []
    for aid, inventory, needs in [
        ("A", {"gold": 10}, {"wood": 8}),
        ("B", {"wood": 10}, {"gold": 8}),
    ]:
        client = RuleDecisionClient() if engine == "baseline" else OllamaDecisionClient(seed=seed)
        agents.append(LLMNegotiationAgent(aid, "strategic", inventory, needs,
            memory_enabled=memory_enabled, memory=(memories or {}).get(aid),
            decision_client=client, market=market, seed=seed))
    return agents

def run_benchmark(runs=5, memory_enabled=False, prophet_enabled=False, engine="baseline", base_seed=42):
    if runs < 1:
        raise ValueError("runs must be positive")
    if engine not in ("baseline", "ollama"):
        raise ValueError("Unknown decision engine")
    results = []
    for index in range(runs):
        seed = base_seed + index
        warmup_start = perf_counter()
        warm_agents = scenario(seed, memory_enabled, prophet_enabled, engine)
        warm_conversation, _ = run_negotiation_simulation(agents=warm_agents, seed=seed)
        warmup_seconds = perf_counter() - warmup_start
        memories = {a.agent_id: a.memory for a in warm_agents}
        agents = scenario(seed, memory_enabled, prophet_enabled, engine, memories)
        
        agents[0].market.context(["gold", "wood"])
        tracemalloc.start()
        start = perf_counter()
        conversation, records = run_negotiation_simulation(agents=agents, seed=seed)
        elapsed = perf_counter() - start
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        results.append({
            "seed": seed, "memory_enabled": memory_enabled, "prophet_enabled": prophet_enabled,
            "engine": engine, "warmup_seconds": warmup_seconds,
            "warmup_decision_errors": warm_conversation.metrics["decision_errors"],
            "latency_seconds": elapsed, "peak_python_allocations_bytes": peak,
            **conversation.metrics,
        })
    keys = ("executed_trades", "joint_utility_gain", "agreement_rate", "latency_seconds")
    summary = {key: {"mean": mean(r[key] for r in results),
                     "stdev": stdev(r[key] for r in results) if runs > 1 else 0.0}
               for key in keys}
    return {"python": platform.python_version(), "base_seed": base_seed, "runs": results,
            "summary": summary,
            "interpretation": "Baseline tests mechanics only. LLM outputs are not guaranteed reproducible across model/runtime versions. Feature benefit is an empirical question."}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--engine", choices=["baseline", "ollama"], default="baseline")
    parser.add_argument("--memory", action="store_true")
    parser.add_argument("--prophet", action="store_true")
    parser.add_argument("--output", default="experiments/results/benchmark.json")
    args = parser.parse_args()
    result = run_benchmark(args.runs, args.memory, args.prophet, args.engine, args.seed)
    target = Path(args.output)
    if not target.is_absolute():
        target = ROOT / target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2))
    print(json.dumps(result["summary"], indent=2))
    print(f"Saved {target}")

if __name__ == "__main__":
    main()
