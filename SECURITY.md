# Security Policy

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Email the maintainers
privately (open a draft issue with only the title "security" and we'll follow up, or
use GitHub's private vulnerability reporting if enabled). We aim to acknowledge within
72 hours and ship a fix or guidance within 30 days.

## Scope & design guarantees

SpamSMS Guardian is **offline-first**. Threat model highlights:

- **Message privacy**: analysis text never leaves your server. No third-party AI or
  URL-reputation calls. URLs are parsed structurally and never opened or fetched.
- **Auth**: passwords use PBKDF2-SHA256 (240k iterations); sessions are opaque bearer
  tokens stored as SHA-256 hashes; CSRF is structurally impossible (no ambient cookies).
- **Entitlements**: trial credit spending is atomic (`UPDATE … WHERE trial_used < limit`
  inside `BEGIN IMMEDIATE`) — verified by a concurrency test that rejects double-spend.
- **Payments**: Stripe webhooks verify signatures over raw bytes and dedupe by event id
  (idempotent). Without keys, billing runs in an offline mock mode that touches no network.

## Out of scope / known limitations

- The bundled classifier trains on a tiny demo corpus and is **not** a production-grade
  spam filter. Do not rely on verdicts for real security decisions.
- Self-hosting responsibility: keep the app server and its SQLite file on trusted,
  access-controlled storage. Rotate any Stripe secrets you configure.

## Hardening checklist for operators

- Run behind TLS in production; set `FRONTEND_ORIGIN` correctly.
- Restrict `/api/billing/webhook` to Stripe's source IPs where possible.
- Set strong `STRIPE_WEBHOOK_SECRET`; never commit `.env`.
- Keep dependencies patched (`pip list --outdated`, `npm audit`).
