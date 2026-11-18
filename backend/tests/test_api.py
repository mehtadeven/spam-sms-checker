"""API tests: auth, entitlement gating, billing funnel, offline guarantee.

All run under the session egress block (conftest.block_egress), so any accidental
network call fails the suite — this is the executable proof of offline-first.
"""

from __future__ import annotations

import pytest

SPAM = "URGENT win a prize now https://bit.ly/x"


def _register(client, email="u@v.com", password="password1"):
    r = client.post("/api/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    return r.json()["token"]


class TestHealthAndAnalyze:
    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200 and r.json()["provider"] == "mock"

    def test_analyze_spam(self, client):
        r = client.post("/api/analyze", json={"text": SPAM}, headers={"x-device-id": "d"})
        assert r.status_code == 200
        assert r.json()["label"] == "SPAM"


class TestAnonymousGrace:
    def test_grace_then_paywall(self, client):
        codes = [
            client.post("/api/analyze", json={"text": SPAM}, headers={"x-device-id": "dev"}).status_code
            for _ in range(5)
        ]
        assert codes == [200, 200, 200, 402, 402]  # limit=3 from settings fixture


class TestAuth:
    def test_login_wrong_password(self, client):
        _register(client)
        r = client.post("/api/auth/login", json={"email": "u@v.com", "password": "nope"})
        assert r.status_code == 401

    def test_duplicate_email(self, client):
        _register(client)
        r = client.post("/api/auth/register", json={"email": "u@v.com", "password": "another1"})
        assert r.status_code == 409

    def test_me_requires_token(self, client):
        assert client.get("/api/auth/me").status_code == 401
        tok = _register(client)
        r = client.get("/api/auth/me", headers={"authorization": "Bearer " + tok})
        assert r.status_code == 200 and r.json()["plan"] == "trial"

    def test_bad_email_rejected(self, client):
        r = client.post("/api/auth/register", json={"email": "not-an-email", "password": "password1"})
        assert r.status_code == 422


class TestTrialConcurrency:
    def test_no_double_spend(self, client):
        """20 concurrent analyses for one trial user (limit=5) => exactly 5 succeed."""
        tok = _register(client, email="race@v.com")
        h = {"authorization": "Bearer " + tok}
        responses = client.gather(
            [("POST", "/api/analyze", {"json": {"text": SPAM}, "headers": h})] * 20
        )
        ok = sum(1 for r in responses if r.status_code == 200)
        paid_wall = sum(1 for r in responses if r.status_code == 402)
        assert ok == 5, "expected exactly trial_limit successes, got %d" % ok
        assert paid_wall == 15


class TestBillingFunnel:
    def test_scan_gated_until_pro(self, client):
        tok = _register(client, email="p@v.com")
        h = {"authorization": "Bearer " + tok}
        csv_body = b"message\n" + SPAM.encode() + b"\nAre we meeting lunch tomorrow?\n"
        pre = client.post("/api/scan", content=csv_body, headers={**h, "content-type": "text/csv"})
        assert pre.status_code == 403

        checkout = client.post("/api/billing/checkout", json={"plan": "pro_monthly"}, headers=h)
        assert checkout.status_code == 200 and checkout.json()["provider"] == "mock"
        sid = checkout.json()["session_id"]
        done = client.post("/api/billing/mock/complete?session_id=" + sid, headers=h)
        assert done.status_code == 200

        post = client.post("/api/scan", content=csv_body, headers={**h, "content-type": "text/csv"})
        assert post.status_code == 200
        summary = post.json()["summary"]
        assert summary["scanned"] == 2
        assert summary["spam"] == 1

    def test_mock_complete_unknown_session(self, client):
        tok = _register(client, email="q@v.com")
        r = client.post("/api/billing/mock/complete?session_id=nope", headers={"authorization": "Bearer " + tok})
        assert r.status_code == 404


class TestOfflineFirst:
    def test_full_flow_needs_no_network(self, client):
        # Runs signup -> trial -> paywall -> mock pay -> pro scan entirely offline.
        # The autouse egress guard would fail the test on any outbound connect.
        tok = _register(client, email="off@v.com")
        h = {"authorization": "Bearer " + tok}
        assert client.post("/api/analyze", json={"text": SPAM}, headers=h).status_code == 200
        co = client.post("/api/billing/checkout", json={"plan": "pro_monthly"}, headers=h)
        client.post("/api/billing/mock/complete?session_id=" + co.json()["session_id"], headers=h)
        r = client.post("/api/scan", content=b"message\nok\n", headers={**h, "content-type": "text/csv"})
        assert r.status_code == 200
