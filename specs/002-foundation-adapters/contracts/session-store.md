# Contract: Session Store & Rate Limiter (`exambrain_shared.redis`)

Async Redis-backed key-value session store with server-enforced TTL, plus fixed-window rate limiting. New module (no prior stub existed for Redis); follows the same deferred-error pattern as the other adapters.

## Interface

```python
class SessionStore:
    def __init__(self, settings: Settings | None = None) -> None: ...
    @property
    def is_configured(self) -> bool: ...   # bool(settings.redis_url)

    async def set_session(
        self, session_id: str, value: dict[str, Any], ttl_seconds: int
    ) -> None: ...
        # SET session:{id} <json> EX ttl — expiry enforced server-side

    async def get_session(self, session_id: str) -> dict[str, Any] | None: ...
        # None when absent/expired/evicted — never raises for missing keys

    async def delete_session(self, session_id: str) -> None: ...

    async def aclose(self) -> None: ...    # releases pooled connections if any


class RateLimiter:
    def __init__(self, settings: Settings | None = None) -> None: ...
    @property
    def is_configured(self) -> bool: ...

    async def check(
        self, scope: str, *, threshold: int, window_seconds: int
    ) -> RateLimitResult: ...
        # atomic INCR on ratelimit:{scope}:{window}; EXPIRE set on first hit


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool          # count <= threshold
    current_count: int
    threshold: int
```

## Error contract

| Condition | Behavior |
|---|---|
| `redis_url` unset | `NotConfiguredError("Redis", "set REDIS_URL")` at call time |
| Redis unreachable | `ConnectionError` (redis-py) surfaced at call time — never at import/construct (FR-013) |
| Missing/expired/evicted key | `get_session` returns `None` (edge case: absent key ≠ crash) |
| Concurrent writes to same key | last-writer-wins; value is always one complete JSON document (atomic SET) |

## Behavioral guarantees

- Client created lazily on first operation via `redis.asyncio.Redis.from_url`; reused thereafter.
- TTL enforced by Redis (`EX`), not client-side timestamps — clock-skew safe.
- `check` is atomic under concurrency: `INCR` is atomic; exactly the N+1th operation in a window reports `allowed=False` at threshold N (FR-012, SC-005).
- Values are JSON-serialized dicts (structured session state: timer, auto-save buffer, focus violations).

## Test contract (fakeredis)

- Set with TTL → get returns value; advance fake time past TTL → get returns `None`.
- N increments allowed, N+1th denied within the same window; new window resets.
- Concurrent `set_session` on one key via `asyncio.gather` → final state equals one of the writes, valid JSON.
- No `redis_url` → `NotConfiguredError` before any client creation.
