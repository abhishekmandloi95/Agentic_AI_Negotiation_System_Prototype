# evaluation.py
import numpy as np
from collections import defaultdict

negotiation_logs = []
agent_utilities = defaultdict(float)

def log_conversation(agent_ids, agents_by_id, conversation):
    agreement_success = any("deal accepted" in msg.lower() for msg in conversation)

    loop_log = {
        "agents": agent_ids,
        "agreed": agreement_success,
        "rounds": len(conversation),
        "messages": len(conversation),
        "final_utilities": {
            aid: agents_by_id[aid].get_utility() for aid in agent_ids
        }
    }

    negotiation_logs.append(loop_log)

    for aid in agent_ids:
        agent_utilities[aid] += agents_by_id[aid].get_utility()

def evaluate(total_possible_utility=100.0):
    if not negotiation_logs:
        return {}

    agreements = [log for log in negotiation_logs if log["agreed"]]
    joint_utilities = [sum(log["final_utilities"].values()) for log in agreements]

    def gini(values):
        if not values: return 0
        sorted_vals = sorted(values)
        height, area = 0, 0
        for value in sorted_vals:
            height += value
            area += height - value / 2.
        fair_area = height * len(values) / 2.
        return (fair_area - area) / fair_area if fair_area else 0

    fairness_scores = [1 - gini(list(log["final_utilities"].values())) for log in agreements]
    concession_rates = []
    for log in agreements:
        utils = list(log["final_utilities"].values())
        if utils:
            concession_rates.append(np.mean(utils) / max(utils))

    return {
        "Agreement Rate": round(len(agreements) / len(negotiation_logs), 3),
        "Avg Joint Utility": round(np.mean(joint_utilities), 3) if joint_utilities else 0,
        "Normalized Joint Utility": round(np.mean(joint_utilities) / total_possible_utility, 3) if joint_utilities else 0,
        "Avg Fairness (1-Gini)": round(np.mean(fairness_scores), 3) if fairness_scores else 0,
        "Avg Rounds to Agreement": round(np.mean([log["rounds"] for log in agreements]), 3) if agreements else 0,
        "Avg Messages": round(np.mean([log["messages"] for log in agreements]), 3) if agreements else 0,
        "Message Efficiency": round(len(agreements) / sum(log["messages"] for log in negotiation_logs), 3) if negotiation_logs else 0,
        # "Avg Concession Rate": round(np.mean(concession_rates), 3) if concession_rates else 0,
        "Avg Profit Per Agent": round(np.mean(list(agent_utilities.values())), 3) if agent_utilities else 0
    }