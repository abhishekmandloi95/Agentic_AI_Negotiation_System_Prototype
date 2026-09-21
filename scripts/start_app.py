
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
LOGS = Path.home() / "Library" / "Logs" / "AgenticNegotiation"
owned = []
handles = []

def healthy(url, payload=None):
    try:
        data = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=2) as response:
            body = response.read()
        if payload is not None:
            return "result" in json.loads(body)
        return bool(body)
    except Exception:
        return False

def occupied(port):
    with socket.socket() as connection:
        connection.settimeout(1)
        return connection.connect_ex(("127.0.0.1", port)) == 0

def start(name, command, port, probe, timeout=120):
    if probe():
        print(f"{name} is already running; reusing it.", flush=True)
        return
    if occupied(port):
        raise RuntimeError(f"Port {port} is occupied but {name} is not healthy. Close the conflicting service and try again.")
    if not shutil.which(command[0]):
        raise RuntimeError(f"Cannot find {command[0]}. Install it before using this launcher.")
    log = (LOGS / (name.lower() + ".log")).open("a")
    handles.append(log)
    print(f"Starting {name}…", flush=True)
    process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                               start_new_session=True)
    owned.append(process)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"{name} stopped during startup. See {log.name}")
        if probe():
            return
        time.sleep(1)
    raise RuntimeError(f"{name} did not become ready. See {log.name}")

def main():
    LOGS.mkdir(parents=True, exist_ok=True)
    start("Ollama", ["ollama", "serve"], 11434,
          lambda: healthy("http://127.0.0.1:11434/api/tags"))
    start("Ganache", ["npx", "--yes", "ganache@7.9.2", "--server.host", "127.0.0.1",
          "--server.port", "7545", "--database.dbPath", str(Path.home() / ".ganache-negotiation")],
          7545, lambda: healthy("http://127.0.0.1:7545",
          {"jsonrpc": "2.0", "method": "eth_chainId", "params": [], "id": 1}), timeout=180)
    
    port = next((p for p in range(8501, 8521) if not occupied(p)), None)
    if port is None:
        raise RuntimeError("No free web port between 8501 and 8520.")
    start("Streamlit", [sys.executable, "-m", "streamlit", "run", "ui_app.py",
          "--server.address", "127.0.0.1", "--server.port", str(port),
          "--server.headless", "true", "--browser.gatherUsageStats", "false"],
          port, lambda: healthy(f"http://127.0.0.1:{port}/_stcore/health"))
    url = f"http://127.0.0.1:{port}"
    webbrowser.open(url)
    print(f"Ready: {url}\nKeep this window open. Press Ctrl+C to stop services started here.\nLogs: {LOGS}", flush=True)
    while all(p.poll() is None for p in owned):
        time.sleep(2)
    raise RuntimeError("A service stopped. Check the logs above.")

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    signal.signal(signal.SIGHUP, lambda *_: sys.exit(0))
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopping launcher services…")
    except Exception as exc:
        print(f"Startup stopped: {exc}", file=sys.stderr)
    finally:
        for process in reversed(owned):
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        for handle in handles:
            handle.close()
