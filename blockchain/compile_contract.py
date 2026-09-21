
import argparse
import json
from pathlib import Path
from utils.paths import ROOT

def compile_record(install=False):
    from solcx import compile_standard, get_installed_solc_versions, install_solc
    version = "0.8.20"
    if version not in {str(v) for v in get_installed_solc_versions()}:
        if not install:
            raise RuntimeError("Compiler missing. Run: python -m blockchain.compile_contract --install")
        install_solc(version)
    source = (ROOT / "blockchain/TradeRecord.sol").read_text()
    result = compile_standard({
        "language": "Solidity", "sources": {"TradeRecord.sol": {"content": source}},
        "settings": {"outputSelection": {"*": {"*": ["abi", "evm.bytecode.object"]}}},
    }, solc_version=version)
    contract = result["contracts"]["TradeRecord.sol"]["TradeRecord"]
    artifact = {"abi": contract["abi"], "bytecode": contract["evm"]["bytecode"]["object"],
                "compiler": version}
    target = ROOT / "blockchain/TradeRecord.json"
    target.write_text(json.dumps(artifact, indent=2))
    return target

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()
    print(compile_record(args.install))
