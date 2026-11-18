#!/usr/bin/env python3
"""Build the frontend, then you can serve everything from one uvicorn process.

Usage:  python scripts/build.py
Afterwards:  cd backend && python -m uvicorn spamsms.main:app --port 8000
and open http://localhost:8000 (FastAPI serves frontend/dist same-origin).
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    npm = "npm.cmd" if os.name == "nt" else "npm"
    print("[build] installing frontend deps…")
    subprocess.check_call([npm, "install"], cwd=ROOT / "frontend")
    print("[build] building frontend…")
    subprocess.check_call([npm, "run", "build"], cwd=ROOT / "frontend")
    dist = ROOT / "frontend" / "dist" / "index.html"
    if not dist.exists():
        print("[build] ERROR: expected", dist, "— build may have failed.")
        return 1
    print("[build] OK →", dist)
    print("[build] serve with: cd backend && python -m uvicorn spamsms.main:app --port 8000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
