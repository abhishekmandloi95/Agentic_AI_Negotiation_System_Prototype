import networkx as nx

def find_trade_loops(graph, agents_by_id, max_size=4):
    loops = []
    for cycle in nx.simple_cycles(graph):
        if 1 < len(cycle) <= max_size:
            valid = True
            for i in range(len(cycle)):
                curr = agents_by_id[cycle[i]]
                nxt = agents_by_id[cycle[(i + 1) % len(cycle)]]
                match_found = False
                for need, qty in curr.needs.items():
                    if need in nxt.inventory and nxt.inventory[need] >= qty:
                        match_found = True
                        break

                if not match_found:
                    valid = False
                    break

            if valid:
                loops.append(cycle)
    return loops