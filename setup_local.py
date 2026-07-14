import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SERVICES = ["backend"]


def run(cmd, cwd):
    print(f"Running in {cwd}: {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=cwd)


def main():
    for service in SERVICES:
        service_dir = ROOT / service
        requirements = service_dir / "requirements.txt"
        venv_dir = service_dir / "venv"
        if not requirements.exists():
            print(f"Skipping {service}: no requirements.txt")
            continue

        if not venv_dir.exists():
            run([sys.executable, "-m", "venv", "venv"], service_dir)

        python_bin = venv_dir / "bin" / "python"
        run([str(python_bin), "-m", "pip", "install", "-r", "requirements.txt"], service_dir)
        if service == "backend":
            run([str(python_bin), "manage.py", "migrate"], service_dir)
            run([str(python_bin), "manage.py", "seed_dev_data"], service_dir)

    print("Local setup complete.")


if __name__ == "__main__":
    main()
