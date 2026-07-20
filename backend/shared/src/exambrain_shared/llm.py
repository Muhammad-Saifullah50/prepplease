"""Async LiteLLM gateway to the configured provider (Constitution V).

No client construction or network I/O at import or ``__init__`` time.
Transient provider failures are retried with bounded exponential backoff +
jitter (tenacity); permanent failures raise :class:`PermanentLLMError`
immediately. Every call updates the in-memory :class:`UsageTracker` and
emits a structured log event that never contains raw prompt/response text.
"""

import hashlib
import time
from dataclasses import dataclass
from typing import Any

import litellm
import litellm.exceptions
import structlog
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential_jitter,
)

from exambrain_shared.config import Settings, get_settings
from exambrain_shared.errors import (
    NotConfiguredError,
    PermanentLLMError,
    TransientLLMError,
)
from exambrain_shared.llm_usage import UsageSnapshot, UsageTracker

logger = structlog.get_logger(__name__)

# Multiplier for exponential backoff; tests shrink it so retries are instant.
_BACKOFF_MULTIPLIER = 1.0

# LiteLLM-normalized exception classification (research R1).
_TRANSIENT_ERRORS: tuple[type[Exception], ...] = (
    litellm.exceptions.RateLimitError,
    litellm.exceptions.Timeout,
    litellm.exceptions.APIConnectionError,
    litellm.exceptions.InternalServerError,
    litellm.exceptions.ServiceUnavailableError,
)
_PERMANENT_ERRORS: tuple[type[Exception], ...] = (
    litellm.exceptions.AuthenticationError,
    litellm.exceptions.ContextWindowExceededError,  # BadRequestError subclass
    litellm.exceptions.NotFoundError,
    litellm.exceptions.BadRequestError,
)


def _is_transient(exc: BaseException) -> bool:
    return isinstance(exc, _TRANSIENT_ERRORS)


@dataclass(frozen=True)
class CompletionResult:
    """A completion with its per-call token usage (US2 acceptance 1)."""

    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int


class LLMClient:
    """Async gateway for all LLM operations.

    Provider and model come exclusively from environment configuration
    (Constitution V — LLM abstraction). Credentials are read from settings
    at call time so rotation via ``CredentialManager.refresh`` takes effect
    without restart (FR-018).
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._tracker = UsageTracker()

    @property
    def is_configured(self) -> bool:
        s = self._settings
        if not (s.llm_provider and s.llm_model):
            return False
        if s.llm_api_key:
            return True
        aws_trio = bool(
            s.aws_access_key_id and s.aws_secret_access_key and s.aws_region
        )
        return s.llm_provider == "bedrock" and aws_trio

    @property
    def usage(self) -> UsageSnapshot:
        """Cumulative per-model token counters for the process lifetime."""
        return self._tracker.snapshot()

    def _require_config(self) -> None:
        if not self.is_configured:
            raise NotConfiguredError(
                "LLM",
                "set LLM_PROVIDER, LLM_MODEL, and LLM_API_KEY (or the AWS "
                "credential trio for the bedrock provider)",
            )

    def _credential_kwargs(self) -> dict[str, Any]:
        """Per-call credentials from settings — never global state (R2)."""
        s = self._settings
        if s.llm_provider == "bedrock" and not s.llm_api_key:
            return {
                "aws_access_key_id": s.aws_access_key_id,
                "aws_secret_access_key": s.aws_secret_access_key,
                "aws_region_name": s.aws_region,
            }
        return {"api_key": s.llm_api_key}

    async def _call_with_retry(self, operation: Any, /, **kwargs: Any) -> Any:
        """Invoke a LiteLLM coroutine with bounded transient-retry (FR-008)."""
        s = self._settings
        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception(_is_transient),
                stop=(
                    stop_after_attempt(s.llm_max_retries)
                    | stop_after_delay(s.llm_retry_deadline_seconds)
                ),
                wait=wait_exponential_jitter(
                    initial=_BACKOFF_MULTIPLIER, max=10 * _BACKOFF_MULTIPLIER
                ),
                reraise=False,
            ):
                with attempt:
                    return await operation(
                        num_retries=0, **self._credential_kwargs(), **kwargs
                    )
        except RetryError as exc:
            last = exc.last_attempt.exception()
            raise TransientLLMError(
                "LLM call failed after bounded retries (transient provider "
                "errors persisted)"
            ) from last
        except _PERMANENT_ERRORS as exc:
            raise PermanentLLMError(f"LLM call rejected by provider: {exc}") from exc

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> CompletionResult:
        """Generate a completion, returning text plus per-call token counts."""
        self._require_config()
        model = self._settings.llm_model
        assert model is not None  # guarded by _require_config
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        call_kwargs: dict[str, Any] = {"model": model, "messages": messages}
        if temperature is not None:
            call_kwargs["temperature"] = temperature
        if max_tokens is not None:
            call_kwargs["max_tokens"] = max_tokens
        call_kwargs.update(kwargs)

        start = time.monotonic()
        response = await self._call_with_retry(litellm.acompletion, **call_kwargs)
        latency_ms = (time.monotonic() - start) * 1000

        prompt_tokens = int(response.usage.prompt_tokens)
        completion_tokens = int(response.usage.completion_tokens)
        self._tracker.record(model, prompt_tokens, completion_tokens)
        self._log_call(
            "llm_completion",
            model,
            prompt,
            latency_ms,
            prompt_tokens,
            completion_tokens,
        )
        return CompletionResult(
            text=response.choices[0].message.content,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    async def embed(self, text: str, **kwargs: Any) -> list[float]:
        """Generate an embedding via the configured embedding model."""
        self._require_config()
        model = self._settings.llm_embedding_model
        if not model:
            raise NotConfiguredError("LLM", "set LLM_EMBEDDING_MODEL")

        start = time.monotonic()
        response = await self._call_with_retry(
            litellm.aembedding, model=model, input=[text], **kwargs
        )
        latency_ms = (time.monotonic() - start) * 1000

        prompt_tokens = int(getattr(response.usage, "prompt_tokens", 0) or 0)
        self._tracker.record(model, prompt_tokens, 0)
        self._log_call("llm_embedding", model, text, latency_ms, prompt_tokens, 0)
        item = response.data[0]
        embedding = item["embedding"] if isinstance(item, dict) else item.embedding
        return list(embedding)

    @staticmethod
    def _log_call(
        event: str,
        model: str,
        prompt: str,
        latency_ms: float,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        """Log call metadata — never raw prompt/response text (FR-019, X)."""
        logger.info(
            event,
            model=model,
            prompt_hash=hashlib.sha256(prompt.encode()).hexdigest(),
            latency_ms=round(latency_ms, 2),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
