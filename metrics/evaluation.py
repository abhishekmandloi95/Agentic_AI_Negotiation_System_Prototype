
from statistics import mean

def fairness(values):
    values = sorted(values)
    total = sum(values)
    if not total:
        return 0.0  
    n = len(values)
    gini = sum((2 * i - n - 1) * x for i, x in enumerate(values, 1)) / (n * total)
    return 1 - gini

def summarize_run(agents, before, remaining_before, events, records):
    gains = {a.agent_id: a.get_utility() - before[a.agent_id] for a in agents}
    negotiations = [e for e in events if e["kind"] == "negotiation"]
    agreements = [e for e in negotiations if e["agreed"]]
    messages = sum(e["kind"] == "decision" for e in events)
    return {
        "negotiations": len(negotiations),
        "agreements": len(agreements),
        "executed_trades": len(records),
        "bilateral_trades": sum(r["kind"] == "bilateral" for r in records),
        "loop_trades": sum(r["kind"] == "loop" for r in records),
        "transferred_units": sum(t["quantity"] for r in records for t in r["transfers"]),
        "agreement_rate": len(agreements) / len(negotiations) if negotiations else 0.0,
        "joint_utility_gain": sum(gains.values()),
        "normalized_utility_gain": sum(gains.values()) / remaining_before if remaining_before else 0.0,
        "fairness": fairness(list(gains.values())),
        "proposal_rounds": sum(e["rounds"] for e in negotiations),
        "avg_rounds_to_agreement": mean(e["rounds"] for e in agreements) if agreements else 0.0,
        "messages": messages,
        "message_efficiency": len(records) / messages if messages else 0.0,
        "decision_errors": sum(e["kind"] == "error" for e in events),
        "memory_errors": sum(e["kind"] == "memory_error" for e in events),
        "utility_gains": gains,
        "blockchain_failures": sum(r["blockchain_status"] == "failed" for r in records),
    }

def evaluate(logs=None, total_possible_utility=None):
    
    logs = list(logs or [])
    if not logs:
        return {}
    return {
        "Runs": len(logs),
        "Executed trades": sum(r["executed_trades"] for r in logs),
        "Mean run agreement rate": round(mean(r["agreement_rate"] for r in logs), 3),
        "Average fulfilled units per run": round(mean(r["joint_utility_gain"] for r in logs), 3),
        "Average normalized fulfillment": round(mean(r["normalized_utility_gain"] for r in logs), 3),
        "Average fairness (1-Gini)": round(mean(r["fairness"] for r in logs), 3),
        "Decision messages": sum(r["messages"] for r in logs),
        "Proposal rounds": sum(r["proposal_rounds"] for r in logs),
        "Decision errors": sum(r["decision_errors"] for r in logs),
        "Memory errors": sum(r["memory_errors"] for r in logs),
        "Blockchain recording failures": sum(r["blockchain_failures"] for r in logs),
    }
