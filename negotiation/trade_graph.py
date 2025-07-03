import networkx as nx

def build_trade_graph(agents):
    graph = nx.DiGraph()

    for agent in agents:
        graph.add_node(agent.agent_id, agent=agent)

    for agent in agents:
        for other_agent in agents:
            if agent.agent_id == other_agent.agent_id:
                continue
            if any(need in other_agent.inventory for need in agent.needs):
                graph.add_edge(agent.agent_id, other_agent.agent_id)

    return graph