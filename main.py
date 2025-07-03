from agents.base_agent import LLMNegotiationAgent
from negotiation.trade_graph import build_trade_graph  
from negotiation.loop_detector import find_trade_loops
from negotiation.protocol import execute_multiagent_chain  
import yaml

def load_all_agents(profile_path="data/profiles.yaml"):
    with open(profile_path) as f:
        profiles = yaml.safe_load(f)["agents"]
    return [LLMNegotiationAgent(agent["id"], profile_path) for agent in profiles]

if __name__ == "__main__":
    agents = load_all_agents()
    agents_by_id = {agent.agent_id: agent for agent in agents}
    graph = build_trade_graph(agents)

 
    loops = find_trade_loops(graph, agents_by_id, max_size=5)

    if loops:
        execute_multiagent_chain(loops[0], agents_by_id)
    else:
        print(" No valid trade.")