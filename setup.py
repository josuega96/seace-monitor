import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"


def run(cmd, env=None):
    print(f"> {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=ROOT, env=env)


def main():
    if not VENV_DIR.exists():
        run([sys.executable, "-m", "venv", str(VENV_DIR)])

    if os.name == "nt":
        python_bin = VENV_DIR / "Scripts" / "python.exe"
        pip_bin = VENV_DIR / "Scripts" / "pip.exe"
    else:
        python_bin = VENV_DIR / "bin" / "python"
        pip_bin = VENV_DIR / "bin" / "pip"

    run([str(pip_bin), "install", "--upgrade", "pip"])
    run([str(pip_bin), "install", "-r", "requirements.txt"])
    run([str(python_bin), "-m", "playwright", "install", "chromium"])

    print("\nEntorno listo.")
    print(f"Python virtual env: {python_bin}")
    print("Siguiente paso:")
    print("1) Backend: .venv\\Scripts\\python.exe backend\\server.py")
    print("2) Frontend: cd frontend && npm install && npm run dev")


if __name__ == "__main__":
    main()
