"""Pytest fixtures + a session-wide egress block that proves offline-first.

Async is driven with asyncio.run inside plain sync tests (pytest-asyncio is not
installable here). The egress guard rejects any socket connect to a non-local
address, so if any code path tries to phone home during tests it fails loudly.
"""

from __future__ import annotations

import socket

import pytest

_ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1", "test", ""}
_real_connect = socket.socket.connect


def _guarded_connect(self, addr, *args, **kwargs):
    host = addr[0] if isinstance(addr, tuple) else addr
    if isinstance(host, str) and host not in _ALLOWED_HOSTS:
        raise AssertionError("TEST attempted outbound network connect to {!r}".format(addr))
    return _real_connect(self, addr, *args, **kwargs)


@pytest.fixture(scope="session", autouse=True)
def block_egress():
    real_create = socket.create_connection

    def guarded_create(address, *a, **k):
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host not in _ALLOWED_HOSTS:
            raise AssertionError("TEST attempted create_connection to {!r}".format(address))
        return real_create(address, *a, **k)

    socket.socket.connect = _guarded_connect
    socket.create_connection = guarded_create
    try:
        yield
    finally:
        socket.socket.connect = _real_connect
        socket.create_connection = real_create


@pytest.fixture()
def settings_factory(tmp_path):
    from spamsms.config import Settings

    def make(**overrides):
        db = overrides.pop("database_path", ":memory:")
        base = dict(database_path=db, anonymous_grace_limit=3, trial_analyses=5, cors_origins=[])
        base.update(overrides)
        return Settings(**base)

    return make


class _LoopRunner:
    """Runs coroutines on a dedicated background event-loop thread.

    Needed because the FastAPI lifespan context manager is async-only and must
    stay entered across all requests in a test; asyncio.run per-call would tear
    the loop down between requests. One shared loop also lets gather() exercise
    true await-point interleaving (the trial double-spend race).
    """

    def __init__(self):
        import asyncio
        import threading

        self._asyncio = asyncio
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self._thread.start()

    def run(self, coro):
        return self._asyncio.run_coroutine_threadsafe(coro, self.loop).result()

    def stop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join(timeout=2)


@pytest.fixture()
def runner():
    r = _LoopRunner()
    try:
        yield r
    finally:
        r.stop()


@pytest.fixture()
def app(runner, settings_factory):
    """App with its lifespan entered on the shared loop; yields (app, runner)."""
    from spamsms.main import create_app

    application = create_app(settings_factory())
    ctx = application.router.lifespan_context(application)
    runner.run(ctx.__aenter__())
    try:
        yield application
    finally:
        runner.run(ctx.__aexit__(None, None, None))


@pytest.fixture()
def client(app, runner):
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)

    class SyncClient:
        def _request(self, method, url, **kw):
            async def go():
                async with AsyncClient(transport=transport, base_url="http://test") as c:
                    return await c.request(method, url, **kw)
            return runner.run(go())

        def request(self, method, url, **kw):
            return self._request(method, url, **kw)

        def gather(self, calls):
            """calls: list of (method, url, kwargs) run concurrently on one loop."""
            import asyncio

            async def go():
                async with AsyncClient(transport=transport, base_url="http://test") as c:
                    return await asyncio.gather(*[c.request(m, u, **k) for m, u, k in calls])

            return runner.run(go())

        def get(self, url, **kw): return self.request("GET", url, **kw)
        def post(self, url, **kw): return self.request("POST", url, **kw)

    return SyncClient()
