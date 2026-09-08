from experiments.benchmark import run_benchmark

def run_simulation(use_prophet, engine="baseline"):
    result = run_benchmark(runs=5, prophet_enabled=use_prophet, engine=engine)
    return result

if __name__ == "__main__":
    import json
    for enabled in (True, False):
        print(json.dumps(run_simulation(enabled), indent=2))
