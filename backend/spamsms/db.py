"""Stdlib sqlite3 persistence layer.

No SQLAlchemy (cannot install on this Python without a C toolchain). One
connection is reused per process. Writes that must be atomic (trial spend,
webhook idempotency) run inside an explicit BEGIN IMMEDIATE guarded by a
process-local lock; busy_timeout handles cross-process contention under WAL.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    stripe_customer_id TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entitlements (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    trial_used INTEGER NOT NULL DEFAULT 0,
    trial_limit INTEGER NOT NULL,
    trial_ends_at TEXT,
    paid_until TEXT
);

-- Anonymous (pre-signup) grace tracking, keyed by a client device id.
CREATE TABLE IF NOT EXISTS anonymous_usage (
    device_id TEXT PRIMARY KEY,
    used INTEGER NOT NULL DEFAULT 0,
    first_seen_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_hash TEXT NOT NULL UNIQUE,
    label TEXT,
    created_at TEXT NOT NULL,
    revoked INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS stripe_events (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    received_at TEXT NOT NULL,
    payload_hash TEXT
);

-- Mock-provider checkout sessions (offline demo ledger).
CREATE TABLE IF NOT EXISTS mock_sessions (
    session_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    plan TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_apikeys_user ON api_keys(user_id);
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False + our own lock lets one connection serve the
        # threadpool safely. isolation_level=None => manual transaction control.
        self._conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False, timeout=5.0)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._configure()

    def _configure(self) -> None:
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._conn.executescript(SCHEMA)

    # --- read helpers (autocommit; single statements are consistent) ---
    def query_one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        with self._lock:
            cur = self._conn.execute(sql, params)
            return cur.fetchone()

    def query_all(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            cur = self._conn.execute(sql, params)
            return cur.fetchall()

    # --- write helpers ---
    def execute(self, sql: str, params: tuple = ()) -> int:
        """Single-statement write. Returns lastrowid."""
        with self._lock:
            cur = self._conn.execute(sql, params)
            return cur.lastrowid or 0

    def rowcount_execute(self, sql: str, params: tuple = ()) -> int:
        """Single-statement write returning affected row count (for guards)."""
        with self._lock:
            cur = self._conn.execute(sql, params)
            return cur.rowcount

    def transaction(self, fn):
        """Run fn(conn) inside BEGIN IMMEDIATE ... COMMIT under the lock.

        fn may call conn.execute and inspect .rowcount for atomic guard-and-write
        patterns (e.g. trial spend). Rolls back on any exception.
        """
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                result = fn(self._conn)
                self._conn.execute("COMMIT")
                return result
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise

    def close(self) -> None:
        with self._lock:
            self._conn.close()
