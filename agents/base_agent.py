"""Negotiation agents with explicit decisions and optional local LLM/RAG."""
import json
import os
from jinja2 import Environment, StrictUndefined
from market.service import service as _MARKET
from negotiation.trades import Proposal, Transfer, execute_proposal, validate_balances
from utils.paths import ROOT

DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "proposal_id": {"type": "string"},
        "action": {"type": "string", "enum": ["accept", "reject", "counter"]},
        "reason": {"type": "string"},
        "transfers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "giver": {"type": "string"}, "receiver": {"type": "string"},
                    "resource": {"type": "string"},
                    "quantity": {"type": "integer", "minimum": 1},
                },
                "required": ["giver", "receiver", "resource", "quantity"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["proposal_id", "action", "reason"],
    "additionalProperties": False,
}

def decision_schema(proposal):
    from copy import deepcopy
    schema = deepcopy(DECISION_SCHEMA)
    schema["required"] = list(schema["properties"])
    if proposal["kind"] != "bilateral":
        schema["properties"]["action"]["enum"] = ["accept", "reject"]
    return schema

class OllamaDecisionClient:
    def __init__(self, model=None, seed=0):
        self.model = model or os.getenv("OLLAMA_MODEL", "mistral")
        self.seed = seed

    def invoke(self, inputs):
        import requests
        response = requests.post(
            os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/") + "/api/generate",
            json={"model": self.model, "prompt": inputs["prompt"], "stream": False,
                  "format": decision_schema(inputs["proposal"]), "options": {"temperature": 0, "seed": self.seed}},
            timeout=(5, 120),
        )
        response.raise_for_status()
        return response.json()["response"]

class OpenAIDecisionClient:
    """OpenAI adapter using the same validated negotiation decisions."""
    def __init__(self, model="gpt-5", api_key=None):
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")

    def invoke(self, inputs):
        import requests
        from copy import deepcopy
        if not self.api_key:
            raise ValueError("Enter an OpenAI API key in the sidebar or set OPENAI_API_KEY.")
        schema = decision_schema(inputs["proposal"])
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": "Bearer " + self.api_key},
            json={"model": self.model,
                  "messages": [{"role": "user", "content": inputs["prompt"] +
                                "\nAlways include transfers: use [] for accept or reject."}],
                  "response_format": {"type": "json_schema", "json_schema": {
                      "name": "negotiation_decision", "strict": True, "schema": schema}}},
            timeout=(5, 120),
        )
        if not response.ok:
            raise RuntimeError(f"OpenAI request failed (HTTP {response.status_code}). Check your API key, model access, billing and rate limits.")
        choice = response.json()["choices"][0]
        if choice["message"].get("refusal"):
            raise ValueError("OpenAI declined to provide a negotiation decision.")
        if choice.get("finish_reason") != "stop" or not choice["message"].get("content"):
            raise ValueError("OpenAI returned an incomplete decision; no approval was recorded.")
        return choice["message"]["content"]

class RuleDecisionClient:
    """Deterministic baseline; does not model LLM or RAG effects."""
    def invoke(self, inputs):
        return {"proposal_id": inputs["proposal"]["proposal_id"],
                "action": "accept", "reason": "That works for me—it gives me resources I need."}

class LLMNegotiationAgent:
    def __init__(self, agent_id, style, inventory, needs, memory_enabled=True,
                 *, decision_client=None, market=None, memory=None, auto_accept=False, seed=0):
        if not isinstance(agent_id, str) or not agent_id:
            raise ValueError("Agent ID must be a nonempty string.")
        validate_balances(inventory)
        validate_balances(needs)
        self.agent_id, self.style = agent_id, style
        self.inventory, self.needs = dict(inventory), dict(needs)
        # Needs represent outstanding demand, separate from transferable inventory.
        self.initial_needs = dict(needs)
        self.history, self.executed_proposals = [], set()
        self.market = market if market is not None else _MARKET
        self.memory_enabled, self.auto_accept = memory_enabled, auto_accept
        self.memory = memory if memory_enabled else None
        self.chain = decision_client if decision_client is not None else OllamaDecisionClient(seed=seed)
        self._template = Environment(undefined=StrictUndefined).from_string(
            (ROOT / "prompts/agent_prompt.txt").read_text()
        )

    def _memory(self):
        if self.memory_enabled and self.memory is None:
            from negotiation.rag_memory import NegotiationRAGMemory
            self.memory = NegotiationRAGMemory()
        return self.memory

    def decide(self, proposal, conversation=(), *, participants=None):
        from negotiation.protocol import parse_decision
        context = self.market.context(sorted({t.resource for t in proposal.transfers}))
        memories = []
        memory = self._memory() if self.memory_enabled else None
        if memory is not None:
            for partner in proposal.participants:
                if partner != self.agent_id:
                    memories.extend(memory.retrieve(self.agent_id, partner, json.dumps(proposal.to_dict())))
        inputs = {
            "name": self.agent_id, "style": self.style,
            "my_outgoing": [t.__dict__ for t in proposal.transfers if t.giver == self.agent_id],
            "my_incoming": [t.__dict__ for t in proposal.transfers if t.receiver == self.agent_id],
            "participants": participants or {},
            "inventory": self.inventory, "needs": self.needs,
            "proposal": proposal.to_dict(), "market_context": context.for_prompt(),
            "retrieved_memory": memories, "conversation_history": list(conversation)[-20:],
        }
        inputs["prompt"] = self._template.render(**inputs)
        # A format repair is bounded; tool/network failures are reported by the protocol.
        for attempt in range(2):
            raw = self.chain.invoke(inputs)
            try:
                decision = parse_decision(raw, proposal.proposal_id, self.agent_id)
                if decision["action"] == "counter":
                    if proposal.kind != "bilateral":
                        raise ValueError("Loops allow only accept or reject; use transfers: [].")
                    from types import SimpleNamespace
                    from negotiation.trades import validate_proposal
                    counter = Proposal.create([Transfer(**t) for t in decision["transfers"]])
                    if set(counter.participants) != set(proposal.participants):
                        raise ValueError("Keep the same two participants in the counteroffer.")
                    balances = {aid: SimpleNamespace(**values) for aid, values in (participants or {}).items()}
                    if balances:
                        validate_proposal(counter, balances)
                return decision
            except ValueError as exc:
                if attempt:
                    raise
                inputs["prompt"] += "\nYour previous response was invalid: " + str(exc) + "\nReturn a corrected decision for the current proposal. Include transfers: [] for accept/reject; bilateral counters must include both complete transfer legs. Do not treat this retry as acceptance."
        raise AssertionError("Unreachable")

    def remember(self, proposal, accepted):
        if not self.memory_enabled:
            return
        memory = self._memory()
        text = json.dumps({"outcome": "executed" if accepted else "not executed", **proposal.to_dict()})
        for partner in proposal.participants:
            if partner != self.agent_id:
                memory.add_snippet(self.agent_id, partner, text)

    def can_offer_to(self, other):
        return any(q > 0 and other.needs.get(r, 0) > 0 for r, q in self.inventory.items())

    def can_request_from(self, other):
        return other.can_offer_to(self)

    def propose_trade(self, other, fraction=0.5):
        context = self.market.context(sorted(set(self.inventory) | set(other.inventory)))
        for resource, need in sorted(self.needs.items()):
            stock = other.inventory.get(resource, 0)
            if need <= 0 or stock <= 0:
                continue
            scalar = context.by_service[resource].price_scalar
            requested = max(1, min(stock, need, round(max(1, int(stock * fraction)) * scalar)))
            for given, stock_given in sorted(self.inventory.items()):
                want = other.needs.get(given, 0)
                if want <= 0 or stock_given <= 0 or given == resource:
                    continue
                scalar = context.by_service[given].price_scalar
                offered = max(1, min(stock_given, want, round(max(1, int(stock_given * fraction)) / scalar)))
                return {"offer": {given: offered}, "request": {resource: requested}}
        return None

    def execute_trade(self, other, offer, request):
        """Low-level caller-authorised exchange. Protocol uses explicit approvals instead."""
        if not offer or not request:
            raise ValueError("Both sides of an exchange are required.")
        proposal = Proposal.create(
            [Transfer(self.agent_id, other.agent_id, r, q) for r, q in offer.items()] +
            [Transfer(other.agent_id, self.agent_id, r, q) for r, q in request.items()]
        )
        return execute_proposal(proposal, {self.agent_id: self, other.agent_id: other},
                                {aid: proposal.proposal_id for aid in proposal.participants})

    def get_utility(self):
        return sum(max(0, initial - self.needs.get(r, 0)) for r, initial in self.initial_needs.items())
