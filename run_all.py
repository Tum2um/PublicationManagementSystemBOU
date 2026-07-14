import os
import signal
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent

SERVICES = [
    {
        "name": "identity",
        "cwd": ROOT / "services" / "identity",
        "cmd": ["venv/bin/python", "app.py"],
        "url": "http://127.0.0.1:5001/health",
    },
    {
        "name": "submission",
        "cwd": ROOT / "services" / "submission",
        "cmd": ["venv/bin/python", "app.py"],
        "url": "http://127.0.0.1:5002/health",
    },
    {
        "name": "review",
        "cwd": ROOT / "services" / "review",
        "cmd": ["venv/bin/python", "app.py"],
        "url": "http://127.0.0.1:5003/health",
    },
    {
        "name": "masterdata",
        "cwd": ROOT / "services" / "masterdata",
        "cmd": ["venv/bin/python", "app.py"],
        "url": "http://127.0.0.1:5004/health",
    },
    {
        "name": "notification",
        "cwd": ROOT / "services" / "notification",
        "cmd": ["venv/bin/uvicorn", "app.main:app", "--reload", "--port", "5005"],
        "url": "http://127.0.0.1:5005/health",
    },
    {
        "name": "frontend",
        "cwd": ROOT / "frontend",
        "cmd": [sys.executable, "-m", "http.server", "3000", "--bind", "127.0.0.1"],
        "url": "http://127.0.0.1:3000",
    },
]


def main():
    processes = []
    try:
        for service in SERVICES:
            print(f"Starting {service['name']}...")
            proc = subprocess.Popen(
                service["cmd"],
                cwd=service["cwd"],
                env={**os.environ},
            )
            processes.append(proc)

        print("\nAll services starting. Press Ctrl+C to stop.\n")
        for service in SERVICES:
            print(f"{service['name']}: {service['url']}")

        for proc in processes:
            proc.wait()
    except KeyboardInterrupt:
        print("\nStopping services...")
        for proc in processes:
            proc.send_signal(signal.SIGINT)
        for proc in processes:
            proc.wait(timeout=5)
    except Exception:
        for proc in processes:
            proc.terminate()
        raise


if __name__ == "__main__":
    main()
