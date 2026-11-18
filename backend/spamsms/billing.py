"""Billing providers behind one interface.

MockProvider (default): fully offline, drives the entire upgrade funnel with no
keys and no network. StripeProvider: real Checkout Sessions + webhook signature
verification. This is the ONLY module allowed to touch the network, and it does
so lazily inside methods — never at import time. analyze/scan/auth must not
import stripe.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from .security import now_iso


class BillingError(Exception):
    pass


class BillingProvider:
    name = "base"

    def create_checkout(self, *, user_id: int, email: str, plan: str) -> dict:
        raise NotImplementedError

    def apply_paid(self, db, user_id: int, months: int = 1) -> str:
        """Extend paid_until by N months atomically; returns new paid_until."""
        def _tx(conn):
            row = conn.execute("SELECT paid_until FROM entitlements WHERE user_id=?", (user_id,)).fetchone()
            current = row["paid_until"] if row and row["paid_until"] else None
            base = datetime.now(timezone.utc)
            if current and current > base.isoformat():
                base = datetime.fromisoformat(current)
            new_paid = (base + timedelta(days=30 * months)).isoformat()
            conn.execute("UPDATE entitlements SET paid_until=? WHERE user_id=?", (new_paid, user_id))
            return new_paid
        return db.transaction(_tx)


class MockProvider(BillingProvider):
    name = "mock"

    def __init__(self, settings, db):
        self.settings = settings
        self.db = db

    def create_checkout(self, *, user_id: int, email: str, plan: str) -> dict:
        session_id = "mockcs_" + secrets.token_urlsafe(16)
        self.db.execute(
            "INSERT INTO mock_sessions(session_id, user_id, plan, status, created_at) VALUES(?,?,?,?,?)",
            (session_id, user_id, plan, "pending", now_iso()),
        )
        # SPA renders a "Simulate successful payment" button on this route.
        url = "{}/checkout/mock?session_id={}".format(self.settings.frontend_origin.rstrip("/"), session_id)
        return {"provider": "mock", "url": url, "session_id": session_id}

    def complete(self, session_id: str) -> dict | None:
        row = self.db.query_one(
            "SELECT * FROM mock_sessions WHERE session_id=? AND status='pending'", (session_id,)
        )
        if not row:
            return None
        self.db.execute("UPDATE mock_sessions SET status='paid' WHERE session_id=?", (session_id,))
        paid_until = self.apply_paid(self.db, row["user_id"], months=1)
        return {"user_id": row["user_id"], "paid_until": paid_until}


class StripeProvider(BillingProvider):
    name = "stripe"

    def __init__(self, settings, db):
        self.settings = settings
        self.db = db

    def _client(self):
        import stripe  # lazy: never imported unless a real key is configured
        stripe.api_key = self.settings.stripe_secret_key
        return stripe

    def create_checkout(self, *, user_id: int, email: str, plan: str) -> dict:
        if not self.settings.stripe_price_id:
            raise BillingError("STRIPE_PRICE_ID is not configured.")
        stripe = self._client()
        customer_id = self._ensure_customer(user_id, email)
        try:
            session = stripe.checkout.Session.create(
                mode="subscription",
                customer=customer_id,
                client_reference_id=str(user_id),
                metadata={"user_id": str(user_id)},
                line_items=[{"price": self.settings.stripe_price_id, "quantity": 1}],
                success_url=self.settings.frontend_origin.rstrip("/") + "/account?upgraded=1",
                cancel_url=self.settings.frontend_origin.rstrip("/") + "/pricing?canceled=1",
                adapter="urllib",
            )
        except Exception as exc:  # surface, don't swallow into a fake success
            raise BillingError("Stripe checkout failed: {}".format(exc)) from exc
        return {"provider": "stripe", "url": session.url, "session_id": session.id}

    def _ensure_customer(self, user_id: int, email: str) -> str:
        row = self.db.query_one("SELECT stripe_customer_id FROM users WHERE id=?", (user_id,))
        if row and row["stripe_customer_id"]:
            return row["stripe_customer_id"]
        stripe = self._client()
        customer = stripe.Customer.create(email=email, metadata={"user_id": str(user_id)})
        self.db.execute("UPDATE users SET stripe_customer_id=? WHERE id=?", (customer.id, user_id))
        return customer.id

    def construct_event(self, payload_bytes: bytes, sig_header: str | None):
        if not self.settings.stripe_webhook_secret:
            raise BillingError("STRIPE_WEBHOOK_SECRET is not configured.")
        stripe = self._client()
        # RAW bytes required; re-serialized JSON fails HMAC verification.
        return stripe.Webhook.construct_event(
            payload_bytes, sig_header, self.settings.stripe_webhook_secret, tolerance=300
        )


def get_billing(settings, db) -> BillingProvider:
    """Factory chosen once at startup by config, never per-request."""
    if settings.billing_provider == "stripe":
        return StripeProvider(settings, db)
    return MockProvider(settings, db)


def payload_hash(payload_bytes: bytes) -> str:
    return hashlib.sha256(payload_bytes).hexdigest()
