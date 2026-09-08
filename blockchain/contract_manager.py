"""Blockchain audit recording, separate from trade execution and UI state."""
import json
import os
from utils.paths import ROOT

GANACHE_URL = os.getenv("GANACHE_URL", "http://127.0.0.1:7545")
DEPLOY_LOGS = {}

def get_w3():
    from web3 import Web3
    return Web3(Web3.HTTPProvider(GANACHE_URL, request_kwargs={"timeout": 10}))

def _deploy(artifact_name, args, *, w3=None):
    w3 = get_w3() if w3 is None else w3
    if not w3.is_connected():
        raise ConnectionError(f"Blockchain unavailable at {GANACHE_URL}")
    target = ROOT / "blockchain" / artifact_name
    if not target.exists():
        raise FileNotFoundError("Compile TradeRecord first: python -m blockchain.compile_contract --install")
    artifact = json.loads(target.read_text())
    accounts = w3.eth.accounts
    if not accounts:
        raise RuntimeError("Blockchain has no unlocked recording account.")
    contract = w3.eth.contract(abi=artifact["abi"], bytecode=artifact["bytecode"])
    tx = contract.constructor(*args).transact({"from": accounts[0]})
    receipt = w3.eth.wait_for_transaction_receipt(tx, timeout=120)
    if receipt.status != 1 or not receipt.contractAddress:
        raise RuntimeError("Contract deployment reverted.")
    return receipt.contractAddress

def record_trade(record, *, w3=None):
    if record.get("status") != "executed" or not record.get("transfers"):
        raise ValueError("Only executed, complete trades can be recorded.")
    # Stable payload excludes subsequent recording/persistence status.
    payload = {k: record[k] for k in ("proposal_id", "kind", "transfers", "approvals", "status")}
    participants = {t["giver"] for t in payload["transfers"]} | {t["receiver"] for t in payload["transfers"]}
    if set(payload["approvals"]) != participants or any(
        value != payload["proposal_id"] for value in payload["approvals"].values()
    ):
        raise ValueError("Missing or mismatched approvals.")
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    address = _deploy("TradeRecord.json", [serialized], w3=w3)
    DEPLOY_LOGS[address] = payload["proposal_id"]
    return address

def read_record(address, *, w3=None):
    w3 = get_w3() if w3 is None else w3
    artifact = json.loads((ROOT / "blockchain/TradeRecord.json").read_text())
    contract = w3.eth.contract(address=address, abi=artifact["abi"])
    return json.loads(contract.functions.recordJson().call())

def deploy_contract(*, party_from, party_to, service_given, service_received,
                    qty_given, qty_received, note=""):
    """Legacy six-field recorder retained for old callers and historical records."""
    return _deploy("TradeAgreement.json", [party_from, party_to, service_given,
                                          service_received, qty_given, qty_received])
