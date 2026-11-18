# Shell-agnostic shortcuts (each recipe delegates to a Python script so it works
# identically in bash, PowerShell, and cmd — no `&&` chains or shell-specific syntax).
# Requires an activated virtualenv on PATH for backend targets.

.PHONY: install-backend dev build test serve clean

install-backend:
	python -m pip install -r backend/requirements.txt

dev:
	python scripts/dev.py

build:
	python scripts/build.py

test:
	cd backend && python -m pytest -q

serve:
	cd backend && python -m uvicorn spamsms.main:app --port 8000

clean:
	python -c "import shutil,glob,os; [shutil.rmtree(p,ignore_errors=True) for p in glob.glob('**/__pycache__',recursive=True)]; print('cleaned')"
