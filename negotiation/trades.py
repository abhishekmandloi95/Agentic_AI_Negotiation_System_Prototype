"""Immutable proposals and validated, all-or-nothing in-memory transfers."""
from collections import defaultdict
from dataclasses import asdict, dataclass
from uuid import uuid4

@dataclass(frozen=True)
class Transfer:
    giver: str
    receiver: str
    resource: str
    quantity: int

@dataclass(frozen=True)
class Proposal:
    proposal_id: str
    transfers: tuple[Transfer, ...]
    kind: str = "bilateral"

    @classmethod
    def create(cls, transfers, kind="bilateral"):
        return cls(uuid4().hex, tuple(transfers), kind)

    @property
    def participants(self):
        return tuple(sorted({t.giver for t in self.transfers} | {t.receiver for t in self.transfers}))

    def to_dict(self):
        return {"proposal_id": self.proposal_id, "kind": self.kind,
                "transfers": [asdict(t) for t in self.transfers]}

def validate_balances(values):
    if not isinstance(values, dict) or any(
        not isinstance(k, str) or not k or type(v) is not int or v < 0
        for k, v in values.items()
    ):
        raise ValueError("Inventory and needs must map resource names to nonnegative integers.")

def validate_proposal(proposal, agents_by_id):
    if not proposal.transfers or len(proposal.participants) < 2:
        raise ValueError("A trade must contain transfers between at least two agents.")
    outgoing, incoming = defaultdict(int), defaultdict(int)
    edges = set()
    for t in proposal.transfers:
        if t.giver == t.receiver or t.giver not in agents_by_id or t.receiver not in agents_by_id:
            raise ValueError("Unknown participant or self-transfer.")
        if not isinstance(t.resource, str) or not t.resource or type(t.quantity) is not int or t.quantity <= 0:
            raise ValueError("Transfer quantities must be positive integers.")
        edge = (t.giver, t.receiver, t.resource)
        if edge in edges:
            raise ValueError("Duplicate transfer.")
        edges.add(edge)
        outgoing[t.giver, t.resource] += t.quantity
        incoming[t.receiver, t.resource] += t.quantity
    if set(outgoing) & set(incoming):
        raise ValueError("A participant cannot give and receive the same resource in one proposal.")
    for aid in proposal.participants:
        validate_balances(agents_by_id[aid].inventory)
        validate_balances(agents_by_id[aid].needs)
        if not any(k[0] == aid for k in outgoing) or not any(k[0] == aid for k in incoming):
            raise ValueError("Every participant must both give and receive.")
    for (aid, resource), qty in outgoing.items():
        if qty > agents_by_id[aid].inventory.get(resource, 0):
            raise ValueError(f"{aid} has insufficient {resource}.")
    for (aid, resource), qty in incoming.items():
        if qty > agents_by_id[aid].needs.get(resource, 0):
            raise ValueError(f"Transfer exceeds {aid}'s remaining need for {resource}.")

def execute_proposal(proposal, agents_by_id, approvals):
    if set(approvals) != set(proposal.participants) or any(
        approvals[aid] != proposal.proposal_id for aid in proposal.participants
    ):
        raise ValueError("Every participant must approve this exact proposal ID.")
    if any(proposal.proposal_id in getattr(agents_by_id[aid], "executed_proposals", set())
           for aid in proposal.participants):
        raise ValueError("Proposal has already been executed.")
    validate_proposal(proposal, agents_by_id)
    # Prepare every new state before publishing any mutation.
    inventories = {aid: dict(agents_by_id[aid].inventory) for aid in proposal.participants}
    needs = {aid: dict(agents_by_id[aid].needs) for aid in proposal.participants}
    histories = {aid: list(agents_by_id[aid].history) for aid in proposal.participants}
    for t in proposal.transfers:
        inventories[t.giver][t.resource] -= t.quantity
        inventories[t.receiver][t.resource] = inventories[t.receiver].get(t.resource, 0) + t.quantity
        needs[t.receiver][t.resource] -= t.quantity
        histories[t.giver].append((t.receiver, {t.resource: t.quantity}, {}))
        histories[t.receiver].append((t.giver, {}, {t.resource: t.quantity}))
    for aid in proposal.participants:
        agent = agents_by_id[aid]
        agent.inventory, agent.needs, agent.history = inventories[aid], needs[aid], histories[aid]
        agent.executed_proposals = getattr(agent, "executed_proposals", set()) | {proposal.proposal_id}
    return {**proposal.to_dict(), "approvals": dict(approvals), "status": "executed",
            "contract_address": None, "blockchain_status": "not_requested"}
