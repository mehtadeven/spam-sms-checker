"""Checkout creation, entitlement status, and Stripe webhook handling.

Webhook: verifies signature over RAW bytes, dedupes by event id (idempotent),
then grants entitlement from the verified payload's client_reference_id. Never
calls Session.retrieve in the handler (avoids network + is the common bug).
Mock provider completes locally with zero keys/network.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from ..schemas import CheckoutRequest, CheckoutResponse, EntitlementResponse
from ..security import Identity, current_identity, now_iso

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.get("/status", response_model=EntitlementResponse)
def status(request: Request, identity: Identity = Depends(current_identity)):
    settings = request.app.state.settings
    if identity.kind == "paid":
        ent = request.app.state.db.query_one(
            "SELECT paid_until FROM entitlements WHERE user_id=?", (identity.user_id,)
        )
        return EntitlementResponse(
            plan="pro", anonymous_remaining=None, trial_remaining=None,
            paid_until=ent["paid_until"] if ent else None, can_bulk_scan=True,
        )
    if identity.kind == "trial":
        return EntitlementResponse(
            plan="trial", anonymous_remaining=None, trial_remaining=identity.remaining,
            paid_until=None, can_bulk_scan=False,
        )
    return EntitlementResponse(
        plan="free", anonymous_remaining=identity.remaining, trial_remaining=None,
        paid_until=None, can_bulk_scan=False,
    )


@router.post("/checkout", response_model=CheckoutResponse)
def checkout(body: CheckoutRequest, request: Request, identity: Identity = Depends(current_identity)):
    if identity.user_id is None:
        raise HTTPException(status_code=401, detail="Create an account before subscribing.")
    billing = request.app.state.billing
    try:
        result = billing.create_checkout(
            user_id=identity.user_id, email=identity.email or "", plan=body.plan
        )
    except Exception as exc:  # BillingError or surfaced Stripe error
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return CheckoutResponse(**result)


@router.post("/mock/complete")
def mock_complete(request: Request, session_id: str):
    """Dev-only: simulates a successful Stripe payment for the mock provider."""
    billing = request.app.state.billing
    if getattr(billing, "name", "") != "mock":
        raise HTTPException(status_code=404, detail="Mock completion is disabled when Stripe is configured.")
    outcome = billing.complete(session_id)
    if outcome is None:
        raise HTTPException(status_code=404, detail="Unknown or already-completed session.")
    return {"ok": True, "paid_until": outcome["paid_until"]}


@router.post("/webhook")
async def stripe_webhook(request: Request, stripe_signature: str | None = Header(default=None)):
    billing = request.app.state.billing
    if getattr(billing, "name", "") != "stripe":
        raise HTTPException(status_code=404, detail="Webhook active only with Stripe configured.")
    body_bytes = await request.body()  # RAW bytes — required for HMAC verification
    try:
        event = billing.construct_event(body_bytes, stripe_signature)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid signature or payload.")

    # construct_event returns a stripe Event resource, not a plain dict.
    event = event.to_dict() if hasattr(event, "to_dict") else dict(event)
    db = request.app.state.db
    event_id = event["id"]
    event_type = event["type"]

    # Idempotency: record first, apply after. Duplicate delivery => rowcount 0.
    def _tx(conn):
        cur = conn.execute(
            "INSERT INTO stripe_events(id, type, received_at) VALUES(?,?,?) "
            "ON CONFLICT(id) DO NOTHING",
            (event_id, event_type, now_iso()),
        )
        return cur.rowcount

    inserted = db.transaction(_tx)
    if inserted == 0:
        return JSONResponse({"received": True, "duplicate": True}, status_code=200)

    obj = event.get("data", {}).get("object", {})
    client_ref = obj.get("client_reference_id") if hasattr(obj, "get") else getattr(obj, "client_reference_id", None)
    if event_type == "checkout.session.completed" and client_ref:
        uid = int(client_ref)
        billing.apply_paid(db, uid, months=1)
    elif event_type in {"customer.subscription.deleted", "invoice.payment_failed"}:
        pass  # revoke handled by subscription status polling in a fuller impl

    return JSONResponse({"received": True}, status_code=200)
