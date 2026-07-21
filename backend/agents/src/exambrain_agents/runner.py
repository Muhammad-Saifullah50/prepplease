"""Single ``Runner.run`` wrapper: error translation + run logging (R11).

Every pipeline invokes agents exclusively through :func:`run_agent` so the
error mapping (FR-023) and the content-free structured logging (FR-022)
live in exactly one place. Validation-driven corrective retries use
:func:`run_agent_with_corrective_retry`.
"""

import time
from collections.abc import Callable, Sequence
from typing import Any

import litellm.exceptions
import structlog
from agents import Agent, Runner
from agents.exceptions import AgentsException, MaxTurnsExceeded, ModelBehaviorError
from agents.models.interface import Model

from exambrain_agents import config
from exambrain_agents.errors import AgentOutputError, AgentTurnLimitError
from exambrain_shared.errors import PermanentLLMError, TransientLLMError

logger = structlog.get_logger(__name__)

_TRANSIENT_ERRORS: tuple[type[Exception], ...] = (
    litellm.exceptions.RateLimitError,
    litellm.exceptions.Timeout,
    litellm.exceptions.APIConnectionError,
    litellm.exceptions.InternalServerError,
    litellm.exceptions.ServiceUnavailableError,
)
_PERMANENT_ERRORS: tuple[type[Exception], ...] = (
    litellm.exceptions.AuthenticationError,
    litellm.exceptions.NotFoundError,
    litellm.exceptions.BadRequestError,
)


async def run_agent(
    agent: Agent[Any],
    input: str,
    *,
    model: Model | None = None,
    max_turns: int | None = None,
) -> Any:
    """Run ``agent`` and return its typed final output.

    ``model`` overrides the agent's configured model (tests inject
    :class:`~exambrain_agents.testing.FakeModel` here). Errors are mapped
    to the platform hierarchy (FR-023); the log record carries metadata
    only — never prompt/response/document text (FR-022).
    """
    effective = agent.clone(model=model) if model is not None else agent
    turns = max_turns if max_turns is not None else config.max_turns()
    model_name = _model_name(effective)
    start = time.monotonic()
    try:
        result = await Runner.run(effective, input, max_turns=turns)
    except MaxTurnsExceeded as exc:
        _log_run(agent.name, model_name, start, error="turn_limit")
        raise AgentTurnLimitError(agent.name, turns) from exc
    except ModelBehaviorError as exc:
        _log_run(agent.name, model_name, start, error="bad_output")
        raise AgentOutputError(agent.name, str(exc)) from exc
    except _TRANSIENT_ERRORS as exc:
        _log_run(agent.name, model_name, start, error="transient_provider")
        raise TransientLLMError(
            f"provider failure during agent '{agent.name}' run"
        ) from exc
    except _PERMANENT_ERRORS as exc:
        _log_run(agent.name, model_name, start, error="permanent_provider")
        raise PermanentLLMError(
            f"provider rejected agent '{agent.name}' run: {type(exc).__name__}"
        ) from exc
    except AgentsException as exc:
        _log_run(agent.name, model_name, start, error="framework")
        raise AgentOutputError(agent.name, type(exc).__name__) from exc

    usage = result.context_wrapper.usage
    _log_run(
        agent.name,
        model_name,
        start,
        turn_count=len(result.raw_responses),
        prompt_tokens=usage.input_tokens,
        completion_tokens=usage.output_tokens,
    )
    return result.final_output


async def run_agent_with_corrective_retry[T](
    agent: Agent[Any],
    input: str,
    validate: Callable[[T], Sequence[str]],
    *,
    model: Model | None = None,
    max_turns: int | None = None,
) -> tuple[T, list[str]]:
    """Run, validate, retry once with the failure list appended (R11).

    Returns ``(output, failures)`` — ``failures`` is empty when the final
    output validated cleanly, else the second run's failure list so the
    caller persists the record flagged ``needs_review`` (FR-014/FR-017).
    """
    output: T = await run_agent(agent, input, model=model, max_turns=max_turns)
    failures = list(validate(output))
    if not failures:
        return output, []
    corrective = (
        f"{input}\n\nYour previous output failed validation:\n"
        + "\n".join(f"- {failure}" for failure in failures)
        + "\nProduce a corrected output that resolves every failure."
    )
    logger.info("agent_corrective_retry", agent=agent.name, failure_count=len(failures))
    output = await run_agent(agent, corrective, model=model, max_turns=max_turns)
    return output, list(validate(output))


def _model_name(agent: Agent[Any]) -> str:
    model = agent.model
    if model is None:
        return "default"
    if isinstance(model, str):
        return model
    return getattr(model, "model", type(model).__name__)


def _log_run(
    agent_name: str,
    model_name: str,
    start: float,
    *,
    error: str | None = None,
    turn_count: int | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
) -> None:
    """Structured run record — metadata only, never content (FR-022)."""
    logger.info(
        "agent_run",
        agent=agent_name,
        model=model_name,
        latency_ms=round((time.monotonic() - start) * 1000, 2),
        error=error,
        turn_count=turn_count,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
