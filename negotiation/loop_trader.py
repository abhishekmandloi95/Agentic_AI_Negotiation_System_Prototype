"""Directed trade cycles; prior bilateral acceptance never authorises a cycle."""
from collections import defaultdict
from negotiation.trades import Proposal, Transfer, execute_proposal

def build_trade_graph(agents):
    id_map = {a.agent_id: a for a in agents}
    if len(id_map) != len(agents):
        raise ValueError("Agent IDs must be unique.")
    graph = defaultdict(list)
    for a in agents:
        for b in agents:
            if a.agent_id != b.agent_id:
                for r, q in sorted(a.inventory.items()):
                    if q > 0 and b.needs.get(r, 0) > 0:
                        graph[a.agent_id].append((b.agent_id, r))
    return graph, id_map

def find_trade_loops(agents, max_cycle_length=None):
    graph, _ = build_trade_graph(agents)
    if len(agents) < 2:
        return []
    limit = len(agents) if max_cycle_length is None else max_cycle_length
    if limit < 2:
        raise ValueError("Cycle length must be at least two.")
    seen = set()
    def visit(start, current, visited, path):
        for neighbor, resource in graph[current]:
            edge = (current, neighbor, resource)
            if neighbor == start and len(path) >= 1:
                loop = path + [edge]
                if len(loop) <= limit and all(loop[i][2] != loop[(i + 1) % len(loop)][2] for i in range(len(loop))):
                    # Rotations preserve directed edges; reversal does not.
                    seen.add(min(tuple(loop[i:] + loop[:i]) for i in range(len(loop))))
            elif neighbor not in visited and len(path) + 1 < limit:
                visit(start, neighbor, visited | {neighbor}, path + [edge])
    for aid in sorted(graph.copy()):
        visit(aid, aid, {aid}, [])
    return [list(loop) for loop in sorted(seen)]

def loop_proposal(loop, id_map):
    if len(loop) < 2 or len({edge[0] for edge in loop}) != len(loop):
        raise ValueError("A cycle must visit each participant once.")
    if any(loop[i][1] != loop[(i + 1) % len(loop)][0] for i in range(len(loop))):
        raise ValueError("Cycle edges do not form a closed directed path.")
    qty = min(min(id_map[f].inventory.get(r, 0), id_map[t].needs.get(r, 0)) for f, t, r in loop)
    if qty <= 0:
        return None
    return Proposal.create([Transfer(f, t, r, qty) for f, t, r in loop], kind="loop")

def execute_loop(loop, id_map, *, proposal=None, approvals=None):
    if proposal is None or approvals is None:
        raise ValueError("Explicit cycle proposal and participant approvals are required.")
    if tuple((t.giver, t.receiver, t.resource) for t in proposal.transfers) != tuple(loop):
        raise ValueError("Approvals do not match these cycle edges.")
    execute_proposal(proposal, id_map, approvals)
    return proposal.transfers[0].quantity

def detect_and_execute_loops(agents, max_cycle_length=None, confirmed_pairs=None, *, approve=None):
    """Compatibility helper. A callback must approve each exact cycle proposal."""
    id_map = {a.agent_id: a for a in agents}
    results = []
    for loop in find_trade_loops(agents, max_cycle_length):
        proposal = loop_proposal(loop, id_map)
        if proposal is None:
            results.append((loop, 0, "No transferable quantity"))
        elif approve is None:
            results.append((loop, 0, "Missing explicit cycle approvals; bilateral confirmations do not suffice"))
        else:
            approvals = {aid: proposal.proposal_id for aid in proposal.participants
                         if approve(id_map[aid], proposal) is True}
            if len(approvals) != len(proposal.participants):
                results.append((loop, 0, "Cycle rejected"))
            else:
                results.append((loop, execute_loop(loop, id_map, proposal=proposal, approvals=approvals)))
    return results
