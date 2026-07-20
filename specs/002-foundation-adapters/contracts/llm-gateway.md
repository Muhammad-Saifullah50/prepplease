# Contract: LLM Gateway (`exambrain_shared.llm`)

Async gateway for all LLM operations (Constitution V). Provider/model selected only by configuration. Replaces the stub in-place — existing public surface (`LLMClient`, `is_configured`, `complete`, `embed`, `NotConfiguredError` semantics) preserved (FR-021).

## Interface

```python
class LLMClient:
    def __init__(self, settings: Settings | None = None) -> None: ...
    @property
    def is_configured(self) -> bool: ...
        # llm_provider + llm_model + (llm_api_key OR aws cred trio for bedrock)

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> CompletionResult: ...

    async def embed(self, text: str) -> list[float]: ...
        # uses settings.llm_embedding_model; result length == 1024 for Titan V2

    @property
    def usage(self) -> UsageSnapshot: ...
        # cumulative per-model + total counters, process lifetime (FR-009)


@dataclass(frozen=True)
class CompletionResult:
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
```

Note: `complete()` returns `CompletionResult` (was `str` in the stub). The stub always raised before returning, so no caller depends on the old return type; acceptance scenario 1 requires per-call token counts alongside text.

## Error contract

| Condition | Raises | Retried? |
|---|---|---|
| Not configured | `NotConfiguredError("LLM", ...)` — before any network I/O | no |
| Rate limit / timeout / connection / 5xx | retried with exponential backoff + jitter; after `llm_max_retries` attempts or `llm_retry_deadline_seconds` total → `TransientLLMError` (chains provider error) | yes (bounded) |
| Auth failure / invalid model / bad request / context overflow | `PermanentLLMError` carrying provider reason | never |

## Behavioral guarantees

- No network I/O, client construction, or validation at import or `__init__` time.
- Every successful call: records a `UsageRecord`, updates cumulative counters, emits one structlog event with `model`, `prompt_hash` (sha256), `latency_ms`, `prompt_tokens`, `completion_tokens` — never raw prompt/response text.
- Retry policy: exponential backoff with jitter, bounded by both attempt count and total deadline (FR-008).
- Credentials are read from settings at call time (supports rotation, FR-018) and never appear in logs or exception text (FR-019).

## Test contract (simulated provider)

- Fake `litellm.acompletion` returning canned usage → assert `CompletionResult` fields + usage counters.
- Fake raising `RateLimitError` twice then succeeding → assert 3 calls, success.
- Fake raising `AuthenticationError` → assert `PermanentLLMError` after exactly 1 call.
- Fake always raising `Timeout` → assert `TransientLLMError` after `llm_max_retries` calls.
- Empty settings → `NotConfiguredError`, zero fake invocations.
