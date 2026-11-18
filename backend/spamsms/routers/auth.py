"""Registration, login, logout, and current-user endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from ..schemas import AuthResponse, LoginRequest, RegisterRequest, UserOut
from ..security import (
    Identity,
    current_identity,
    hash_password,
    now_iso,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _plan_label(ent) -> str:
    paid_until = ent["paid_until"] if ent else None
    if paid_until and paid_until > now_iso():
        return "pro"
    return "trial"


def _user_out(db, user_id: int) -> UserOut:
    u = db.query_one("SELECT id, email FROM users WHERE id=?", (user_id,))
    ent = db.query_one("SELECT * FROM entitlements WHERE user_id=?", (user_id,))
    return UserOut(
        id=u["id"],
        email=u["email"],
        plan=_plan_label(ent),
        trial_used=ent["trial_used"] if ent else 0,
        trial_limit=ent["trial_limit"] if ent else 0,
        paid_until=ent["paid_until"] if ent else None,
    )


@router.post("/register", response_model=AuthResponse, status_code=201)
def register(body: RegisterRequest, request: Request):
    db = request.app.state.db
    settings = request.app.state.settings
    email = body.email.lower().strip()
    if db.query_one("SELECT id FROM users WHERE email=?", (email,)):
        raise HTTPException(status_code=409, detail="An account with that email already exists.")
    password_hash = hash_password(body.password)
    trial_ends = (datetime.now(timezone.utc) + timedelta(days=settings.trial_days)).isoformat()

    def _tx(conn):
        cur = conn.execute(
            "INSERT INTO users(email, password_hash, created_at) VALUES(?,?,?)",
            (email, password_hash, now_iso()),
        )
        user_id = cur.lastrowid
        conn.execute(
            "INSERT INTO entitlements(user_id, trial_used, trial_limit, trial_ends_at) VALUES(?,?,?,?)",
            (user_id, 0, settings.trial_analyses, trial_ends),
        )
        return user_id

    user_id = db.transaction(_tx)
    token = request.app.state.quota.create_session(user_id)
    return AuthResponse(token=token, user=_user_out(db, user_id))


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest, request: Request):
    db = request.app.state.db
    email = body.email.lower().strip()
    row = db.query_one("SELECT id, password_hash FROM users WHERE email=?", (email,))
    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    token = request.app.state.quota.create_session(row["id"])
    return AuthResponse(token=token, user=_user_out(db, row["id"]))


@router.post("/logout")
def logout(request: Request, authorization: str | None = Header(default=None)):
    request.app.state.quota.revoke_session(authorization)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(identity: Identity = Depends(current_identity), request: Request = None):
    if identity.user_id is None:
        raise HTTPException(status_code=401, detail="Sign in required.")
    return _user_out(request.app.state.db, identity.user_id)
