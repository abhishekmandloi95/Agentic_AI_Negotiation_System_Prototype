from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
import yaml

class LLMNegotiationAgent:
    def __init__(self, agent_id, profile_path="data/profiles.yaml"):
        self.agent_id = agent_id
        with open(profile_path) as f:
            profiles = yaml.safe_load(f)["agents"]
            profile = next(a for a in profiles if a["id"] == agent_id)

        self.role = profile["role"]
        self.style = profile["style"]
        self.inventory = profile["inventory"]
        self.needs = profile["needs"]

        self.llm = OllamaLLM(model="mistral", temperature=0.7)  # or tinyllama if needed
        self.prompt_template = PromptTemplate.from_file(
            "prompts/agent_prompt.txt",
            input_variables=["name", "style", "inventory", "needs", "partner_name",
                             "partner_inventory", "partner_needs", "last_message"],
            template_format="jinja2"
        )
        self.chain = self.prompt_template | self.llm

    def respond(self, partner_agent, last_message, conversation_history, last_speaker):
        input_data = {
            "name": self.agent_id,
            "style": self.style,
            "inventory": ", ".join(f"{k}: {v}" for k, v in self.inventory.items()),
            "needs": ", ".join(f"{k}: {v}" for k, v in self.needs.items()),
            "partner_name": partner_agent.agent_id,
            "partner_inventory": ", ".join(f"{k}: {v}" for k, v in partner_agent.inventory.items()),
            "partner_needs": ", ".join(f"{k}: {v}" for k, v in partner_agent.needs.items()),
            "last_message": last_message,
            "last_speaker": last_speaker,
            "conversation_history": "\n".join(conversation_history)
        }

        return self.chain.invoke(input_data)
    
    def open_negotiation(self, partner_agent):
        input_data = {
            "name": self.agent_id,
            "style": self.style,
            "inventory": ", ".join(f"{k}: {v}" for k, v in self.inventory.items()),
            "needs": ", ".join(f"{k}: {v}" for k, v in self.needs.items()),
            "partner_name": partner_agent.agent_id,
            "partner_inventory": ", ".join(f"{k}: {v}" for k, v in partner_agent.inventory.items()),
            "partner_needs": ", ".join(f"{k}: {v}" for k, v in partner_agent.needs.items()),
            "last_message": "",  # 👈 empty string means: no prior message
            "last_speaker": "",
            "conversation_history": ""  # No prior conversation
        }
        return self.chain.invoke(input_data)