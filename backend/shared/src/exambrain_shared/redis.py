"""Async Redis session store and fixed-window rate limiter (US3).

Follows the deferred-error pattern: no client creation at import or
``__init__`` time; the client is built lazily on first operation via
``redis.asyncio.Redis.from_url`` (FR-013). Missing configuration raises
:class:`NotConfiguredError` at call time; an unreachable Redis surfaces
the underlying connection error at call time only.
"""

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis

from exambrain_shared.config import Settings, get_settings
from exambrain_shared.errors import NotConfiguredError

ClientFactory = Callable[[str], Any]


def _default_client_factory(url: str) -> "Redis":
    return Redis.from_url(url)


class _LazyRedisBase:
    """Shared lazy-client plumbing for SessionStore and RateLimiter."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._client_factory = client_factory or _default_client_factory
        self._client: Any = None

    @property
    def is_configured(self) -> bool:
        return bool(self._settings.redis_url)

    def _get_client(self) -> Any:
        """Return the Redis client, creating it lazily on first use."""
        if not self.is_configured:
            raise NotConfiguredError("Redis", "set REDIS_URL")
        if self._client is None:
            assert self._settings.redis_url is not None
            self._client = self._client_factory(self._settings.redis_url)
        return self._client

    async def aclose(self) -> None:
        """Release pooled connections, if a client was ever created."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None


class SessionStore(_LazyRedisBase):
    """JSON session state with server-enforced TTL (FR-011)."""

    @staticmethod
    def _key(session_id: str) -> str:
        return f"session:{session_id}"

    async def set_session(
        self, session_id: str, value: dict[str, Any], ttl_seconds: int
    ) -> None:
        """Store a session document with per-entry TTL (atomic SET .. EX)."""
        client = self._get_client()
        await client.set(self._key(session_id), json.dumps(value), ex=ttl_seconds)

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Return the session document, or ``None`` if absent/expired/evicted."""
        client = self._get_client()
        raw = await client.get(self._key(session_id))
        if raw is None:
            return None
        decoded: dict[str, Any] = json.loads(raw)
        return decoded

    async def delete_session(self, session_id: str) -> None:
        """Remove a session; deleting an absent key is a no-op."""
        client = self._get_client()
        await client.delete(self._key(session_id))


class AttemptStateCache(_LazyRedisBase):
    """Redis read/write cache for live attempt polling (005-exam-simulation).

    Write-through: on answer save, update PG + refresh cache.
    Read-through: on poll, read cache; on miss, read PG and repopulate.
    Invalidate: on finish/lockout/expiry, delete cache key.
    """

    @staticmethod
    def _key(attempt_id: str) -> str:
        return f"attempt:{attempt_id}:state"

    async def set_state(
        self,
        attempt_id: str,
        *,
        status: str,
        remaining_seconds: int,
        focus_violations: int,
        answers: dict[str, str],
        deadline: str,
        ttl_seconds: int,
    ) -> None:
        client = self._get_client()
        await client.hset(
            self._key(attempt_id),
            mapping={
                "status": status,
                "remaining_seconds": str(remaining_seconds),
                "focus_violations": str(focus_violations),
                "answers": json.dumps(answers),
                "deadline": deadline,
            },
        )
        await client.expire(self._key(attempt_id), ttl_seconds)

    async def get_state(
        self, attempt_id: str
    ) -> dict[str, str] | None:
        client = self._get_client()
        raw = await client.hgetall(self._key(attempt_id))
        if not raw:
            return None
        decoded: dict[str, str] = {k: v for k, v in raw.items()}
        return decoded

    async def invalidate(self, attempt_id: str) -> None:
        client = self._get_client()
        await client.delete(self._key(attempt_id))


@dataclass(frozen=True)
class RateLimitResult:
    """Outcome of one rate-limit check."""

    allowed: bool
    current_count: int
    threshold: int


class RateLimiter(_LazyRedisBase):
    """Fixed-window rate limiting via atomic INCR (FR-012, research R6)."""

    async def check(
        self, scope: str, *, threshold: int, window_seconds: int
    ) -> RateLimitResult:
        """Count one hit against ``scope``'s current window.

        The key embeds the window start so each window has its own counter;
        ``INCR`` is atomic under concurrency and ``EXPIRE`` is set on the
        first hit so counters clean themselves up.
        """
        client = self._get_client()
        window_start = int(time.time() // window_seconds * window_seconds)
        key = f"ratelimit:{scope}:{window_start}"
        count = int(await client.incr(key))
        if count == 1:
            await client.expire(key, window_seconds)
        return RateLimitResult(
            allowed=count <= threshold, current_count=count, threshold=threshold
        )
