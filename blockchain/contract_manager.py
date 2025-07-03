from web3 import Web3
import json

GANACHE_URL = "http://127.0.0.1:7545"

def deploy_contract(initiator, responder, service_given, service_received, qty_given, qty_received):
    web3 = Web3(Web3.HTTPProvider(GANACHE_URL))

    with open("blockchain/TradeAgreement.json") as f:
        contract_data = json.load(f)

    abi = contract_data["abi"]
    bytecode = contract_data["bytecode"]

    acct = web3.eth.accounts[0]
    web3.eth.default_account = acct

    TradeAgreement = web3.eth.contract(abi=abi, bytecode=bytecode)

    tx_hash = TradeAgreement.constructor(
        acct,
        web3.eth.accounts[1],
        service_given,
        service_received,
        qty_given,
        qty_received
    ).transact()

    receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"Smart contract deployed at {receipt.contractAddress}")
    return receipt.contractAddress