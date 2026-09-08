import os
import pytest
from negotiation.protocol import run_negotiation_simulation

@pytest.mark.blockchain
def test_full_cycle_roundtrip_on_in_memory_evm(make_agent):
    pytest.importorskip("eth_tester")
    from web3 import Web3, EthereumTesterProvider
    from blockchain.contract_manager import record_trade, read_record
    w3 = Web3(EthereumTesterProvider())
    agents = [make_agent("A", {"x": 3}, {"z": 3}), make_agent("B", {"y": 3}, {"x": 3}),
              make_agent("C", {"z": 3}, {"y": 3})]
    _, records = run_negotiation_simulation(agents=agents, rounds=0,
        record_on_chain=True, recorder=lambda record: record_trade(record, w3=w3))
    record = records[0]
    assert record["blockchain_status"] == "recorded", record.get("blockchain_error")
    stored = read_record(record["contract_address"], w3=w3)
    assert stored["transfers"] == record["transfers"]
    assert stored["approvals"] == record["approvals"]

@pytest.mark.ganache
def test_live_ganache_roundtrip(make_agent):
    if os.getenv("GANACHE_OK") != "1":
        pytest.skip("Set GANACHE_OK=1 to explicitly enable a local deployment.")
    from blockchain.contract_manager import read_record
    agents = [make_agent("A", {"x": 2}, {"y": 1}), make_agent("B", {"y": 2}, {"x": 1})]
    _, records = run_negotiation_simulation(agents=agents, record_on_chain=True)
    assert records[0]["blockchain_status"] == "recorded", records[0].get("blockchain_error")
    assert read_record(records[0]["contract_address"])["transfers"] == records[0]["transfers"]
