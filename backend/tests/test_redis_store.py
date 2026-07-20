"""Session store & rate limiter tests against fakeredis (research R9, US3).

``fakeredis.FakeAsyncRedis`` is injected via the client factory — no real
Redis, no connections at import/construct time.
"""

import asyncio

import fakeredis
import pytest

from exambrain_shared.config import Settings
from exambrain_shared.errors import NotConfiguredError
from exambrain_shared.redis import RateLimiter, SessionStore

CONFIGURED = Settings(_env_file=None, redis_url="redis://localhost:6379/0")
EMPTY = Settings(_env_file=None, redis_url=None)


@pytest.fixture
def fake_server() -> fakeredis.FakeServer:
    return fakeredis.FakeServer()


@pytest.fixture
def store(fake_server: fakeredis.FakeServer) -> SessionStore:
    return SessionStore(
        CONFIGURED,
        client_factory=lambda url: fakeredis.FakeAsyncRedis(server=fake_server),
    )


@pytest.fixture
def limiter(fake_server: fakeredis.FakeServer) -> RateLimiter:
    return RateLimiter(
        CONFIGURED,
        client_factory=lambda url: fakeredis.FakeAsyncRedis(server=fake_server),
    )


async def test_session_round_trip(store: SessionStore) -> None:
    value = {"timer": 1800, "violations": 0, "buffer": {"q1": "answer"}}
    await store.set_session("exam-123", value, ttl_seconds=60)
    assert await store.get_session("exam-123") == value
    await store.delete_session("exam-123")
    assert await store.get_session("exam-123") is None


async def test_ttl_expiry_returns_none(
    store: SessionStore, fake_server: fakeredis.FakeServer
) -> None:
    await store.set_session("exam-x", {"a": 1}, ttl_seconds=5)
    assert await store.get_session("exam-x") is not None
    async with fakeredis.FakeAsyncRedis(server=fake_server) as probe:
        ttl = await probe.ttl("session:exam-x")
        assert 0 < ttl <= 5  # server-side TTL was set
        # Shrink the TTL to expire the key almost immediately.
        await probe.pexpire("session:exam-x", 10)
    await asyncio.sleep(0.05)
    assert await store.get_session("exam-x") is None


async def test_absent_key_returns_none_never_raises(store: SessionStore) -> None:
    assert await store.get_session("never-set") is None


async def test_concurrent_writes_last_writer_wins(store: SessionStore) -> None:
    values = [{"n": i} for i in range(10)]
    await asyncio.gather(*(store.set_session("k", v, ttl_seconds=60) for v in values))
    final = await store.get_session("k")
    assert final in values  # one complete JSON document


async def test_rate_limiter_threshold_exact(limiter: RateLimiter) -> None:
    """N allowed, N+1th denied within one window (SC-005)."""
    threshold = 5
    for i in range(threshold):
        result = await limiter.check(
            "user-1:gen", threshold=threshold, window_seconds=60
        )
        assert result.allowed, f"call {i + 1} should be allowed"
        assert result.current_count == i + 1
    denied = await limiter.check("user-1:gen", threshold=threshold, window_seconds=60)
    assert not denied.allowed
    assert denied.current_count == threshold + 1


async def test_rate_limiter_concurrent_increments_atomic(
    limiter: RateLimiter,
) -> None:
    results = await asyncio.gather(
        *(limiter.check("scope", threshold=10, window_seconds=60) for _ in range(20))
    )
    counts = sorted(r.current_count for r in results)
    assert counts == list(range(1, 21))  # every increment observed exactly once
    assert sum(1 for r in results if r.allowed) == 10


async def test_not_configured_raises_before_client_creation() -> None:
    def _explode(url: str) -> object:
        raise AssertionError("client factory must not be called")

    store = SessionStore(EMPTY, client_factory=_explode)
    limiter = RateLimiter(EMPTY, client_factory=_explode)
    with pytest.raises(NotConfiguredError, match="Redis"):
        await store.set_session("k", {}, ttl_seconds=1)
    with pytest.raises(NotConfiguredError):
        await store.get_session("k")
    with pytest.raises(NotConfiguredError):
        await limiter.check("s", threshold=1, window_seconds=1)


def test_no_connection_at_import_or_construct() -> None:
    calls: list[str] = []
    SessionStore(CONFIGURED, client_factory=lambda url: calls.append(url))
    RateLimiter(CONFIGURED, client_factory=lambda url: calls.append(url))
    assert calls == []  # lazy: factory untouched until first operation
