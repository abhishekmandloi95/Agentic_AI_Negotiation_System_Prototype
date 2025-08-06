from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

class LLMNegotiationAgent:
    def __init__(self, agent_id, style, inventory: dict, needs: dict):
        # config
        self.agent_id  = agent_id
        self.style     = style
        self.inventory = inventory
        self.needs     = needs

        # history of executed trades
        self.history = []

        # LLM setup (unchanged)
        self.llm = OllamaLLM(model="mistral", temperature=0.7)
        self.prompt_template = PromptTemplate.from_file(
            "prompts/agent_prompt.txt",
            input_variables=[
                "name", "style", "inventory", "needs",
                "partner_name", "partner_inventory", "partner_needs",
                "last_message", "last_speaker", "conversation_history"
            ],
            template_format="jinja2"
        )
        self.chain = self.prompt_template | self.llm

    def open_negotiation(self, partner, max_rounds=None):
        """
        Kick off a negotiation: no prior message or history.
        """

        valid_services = list(set(self.inventory.keys()) | set(partner.inventory.keys()))
        
        input_data = {
            "name": self.agent_id,
            "style": self.style,
            "inventory": ", ".join(f"{k}: {v}" for k, v in self.inventory.items()),
            "needs": ", ".join(f"{k}: {v}" for k, v in self.needs.items()),
            "partner_name": partner.agent_id,
            "partner_inventory": ", ".join(
                f"{k}: {v}" for k, v in partner.inventory.items()
            ),
            "partner_needs": ", ".join(
                f"{k}: {v}" for k, v in partner.needs.items()
            ),
            "last_message": "",
            "last_speaker": "",
            "conversation_history": "",
            "max_rounds": max_rounds,
            "valid_services": valid_services,
        }
        return self.chain.invoke(input_data)

    def respond(self, partner, last_message, conversation_history, last_speaker, max_rounds=None):
        """
        Given the partner’s last message, produce a reply.
        """
        valid_services = list(set(self.inventory.keys()) | set(partner.inventory.keys()))

        input_data = {
            "name": self.agent_id,
            "style": self.style,
            "inventory": ", ".join(f"{k}: {v}" for k, v in self.inventory.items()),
            "needs": ", ".join(f"{k}: {v}" for k, v in self.needs.items()),
            "partner_name": partner.agent_id,
            "partner_inventory": ", ".join(
                f"{k}: {v}" for k, v in partner.inventory.items()
            ),
            "partner_needs": ", ".join(
                f"{k}: {v}" for k, v in partner.needs.items()
            ),
            "last_message": last_message,
            "last_speaker": last_speaker,
            "conversation_history": "\n".join(conversation_history),
            "max_rounds": max_rounds,
            "valid_services": valid_services,
        }
        return self.chain.invoke(input_data)

    def can_offer_to(self, other):
        """True if I have inventory they need."""
        for res, qty in self.inventory.items():
            if qty > 0 and other.needs.get(res, 0) > 0:
                return True
        return False

    def can_request_from(self, other):
        """True if I need something they have."""
        for res, need_qty in self.needs.items():
            if need_qty > 0 and other.inventory.get(res, 0) > 0:
                return True
        return False

    def propose_trade(self, other):
        """
        Build a simple offer: 
        request up to half of their stock (capped by my need)
        offer up to half of my stock (capped by their need).
        """
        for res, need_amt in self.needs.items():
            have = other.inventory.get(res, 0)
            if need_amt and have:
                req = min(have // 2, need_amt)
                for my_res, my_qty in self.inventory.items():
                    want = other.needs.get(my_res, 0)
                    if want and my_qty:
                        off = min(my_qty // 2, want)
                        return {'offer': {my_res: off}, 'request': {res: req}}
        return None

    def execute_trade(self, other, offer, request):
        """Apply agreed exchange and update both sides."""
       # I give:
        for res, amt in offer.items():
            # subtract from me (default 0 if missing, though it shouldn't be)
            self.inventory[res] = self.inventory.get(res, 0) - amt
            # add to other, initializing if needed
            other.inventory[res] = other.inventory.get(res, 0) + amt
            other.needs[res]     = max(0, other.needs.get(res, 0) - amt)
        # I get:
        for res, amt in request.items():
            self.inventory[res] = self.inventory.get(res, 0) + amt
            self.needs[res]     = max(0, self.needs.get(res, 0) - amt)
            other.inventory[res] = other.inventory.get(res, 0) - amt

        # record history for both
        self.history.append((other.agent_id, offer, request))
        other.history.append((self.agent_id, request, offer))