
from experiments.benchmark import run_benchmark

def profile_negotiation(memory_enabled=True, rounds=3, engine="ollama"):
    return run_benchmark(runs=rounds, memory_enabled=memory_enabled, engine=engine)

if __name__ == "__main__":
    import json
    for enabled in (True, False):
        print(json.dumps(profile_negotiation(memory_enabled=enabled), indent=2))
