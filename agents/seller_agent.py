from agents.base_agent import BaseAgent

class SellerAgent(BaseAgent):
    def __init__(self, agent_id, profile):
        super().__init__(agent_id, profile)
        self.style = profile.get("style", "moderate").lower()

    def evaluate_offer(self, offer):
        item = offer.get("item")
        price = offer.get("price")
        min_price = self.inventory.get(item, 0)
        return price >= min_price

    def make_offer(self, to_agent):
        ask_multiplier = {
            "aggressive": 1.3,
            "moderate": 1.1,
            "cooperative": 1.0
        }.get(self.style, 1.1)

        for item in to_agent.needs:
            if item in self.inventory:
                min_price = self.inventory[item]
                return {"item": item, "price": round(min_price * ask_multiplier, 2)}
        
        return None