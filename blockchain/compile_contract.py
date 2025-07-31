from solcx import compile_standard, install_solc
import json

install_solc("0.8.0")

with open("blockchain/TradeAgreement.sol", "r") as file:
    source_code = file.read()

compiled_sol = compile_standard(
    {
        "language": "Solidity",
        "sources": {"TradeAgreement.sol": {"content": source_code}},
        "settings": {
            "outputSelection": {
                "*": {
                    "*": ["abi", "evm.bytecode.object"]
                }
            }
        }
    },
    solc_version="0.8.0"
)

contract_interface = compiled_sol["contracts"]["TradeAgreement.sol"]["TradeAgreement"]

with open("blockchain/TradeAgreement.json", "w") as f:
    json.dump({
        "abi": contract_interface["abi"],
        "bytecode": contract_interface["evm"]["bytecode"]["object"]
    }, f)

print(" Contract compiled and saved as TradeAgreement.json")