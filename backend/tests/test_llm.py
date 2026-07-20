"""LLM gateway tests with a simulated provider (research R9, US2).

``litellm.acompletion`` / ``litellm.aembedding`` are monkeypatched — no
network I/O anywhere. Retry classification, usage tracking, structlog
hygiene, and the not-configured contract are all exercised here.
"""

from types import SimpleNamespace
from typing import Any

import litellm
import pytest

from exambrain_shared.config import Settings
from exambrain_shared.errors import (
    NotConfiguredError,
    PermanentLLMError,
    TransientLLMError,
)
from exambrain_shared.llm import CompletionResult, LLMClient

BEDROCK = Settings(
    _env_file=None,
    llm_provider="bedrock",
    llm_model="bedrock/eu.anthropic.claude-3-5-sonnet-20240620-v1:0",
    llm_embedding_model="bedrock/amazon.titan-embed-text-v2:0",
    aws_access_key_id="AKIAFAKEFAKEFAKE",
    aws_secret_access_key="fake-secret-value",
    aws_region="eu-west-1",
    llm_max_retries=3,
    llm_retry_deadline_seconds=5,
)

EMPTY = Settings(_env_file=None, llm_provider=None, llm_api_key=None)


def _completion_response(
    text: str = "hello", prompt_tokens: int = 7, completion_tokens: int = 3
) -> Any:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
        ),
        model="bedrock/claude",
    )


def _embedding_response(dims: int = 1024) -> Any:
    return SimpleNamespace(
        data=[{"embedding": [0.1] * dims}],
        usage=SimpleNamespace(prompt_tokens=4, completion_tokens=0),
    )


class FakeProvider:
    """Callable fake for ``litellm.acompletion`` recording invocations."""

    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = outcomes
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        outcome = self.outcomes[min(len(self.calls) - 1, len(self.outcomes) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture(autouse=True)
def fast_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zero out backoff sleeps so retry tests run instantly."""
    import exambrain_shared.llm as llm_mod

    monkeypatch.setattr(llm_mod, "_BACKOFF_MULTIPLIER", 0.001)


async def test_complete_success_returns_result_and_tracks_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeProvider([_completion_response("answer", 11, 5)])
    monkeypatch.setattr(litellm, "acompletion", fake)
    client = LLMClient(BEDROCK)

    result = await client.complete("What is 2+2?")

    assert isinstance(result, CompletionResult)
    assert result.text == "answer"
    assert result.prompt_tokens == 11
    assert result.completion_tokens == 5
    snap = client.usage
    assert snap.total_prompt_tokens == 11
    assert snap.total_completion_tokens == 5
    assert snap.per_model[BEDROCK.llm_model].calls == 1


async def test_transient_error_retried_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rate_limit = litellm.RateLimitError("throttled", llm_provider="bedrock", model="m")
    fake = FakeProvider([rate_limit, rate_limit, _completion_response()])
    monkeypatch.setattr(litellm, "acompletion", fake)
    client = LLMClient(BEDROCK)

    result = await client.complete("hi")

    assert len(fake.calls) == 3
    assert result.text == "hello"


async def test_permanent_error_raises_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth = litellm.AuthenticationError(
        "bad credentials", llm_provider="bedrock", model="m"
    )
    fake = FakeProvider([auth])
    monkeypatch.setattr(litellm, "acompletion", fake)
    client = LLMClient(BEDROCK)

    with pytest.raises(PermanentLLMError):
        await client.complete("hi")
    assert len(fake.calls) == 1


async def test_retries_exhausted_raises_transient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timeout = litellm.Timeout("slow", model="m", llm_provider="bedrock")
    fake = FakeProvider([timeout])
    monkeypatch.setattr(litellm, "acompletion", fake)
    client = LLMClient(BEDROCK)

    with pytest.raises(TransientLLMError) as excinfo:
        await client.complete("hi")
    assert len(fake.calls) == BEDROCK.llm_max_retries
    assert excinfo.value.__cause__ is timeout


async def test_not_configured_raises_before_any_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeProvider([_completion_response()])
    monkeypatch.setattr(litellm, "acompletion", fake)
    monkeypatch.setattr(litellm, "aembedding", fake)
    client = LLMClient(EMPTY)

    with pytest.raises(NotConfiguredError):
        await client.complete("hi")
    with pytest.raises(NotConfiguredError):
        await client.embed("hi")
    assert fake.calls == []


async def test_embed_returns_1024_vector(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeProvider([_embedding_response()])
    monkeypatch.setattr(litellm, "aembedding", fake)
    client = LLMClient(BEDROCK)

    vector = await client.embed("chunk text")

    assert len(vector) == 1024
    assert fake.calls[0]["model"] == BEDROCK.llm_embedding_model


async def test_log_event_has_metadata_but_never_prompt_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeProvider([_completion_response()])
    monkeypatch.setattr(litellm, "acompletion", fake)
    client = LLMClient(BEDROCK)
    secret_prompt = "SUPER-SECRET-PROMPT-CONTENT"

    import structlog.testing

    with structlog.testing.capture_logs() as captured:
        await client.complete(secret_prompt)

    log_text = repr(captured)
    assert secret_prompt not in log_text
    assert BEDROCK.llm_model in log_text
    assert "prompt_tokens" in log_text
    assert "latency_ms" in log_text


def test_is_configured_accepts_aws_trio_for_bedrock() -> None:
    assert LLMClient(BEDROCK).is_configured
    assert not LLMClient(EMPTY).is_configured
    # Non-bedrock provider still requires an API key.
    openai_no_key = Settings(
        _env_file=None, llm_provider="openai", llm_model="gpt-4o", llm_api_key=None
    )
    assert not LLMClient(openai_no_key).is_configured
    openai_with_key = Settings(
        _env_file=None, llm_provider="openai", llm_model="gpt-4o", llm_api_key="sk-x"
    )
    assert LLMClient(openai_with_key).is_configured
