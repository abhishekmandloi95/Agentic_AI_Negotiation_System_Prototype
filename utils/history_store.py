import json
from pathlib import Path
import time
from datetime import datetime

HISTORY_FILE = Path("data/trade_history.json")
CONVO_FILE = None

def load_trade_history():
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return []

def save_trade_to_history(trade):
    history = load_trade_history()
    history.append(trade)
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

def save_trade_history(trades, path="tmp/test_trade_history.json"):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(trades, f, indent=2)

def load_test_trade_history(path="tmp/test_trade_history.json"):
    path = Path(path)
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return []

def create_conversation_log():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = Path(f"data/convo_log_{timestamp}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump([], f)
    return path

def append_conversation_line(agent_id, message, exchange_details=None):
    if not CONVO_FILE:
        return
    log_entry = {
        "agent": agent_id,
        "message": message,
        "timestamp": datetime.now().isoformat(),
    }
    if exchange_details:
        log_entry["details"] = exchange_details
    try:
        with open(CONVO_FILE, "r+") as f:
            history = json.load(f)
            history.append(log_entry)
            f.seek(0)
            json.dump(history, f, indent=2)
            f.truncate()
    except Exception as e:
        print(f"Failed to write to conversation log: {e}")

def load_conversation_log(path):
    path = Path(path)
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return []