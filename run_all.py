import os
import signal
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent

SERVICES = [
    {
        "name": "django-backend",
        "cwd": ROOT / "backend",
        "cmd": ["venv/bin/python", "manage.py", "runserver", "127.0.0.1:8000"],
        "url": "http://127.0.0.1:8000/health",
    },
    {
        "name": "frontend",
        "cwd": ROOT,
        "cmd": [sys.executable, "serve_frontend.py"],
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
