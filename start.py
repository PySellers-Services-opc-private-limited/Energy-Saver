#!/usr/bin/env python3
"""
Energy Saver AI – Project Startup Script
==========================================
Starts the backend API server (and optionally prints frontend instructions).

Usage:
    python start.py                  # start backend in dev mode
    python start.py --prod           # start backend in production mode
    python start.py --port 8080      # custom port
    python start.py --check          # verify environment only
"""

from __future__ import annotations

import argparse
import importlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
BACKEND_DIR = ROOT / "backend"


# ── Colours ───────────────────────────────────────────────────────────────────

class C:
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    CYAN   = "\033[96m"
    RESET  = "\033[0m"
    BOLD   = "\033[1m"


def ok(msg: str)   -> None: print(f"{C.GREEN}  ✓  {msg}{C.RESET}")
def warn(msg: str) -> None: print(f"{C.YELLOW}  !  {msg}{C.RESET}")
def err(msg: str)  -> None: print(f"{C.RED}  ✗  {msg}{C.RESET}")
def info(msg: str) -> None: print(f"{C.CYAN}  →  {msg}{C.RESET}")


# ── Environment Check ─────────────────────────────────────────────────────────

def check_environment() -> bool:
    print(f"\n{C.BOLD}Energy Saver AI — Environment Check{C.RESET}")
    print("=" * 42)

    all_ok = True

    # Python version
    major, minor = sys.version_info[:2]
    if major == 3 and minor >= 10:
        ok(f"Python {major}.{minor} (✓ 3.10+ required)")
    else:
        err(f"Python {major}.{minor} – need 3.10+")
        all_ok = False

    # Required packages
    required = ["fastapi", "uvicorn", "sqlalchemy", "pydantic", "jose", "bcrypt"]
    for pkg in required:
        try:
            importlib.import_module(pkg.replace("-", "_"))
            ok(f"Package: {pkg}")
        except ImportError:
            err(f"Package missing: {pkg}  →  pip install -r backend/requirements.txt")
            all_ok = False

    # .env file
    env_file = ROOT / ".env"
    if env_file.exists():
        ok(".env file found")
    else:
        warn(".env not found – using defaults (copy .env.example to .env)")

    # Model files
    model_dir = ROOT / "models"
    keras_files = list(model_dir.glob("*.keras"))
    if keras_files:
        ok(f"Model files: {len(keras_files)} .keras files found")
    else:
        warn("No .keras model files – run: python main.py train (or make train)")

    # Data directory
    data_dir = ROOT / "data"
    csv_files = list(data_dir.glob("*.csv"))
    if csv_files:
        ok(f"Data files: {len(csv_files)} CSV files found")
    else:
        warn("No data CSVs – run: python data/generate_data.py (or make data)")

    print()
    return all_ok


# ── Start Backend ─────────────────────────────────────────────────────────────

def start_backend(prod: bool = False, port: int = 8000, host: str = "0.0.0.0") -> None:
    print(f"\n{C.BOLD}Starting Energy Saver AI Backend{C.RESET}")
    print("=" * 42)
    info(f"Mode:   {'production' if prod else 'development (reload)'}")
    info(f"URL:    http://{host}:{port}")
    info(f"Docs:   http://localhost:{port}/docs")
    info(f"Health: http://localhost:{port}/healthz")
    print()

    # Frontend reminder
    print(f"{C.YELLOW}Frontend{C.RESET}: run in a separate terminal:")
    print(f"   npm --prefix frontend run dev   →  http://localhost:5173\n")

    # Build command
    cmd = [
        sys.executable,
        str(BACKEND_DIR / "run_server.py"),
        "--host", host,
        "--port", str(port),
    ]
    if not prod:
        cmd.append("--reload")
    else:
        cmd += ["--workers", "4"]

    os.execv(sys.executable, cmd)  # replace this process


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Energy Saver AI startup script")
    parser.add_argument("--prod",    action="store_true", help="Production mode (4 workers, no reload)")
    parser.add_argument("--port",    type=int, default=8000, help="Port (default: 8000)")
    parser.add_argument("--host",    default="0.0.0.0", help="Host (default: 0.0.0.0)")
    parser.add_argument("--check",   action="store_true", help="Check environment only, don't start server")
    args = parser.parse_args()

    all_ok = check_environment()

    if args.check:
        sys.exit(0 if all_ok else 1)

    if not all_ok:
        warn("Some checks failed – starting anyway…\n")

    start_backend(prod=args.prod, port=args.port, host=args.host)


if __name__ == "__main__":
    main()
