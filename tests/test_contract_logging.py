import json
from utils.history_store import (save_trade_history, load_test_trade_history,
                                create_conversation_log, append_conversation_line, load_conversation_log)

def test_contract_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "history.json"
    save_trade_history([{"initiator":"A", "contract_address":"0x123"}], path)
    assert load_test_trade_history(path)[0]["initiator"] == "A"

def test_unique_logs_preserve_sessions(tmp_path):
    first, second = create_conversation_log(tmp_path), create_conversation_log(tmp_path)
    assert first != second
    append_conversation_line("A", "one", path=first)
    append_conversation_line("B", "two", {"quantity": 2}, path=first)
    assert [x["message"] for x in load_conversation_log(first)] == ["one", "two"]
    assert load_conversation_log(first)[1]["details"] == {"quantity": 2}
    assert load_conversation_log(second) == []
