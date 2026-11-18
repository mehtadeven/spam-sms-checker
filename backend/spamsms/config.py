"""Application settings loaded from environment / .env via pydantic-settings.

Settings are read through a cached factory (get_settings) so tests can clear the
cache and point at a temp DB instead of freezing values at import time.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_db_path() -> str:
    """Prefer %LOCALAPPDATA% over a repo-relative path (WAL + gitignore safety)."""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return str(Path(base) / "spamsms" / "spamsms.db")
    return str(Path.home() / ".spamsms" / "spamsms.db")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "SpamSMS Guardian"
    environment: str = Field(default="development")

    # --- Persistence ---
    database_path: str = Field(default_factory=_default_db_path)

    # --- Entitlements ---
    anonymous_grace_limit: int = 10          # free checks before signup
    trial_days: int = 14
    trial_analyses: int = 200                # generous cap during trial
    max_scan_rows: int = 10000
    max_scan_bytes: int = 2 * 1024 * 1024    # 2 MiB CSV body cap

    # --- Rate limiting (token bucket, per IP+user) ---
    rate_limit_per_minute: int = 60

    # --- CORS (empty by default; dev uses Vite proxy, prod is same-origin) ---
    cors_origins: list[str] = []

    # --- Billing: mock unless a real Stripe secret key is present ---
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_price_id: str | None = None       # subscription Price id from dashboard
    billing_provider_override: str | None = None  # "mock" | "stripe" to force

    # Frontend origin used for Stripe redirect URLs
    frontend_origin: str = "http://localhost:5173"

    @property
    def billing_provider(self) -> str:
        if self.billing_provider_override:
            return self.billing_provider_override
        return "stripe" if self.stripe_secret_key else "mock"

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"prod", "production"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
