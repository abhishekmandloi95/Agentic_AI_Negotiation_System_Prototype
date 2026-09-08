"""Human-facing chat rendering; execution uses structured protocol events."""
import streamlit as st

def render_conversation(events):
    if not events:
        st.info("Start a new negotiation to see the agents talk.")
        return
    announced = set()
    def bubble(agent, message, label=None):
        with st.chat_message(f"Agent {agent}", avatar="🤖"):
            st.markdown(f"**Agent {agent}**")
            st.write(message)
            if label:
                st.caption(label)

    for event in events:
        kind = event["kind"]
        if kind in ("proposal", "counteroffer"):
            proposal = event["proposal"]
            if proposal["proposal_id"] in announced:
                continue
            announced.add(proposal["proposal_id"])
            if event.get("agent"):
                bubble(event["agent"], event["message"],
                       "Counteroffer" if kind == "counteroffer" else "Offer")
            else:
                st.info("A multilateral exchange is proposed:")
                for transfer in proposal["transfers"]:
                    resource = transfer["resource"].replace("_", " ")
                    st.write(f"Agent {transfer['giver']} offers {transfer['quantity']} units of {resource} to Agent {transfer['receiver']}.")
        elif kind == "decision":
            action = event["action"]
            bubble(event["agent"], event["reason"],
                   {"accept": "Accepted", "reject": "Declined", "counter": "Suggesting different terms"}[action])
        elif kind == "executed":
            st.success("Trade completed — the agreed resources have been exchanged.")
        elif kind == "not_agreed":
            st.info(event["message"])
        elif kind == "error":
            if event.get("category") == "invalid_response":
                st.warning(f"Agent {event['agent']} returned an invalid decision. No approval was recorded. See the technical log.")
            else:
                st.warning(f"Agent {event['agent']} could not respond. Check the selected model provider and see the technical log for details.")
        elif kind == "invalid":
            st.warning("The proposed terms were not valid. No transfer was made.")
        elif kind == "memory_error":
            st.warning(f"Agent {event['agent']}'s memory could not be updated. See the technical log.")
        elif kind == "recording_error":
            st.warning(event["message"])
