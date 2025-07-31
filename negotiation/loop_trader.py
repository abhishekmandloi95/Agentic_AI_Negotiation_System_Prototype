from collections import defaultdict

def build_trade_graph(agents):
    graph = defaultdict(list)
    id_map = {a.agent_id: a for a in agents}

    for a in agents:
        for b in agents:
            if a.agent_id == b.agent_id:
                continue
            for res, qty in a.inventory.items():
                if qty > 0 and b.needs.get(res, 0) > 0:
                    graph[a.agent_id].append((b.agent_id, res))
    return graph, id_map

def _dfs_cycles(graph, start, current, visited, path, loops, max_len=None):
    if max_len and len(path) > max_len:
        return

    for (nbr, res) in graph[current]:
        if nbr == start and len(path) >= 1:
            # Found a cycle: record path + this edge
            loops.append(path + [(current, nbr, res)])
        elif nbr not in visited:
            _dfs_cycles(
                graph, start, nbr,
                visited | {nbr},
                path + [(current, nbr, res)],
                loops, max_len
            )

def find_trade_loops(agents, max_cycle_length=None):

    graph, id_map = build_trade_graph(agents)
    loops = []
    for a in agents:
        _dfs_cycles(graph, a.agent_id, a.agent_id, {a.agent_id}, [], loops, max_cycle_length)
    # Deduplicate by picking a canonical rotation for each loop
    seen = set()
    unique_loops = []
    for loop in loops:
        # build all rotations of this loop
        n = len(loop)
        rotations = [ tuple(loop[i:]+loop[:i]) for i in range(n) ]
        canon = min(rotations)
        if canon not in seen:
            seen.add(canon)
         # restore as a list of edges
            unique_loops.append(list(canon))
    return unique_loops

def execute_loop(loop, id_map):

    # 1) Figure out how much we can move on each edge
    amounts = []
    for frm, to, res in loop:
        giver    = id_map[frm]
        receiver = id_map[to]

        available = giver.inventory.get(res, 0)
        needed    = receiver.needs.get(res, 0)
        amounts.append(min(available, needed))

    qty = min(amounts) if amounts else 0
    if qty <= 0:
        return 0

    # 2) Execute the transfers safely
    for frm, to, res in loop:
        giver    = id_map[frm]
        receiver = id_map[to]

        # subtract from giver
        giver.inventory[res]   = giver.inventory.get(res, 0) - qty

        # add to receiver
        receiver.inventory[res] = receiver.inventory.get(res, 0) + qty

        # reduce their need
        receiver.needs[res]     = max(0, receiver.needs.get(res, 0) - qty)

        # record history on both sides
        # giver logs what they gave
        giver.history.append((to, {res: qty}, {}))
        # receiver logs what they received
        receiver.history.append((frm, {}, {res: qty}))

    return qty

# --- Integration into your engine ---

def detect_and_execute_loops(agents, max_cycle_length=None):
    id_map = {a.agent_id: a for a in agents}
    loops = find_trade_loops(agents, max_cycle_length)
    executed = []
    for loop in loops:
        qty = execute_loop(loop, id_map)
        executed.append((loop, qty))
        # you could deploy smart-contract here for the multi-party agreement
    return executed