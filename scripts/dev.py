#!/usr/bin/env python3
"""Start backend + frontend dev servers with one command (shell-agnostic).

Usage:  python scripts/dev.py
Windows note: this does not activate a venv; run it inside your activated env,
or use the documented per-directory commands in README.md.
"""

import os
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    procs = []
    py = sys.executable

    backend = subprocess.Popen(
        [py, "-m", "uvicorn", "spamsms.main:app", "--port", "8000"],
        cwd=ROOT / "backend",
    )
    procs.append(backend)
    print("[dev] backend → http://localhost:8000")

    npm = "npm.cmd" if os.name == "nt" else "npm"
    try:
        frontend = subprocess.Popen([npm, "run", "dev"], cwd=ROOT / "frontend")
        procs.append(frontend)
        print("[dev] frontend → http://localhost:5173")
    except FileNotFoundError:
        print("[dev] npm not found — start the frontend manually (cd frontend && npm run dev)")

    def shutdown(_sig, _frm):
        for p in procs:
            p.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Wait on the backend; if it dies, tear everything down.
    code = backend.wait()
    shutdown(None, None)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
