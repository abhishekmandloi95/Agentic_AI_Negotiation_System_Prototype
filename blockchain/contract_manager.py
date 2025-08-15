import json
from utils.history_store import save_trade_to_history
from web3 import Web3
import streamlit as st

GANACHE_URL = "http://127.0.0.1:7545"

# global container that other files can import
DEPLOY_LOGS: dict[str, str] = {}        # addr → human-readable summary
# ────────────────────────────────────────────────────────────────

def deploy_contract(
    *,
    party_from:       str,
    party_to:         str,
    service_given:    str,
    service_received: str,
    qty_given:        int,
    qty_received:     int,
    note:             str = ""
) -> str:
    """
    Deploy TradeAgreement (6-arg constructor) and store/print a summary.
    """
    w3 = Web3(Web3.HTTPProvider(GANACHE_URL))
    if not w3.is_connected():
        raise ConnectionError(f"Ganache is not running on {GANACHE_URL}")

    with open("blockchain/TradeAgreement.json") as f:
        artifact = json.load(f)

    acct = w3.eth.accounts[0]
    w3.eth.default_account = acct

    TradeAgreement = w3.eth.contract(abi=artifact["abi"],
                                     bytecode=artifact["bytecode"])

    tx_hash = TradeAgreement.constructor(
        party_from,
        party_to,
        service_given,
        service_received,
        qty_given,
        qty_received
    ).transact({"from": acct})

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    address = receipt.contractAddress

    # build & save the one-line summary **inside** the function
    summary = (f"{party_from} → {party_to} : "
               f"{qty_given} {service_given} ⇄ "
               f"{qty_received} {service_received}")
    
    human = note if note else summary      # note will carry the agent-ID text

    print(f"Smart contract deployed at {address} | {human}")
    DEPLOY_LOGS[address] = human           # <- human text for UI

    save_trade_to_history({
    "contract_address": address,
    "initiator": party_from,
    "responder": party_to,
    "service_given": service_given,
    "service_received": service_received,
    "quantity_given": qty_given,
    "quantity_received": qty_received
    })

    try:
        if "current_contracts" not in st.session_state:
            st.session_state.current_contracts = []

        st.session_state.current_contracts.append({
            "contract_address": address,
            "initiator": party_from,
            "responder": party_to,
            "service_given": service_given,
            "service_received": service_received,
            "quantity_given": qty_given,
            "quantity_received": qty_received
        })
    except Exception as e:
        print("Warning: Could not update Streamlit session state. Reason:", e)

    return address