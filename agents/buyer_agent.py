from agents.base_agent import BaseAgent

class BuyerAgent(BaseAgent):
    def __init__(self, agent_id, profile):
        super().__init__(agent_id, profile)
        self.style = profile.get("style", "moderate").lower()

    def evaluate_offer(self, offer):
        item = offer.get("item")
        price = offer.get("price")
        max_price = self.needs.get(item, 0)
        return price <= max_price

    def make_offer(self):
        offer_multiplier = {
            "aggressive": 0.7,
            "moderate": 0.9,
            "cooperative": 1.0
        }.get(self.style, 0.9)

        for item, max_price in self.needs.items():
            return {"item": item, "price": round(max_price * offer_multiplier, 2)}