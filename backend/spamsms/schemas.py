"""Pydantic request/response models.

Note: no EmailStr (needs email-validator, unavailable here) — email is validated
with a bounded regex pattern instead.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

EMAIL_PATTERN = r"^[^@\s]{1,64}@[^@\s.]+(\.[^@\s.]+)+$"


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    device_id: str | None = Field(default=None, max_length=128)


class Driver(BaseModel):
    word: str
    impact: float


class Signal(BaseModel):
    title: str
    detail: str
    severity: Literal["high", "caution"]


class AnalyzeResponse(BaseModel):
    label: Literal["SPAM", "HAM", "UNSURE"]
    spam_probability: float
    matched_vocabulary_terms: int
    drivers: list[Driver]
    signals: list[Signal]
    domains: list[str]
    quota: "QuotaStatus"


class QuotaStatus(BaseModel):
    kind: Literal["anonymous", "trial", "paid", "pro"]
    remaining: int | None
    limit: int | None
    pays_wall: bool


class RegisterRequest(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN)
    password: str = Field(min_length=1, max_length=128)


class AuthResponse(BaseModel):
    token: str
    user: "UserOut"


class UserOut(BaseModel):
    id: int
    email: str
    plan: Literal["trial", "pro"]
    trial_used: int
    trial_limit: int
    paid_until: str | None


class ScanSummary(BaseModel):
    scanned: int
    spam: int
    ham: int
    unsure: int
    top_signals: list[tuple[str, int]]


class ScanRow(BaseModel):
    index: int
    message: str
    label: Literal["SPAM", "HAM", "UNSURE"]
    spam_probability: float
    trigger_words: list[str]
    safety_signals: list[str]


class ScanResponse(BaseModel):
    summary: ScanSummary
    rows: list[ScanRow]
    truncated: bool


class CheckoutRequest(BaseModel):
    plan: Literal["pro_monthly"] = "pro_monthly"


class CheckoutResponse(BaseModel):
    provider: Literal["mock", "stripe"]
    url: str
    session_id: str


class EntitlementResponse(BaseModel):
    plan: Literal["free", "trial", "pro"]
    anonymous_remaining: int | None
    trial_remaining: int | None
    paid_until: str | None
    can_bulk_scan: bool


AuthResponse.model_rebuild()
AnalyzeResponse.model_rebuild()
