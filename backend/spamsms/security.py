"""Stdlib password hashing, bearer-token sessions, rate limiting, and the
entitlement/quota dependency that gates analysis and Pro features.

Auth is opaque bearer tokens (not cookies): cross-port cookie sessions on
http://localhost are a known trap and tokens make CSRF structurally impossible.
Only sha256(token) is stored, so a DB dump cannot be replayed as a session.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException, Request

PBKDF2_ITERATIONS = 240_000


# --- passwords -------------------------------------------------------------
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(PBKDF2_ITERATIONS, salt.hex(), dk.hex())


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- token bucket rate limiter (per key) -----------------------------------
class RateLimiter:
    def __init__(self, per_minute: int):
        self.capacity = max(1, per_minute)
        self.rate = self.capacity / 60.0
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            tokens, last = self._buckets.get(key, (float(self.capacity), now))
            tokens = min(self.capacity, tokens + (now - last) * self.rate)
            if tokens >= 1:
                self._buckets[key] = (tokens - 1, now)
                return True
            self._buckets[key] = (tokens, now)
            return False


# --- identity resolved from request ----------------------------------------
@dataclass
class Identity:
    kind: str                 # "anonymous" | "trial" | "paid"
    user_id: int | None
    email: str | None
    device_id: str | None
    remaining: int | None     # analyses left before paywall (None = unlimited/pro)
    limit: int | None
    can_bulk_scan: bool


class QuotaService:
    """Single place that enforces anonymous grace, trial spend, and Pro gating."""

    def __init__(self, db, settings):
        self.db = db
        self.settings = settings

    # -- anonymous grace --
    def _anon_remaining(self, device_id: str) -> int:
        row = self.db.query_one("SELECT used FROM anonymous_usage WHERE device_id=?", (device_id,))
        used = row["used"] if row else 0
        return max(0, self.settings.anonymous_grace_limit - used)

    def _consume_anon(self, device_id: str) -> bool:
        def _tx(conn):
            conn.execute(
                "INSERT INTO anonymous_usage(device_id, used, first_seen_at) VALUES(?,0,?) "
                "ON CONFLICT(device_id) DO NOTHING",
                (device_id, now_iso()),
            )
            cur = conn.execute(
                "UPDATE anonymous_usage SET used = used + 1 "
                "WHERE device_id=? AND used < ?",
                (device_id, self.settings.anonymous_grace_limit),
            )
            if cur.rowcount != 1:
                raise HTTPException(status_code=402, detail="Free checks exhausted. Create an account to continue.")
            return True
        return self.db.transaction(_tx)

    # -- trial --
    def _consume_trial(self, user_id: int) -> int:
        """Atomically spend one trial credit; returns remaining. Raises 402 when spent."""
        def _tx(conn):
            cur = conn.execute(
                "UPDATE entitlements SET trial_used = trial_used + 1 "
                "WHERE user_id=? AND paid_until IS NULL AND trial_used < trial_limit",
                (user_id,),
            )
            if cur.rowcount != 1:
                raise HTTPException(status_code=402, detail="Trial complete. Subscribe to keep scanning.")
            row = conn.execute("SELECT trial_used, trial_limit FROM entitlements WHERE user_id=?", (user_id,)).fetchone()
            return max(0, row["trial_limit"] - row["trial_used"])
        return self.db.transaction(_tx)

    def resolve(self, request: Request, authorization: str | None) -> Identity:
        user = None
        if authorization and authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1].strip()
            user = self._user_from_token(token)

        if user is not None:
            ent = self.db.query_one("SELECT * FROM entitlements WHERE user_id=?", (user["id"],))
            paid_until = ent["paid_until"] if ent else None
            is_paid = bool(paid_until and paid_until > now_iso())
            if is_paid:
                return Identity("paid", user["id"], user["email"], None, None, None, True)
            # trial
            remaining = max(0, ent["trial_limit"] - ent["trial_used"]) if ent else 0
            return Identity("trial", user["id"], user["email"], None, remaining, ent["trial_limit"] if ent else None, False)

        # anonymous
        device_id = (request.headers.get("x-device-id") or "").strip()[:128] or None
        if not device_id:
            # No device id => treat as fresh but capped single-session; still allow check.
            return Identity("anonymous", None, None, None, self.settings.anonymous_grace_limit, self.settings.anonymous_grace_limit, False)
        return Identity("anonymous", None, None, device_id, self._anon_remaining(device_id), self.settings.anonymous_grace_limit, False)

    def consume(self, identity: Identity) -> None:
        if identity.kind == "paid":
            return
        if identity.kind == "trial":
            identity.remaining = self._consume_trial(identity.user_id)
            return
        # anonymous
        if identity.device_id:
            self._consume_anon(identity.device_id)
            identity.remaining = self._anon_remaining(identity.device_id)
        else:
            if (identity.remaining or 0) <= 0:
                raise HTTPException(status_code=402, detail="Free checks exhausted. Create an account to continue.")
            identity.remaining = max(0, (identity.remaining or 1) - 1)

    def _user_from_token(self, token: str):
        row = self.db.query_one(
            "SELECT u.id, u.email, s.expires_at FROM sessions s JOIN users u ON u.id=s.user_id "
            "WHERE s.token_hash=?",
            (_token_hash(token),),
        )
        if not row:
            return None
        if row["expires_at"] <= now_iso():
            self.db.rowcount_execute("DELETE FROM sessions WHERE token_hash=?", (_token_hash(token),))
            return None
        return {"id": row["id"], "email": row["email"]}

    # -- session issuance --
    def create_session(self, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        expires = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        self.db.execute(
            "INSERT INTO sessions(token_hash, user_id, created_at, expires_at) VALUES(?,?,?,?)",
            (_token_hash(token), user_id, now_iso(), expires),
        )
        return token

    def revoke_session(self, authorization: str | None) -> None:
        if authorization and authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1].strip()
            self.db.rowcount_execute("DELETE FROM sessions WHERE token_hash=?", (_token_hash(token),))


# --- FastAPI dependencies --------------------------------------------------
def get_quota(request: Request) -> QuotaService:
    return request.app.state.quota


def current_identity(
    request: Request,
    quota: QuotaService = Depends(get_quota),
    authorization: str | None = Header(default=None),
) -> Identity:
    return quota.resolve(request, authorization)


def require_analysis_quota(
    identity: Identity = Depends(current_identity),
    quota: QuotaService = Depends(get_quota),
) -> Identity:
    """Consumes one credit (anon/trial) or passes for paid. Use on analyze."""
    quota.consume(identity)
    return identity


def require_pro(identity: Identity = Depends(current_identity)) -> Identity:
    if not identity.can_bulk_scan:
        raise HTTPException(status_code=403, detail="Bulk inbox scanning is a Pro feature.")
    return identity


def require_login(identity: Identity = Depends(current_identity)):
    if identity.user_id is None:
        raise HTTPException(status_code=401, detail="Sign in required.")
    return identity
