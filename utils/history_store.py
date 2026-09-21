
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from uuid import uuid4
from utils.paths import DATA_DIR, project_path

HISTORY_FILE = DATA_DIR / "trade_history.json"
CONVO_FILE = None
_LOCK = RLock()

def _load(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        rows = json.load(f)
    if not isinstance(rows, list):
        raise ValueError(f"Expected a JSON list in {path}")
    return rows

def _write(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".history-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2, ensure_ascii=False)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def load_trade_history():
    with _LOCK:
        return _load(HISTORY_FILE)

def save_trade_to_history(trade):
    with _LOCK:
        rows = _load(HISTORY_FILE)
        rows.append(trade)
        _write(HISTORY_FILE, rows)

def save_trade_history(trades, path="tmp/test_trade_history.json"):
    with _LOCK:
        _write(project_path(path), trades)

def load_test_trade_history(path="tmp/test_trade_history.json"):
    return _load(project_path(path))

def create_conversation_log(directory=None):
    directory = Path(directory) if directory is not None else DATA_DIR
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    path = directory / f"convo_log_{stamp}_{uuid4().hex}.json"
    with path.open("x", encoding="utf-8") as f:
        json.dump([], f)
    return path

def append_conversation_line(agent_id, message, exchange_details=None, *, path=None):
    path = path if path is not None else CONVO_FILE
    if path is None:
        return
    entry = {"agent": agent_id, "message": message,
             "timestamp": datetime.now(timezone.utc).isoformat()}
    if exchange_details is not None:
        entry["details"] = exchange_details
    with _LOCK:
        rows = _load(path)
        rows.append(entry)
        _write(path, rows)

def load_conversation_log(path):
    with _LOCK:
        return _load(path)
