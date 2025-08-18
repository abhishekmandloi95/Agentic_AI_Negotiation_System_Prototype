import tempfile
import os
from utils.history_store import save_trade_history, load_test_trade_history

def test_contract_save_and_load_roundtrip():
    contract = {
        "initiator": "AgentA",
        "responder": "AgentB",
        "contract_address": "0x123abc",
        "details": {"resource": "analytics", "quantity": 10}
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "contracts.json")
        save_trade_history([contract], path)
        loaded = load_test_trade_history(path)
    
    assert isinstance(loaded, list)
    assert loaded[0]["initiator"] == "AgentA"
    assert loaded[0]["contract_address"] == "0x123abc"