# Contributing to SpamSMS Guardian

Thanks for your interest! This is an offline-first project — please read the
ground rules before opening a PR.

## Ground rules

1. **Never add network egress to the analysis path.** Predictions and threat-signal
   checks must run fully offline. The only module allowed to touch the network is
   `backend/spamsms/billing.py` (Stripe), and only when a key is configured. A test
   enforces this by blocking outbound sockets.
2. **Keep the install trivial.** No new dependency that requires a C compiler unless
   it has wheels for common platforms. Prefer stdlib (`sqlite3`, `hashlib`, `secrets`).
3. **Stay honest about the model.** Do not present scores as calibrated risk. If you
   change decision thresholds, update the README's limitations section and metrics.

## Dev setup

```bash
# backend
cd backend && python -m venv .venv && . .venv/Scripts/activate  # or source on *nix
pip install -r requirements.txt
python -m uvicorn spamsms.main:app --port 8000

# frontend (new terminal)
cd frontend && npm install && npm run dev
```

Run tests: `cd backend && python -m pytest`. Typecheck the frontend: `cd frontend && npm run typecheck`.

## Workflow

- Branch from `main`: `git checkout -b feat/your-idea`.
- Add or update tests for behavior changes.
- Ensure `npm run build` passes if you touched the frontend.
- Open a PR describing the *why*, link any issue, and note any user-visible copy changes.

## Environment notes

- Local development targets Python 3.15; CI runs 3.12–3.13. Some packages lack cp315
  wheels (e.g. PyYAML → hence no `uvicorn[standard]` / SQLAlchemy). Keep runtime deps wheel-safe.
- On locked-down Windows machines, rollup's native binary may be blocked by App Control;
  `frontend/scripts/use-wasm-rollup.mjs` auto-swaps in the WASM build at `npm install`.

## Code style

Python: readable, typed where it helps, no clever one-liners. Frontend: functional React + TS strict mode. Match surrounding code.

By contributing you agree your contributions are licensed under the MIT license.
