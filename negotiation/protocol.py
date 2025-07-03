from agents.base_agent import LLMNegotiationAgent
from blockchain.contract_manager import deploy_contract

def execute_multiagent_chain(loop_ids, agents_by_id):
    conversation = []
    for i in range(len(loop_ids)):
        sender_id = loop_ids[i]
        receiver_id = loop_ids[(i + 1) % len(loop_ids)]
        sender = agents_by_id[sender_id]
        receiver = agents_by_id[receiver_id]

        if i == 0:
            msg = sender.open_negotiation(receiver)
        else:
            msg = sender.respond(receiver, last_message, conversation, last_speaker)

        print(f"{sender_id}: {msg}\n")
        conversation.append(f"{sender_id}: {msg}")
        if "agreement" in msg.lower():
            deploy_contract(
                sender.agent_id,
                receiver.agent_id,
                "data_service",
                "legal_service",
                50, 100
            )
        last_message = msg
        last_speaker = sender_id

    