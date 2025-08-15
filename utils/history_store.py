import json
from pathlib import Path

HISTORY_FILE = Path("data/trade_history.json")

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