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
            # -- enforce max_len on the closing edge too --
            if max_len and (len(path) + 1) > max_len:
                continue
            loops.append(path + [(current, nbr, res)])
        elif nbr not in visited:
            # -- pre-check to avoid recursing into overlength paths --
            if max_len and (len(path) + 1) > max_len:
                continue
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
        n = len(loop)
        # rotations (forward)
        rotations_fwd = [tuple(loop[i:] + loop[:i]) for i in range(n)]
        # rotations (reversed): reverse order AND swap (from,to) for each edge
        rev = [(to, frm, res) for (frm, to, res) in reversed(loop)]
        rotations_rev = [tuple(rev[i:] + rev[:i]) for i in range(n)]
        canon = min(rotations_fwd + rotations_rev)
        if canon not in seen:
            seen.add(canon)
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

def detect_and_execute_loops(agents, max_cycle_length=None, confirmed_pairs=None):
    loops = []
    found_loops = find_trade_loops(agents, max_cycle_length)
    id_map = {a.agent_id: a for a in agents}  # ✅ define id_map once

    for loop in found_loops:
        loop_pairs = [tuple(sorted([f, t])) for f, t, _ in loop]

        # Check confirmation if required
        if confirmed_pairs is not None:
            missing = [p for p in loop_pairs if p not in confirmed_pairs]
        else:
            missing = []

        if missing:
            reason = f"[Loop invalid: missing verbal confirmations for {missing}. Loop aborted to prevent unfair trades]"
            loops.append((loop, 0, reason))  # ✅ keep reason for UI display
            continue

        qty = execute_loop(loop, id_map)
        if qty <= 0:
            reason = "[Loop invalid: no transferable quantity available]"
            loops.append((loop, 0, reason))  # ✅ keep reason for UI display
            continue

        loops.append((loop, qty))  # No reason for valid loops

    return loops