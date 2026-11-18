"""Stripe webhook correctness tested offline: local HMAC signature verification
and event-id idempotency. No network — we sign the payload ourselves and feed it
through construct_event with a mock secret.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest


def _sign(payload_bytes: bytes, secret: str) -> str:
    timestamp = int(time.time())
    body_sig = "{}.{}".format(timestamp, payload_bytes.decode())
    v1 = hmac.new(secret.encode(), body_sig.encode(), hashlib.sha256).hexdigest()
    return "t={},v1={}".format(timestamp, v1)


@pytest.fixture()
def stripe_env(runner, settings_factory):
    """Returns (client, db, make_user) with lifespan entered on the shared loop."""
    from spamsms.main import create_app
    from spamsms.security import now_iso
    from httpx import ASGITransport, AsyncClient

    settings = settings_factory(
        billing_provider_override="stripe",
        stripe_secret_key="sk_test_dummy",
        stripe_webhook_secret="whsec_test",
    )
    app = create_app(settings)
    ctx = app.router.lifespan_context(app)
    runner.run(ctx.__aenter__())
    try:
        transport = ASGITransport(app=app)

        class C:
            def post(self, url, **kw):
                async def go():
                    async with AsyncClient(transport=transport, base_url="http://test") as c:
                        return await c.post(url, **kw)
                return runner.run(go())

        db = app.state.db

        def make_user(email):
            uid = db.execute(
                "INSERT INTO users(email,password_hash,created_at) VALUES(?,?,?)",
                (email, "x", now_iso()),
            )
            db.execute(
                "INSERT INTO entitlements(user_id,trial_used,trial_limit) VALUES(?,0,5)",
                (uid,),
            )
            return uid

        yield C(), db, make_user
    finally:
        runner.run(ctx.__aexit__(None, None, None))


def _paid_until(db, user_id):
    row = db.query_one("SELECT paid_until FROM entitlements WHERE user_id=?", (user_id,))
    return row["paid_until"] if row else None


def _completed_event(user_id: int, event_id="evt_1"):
    return json.dumps({
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {"object": {"client_reference_id": str(user_id), "status": "complete"}},
    }).encode()


def test_valid_signature_grants_pro(stripe_env):
    client, db, make_user = stripe_env
    uid = make_user("hook@v.com")
    payload = _completed_event(uid)
    sig = _sign(payload, "whsec_test")
    r = client.post("/api/billing/webhook", content=payload, headers={"stripe-signature": sig, "content-type": "application/json"})
    assert r.status_code == 200, r.text
    assert _paid_until(db, uid) is not None  # entitlement actually granted


def test_bad_signature_rejected(stripe_env):
    client, db, make_user = stripe_env
    uid = make_user("bad@v.com")
    payload = _completed_event(uid, event_id="evt_bad")
    r = client.post("/api/billing/webhook", content=payload, headers={"stripe-signature": "t=1,v1=deadbeef", "content-type": "application/json"})
    assert r.status_code == 400
    assert _paid_until(db, uid) is None  # no grant on bad signature


def test_duplicate_event_is_idempotent(stripe_env):
    client, db, make_user = stripe_env
    uid = make_user("dup@v.com")
    payload = _completed_event(uid, event_id="evt_dup")
    sig = _sign(payload, "whsec_test")
    h = {"stripe-signature": sig, "content-type": "application/json"}
    first = client.post("/api/billing/webhook", content=payload, headers=h)
    second = client.post("/api/billing/webhook", content=payload, headers=h)
    assert first.status_code == 200
    assert second.json().get("duplicate") is True
