"""Per-agent model resolution and behavior knobs (FR-021, research R10).

Every agent's model is a :class:`LitellmModel` so all traffic flows through
LiteLLM to the configured provider (Constitution V). A per-agent env
override (``AGENT_<NAME>_MODEL``) falls back to the platform-wide
``LLM_MODEL``.
"""

from agents.extensions.models.litellm_model import LitellmModel

from exambrain_shared.config import Settings, get_settings
from exambrain_shared.errors import NotConfiguredError

_AGENT_MODEL_FIELDS = {
    "parsing": "agent_parsing_model",
    "alignment": "agent_alignment_model",
    "blueprint": "agent_blueprint_model",
    "generator": "agent_generator_model",
    "evaluation": "agent_evaluation_model",
}


def _credential_kwargs(settings: Settings) -> dict[str, str | None]:
    """API key for LitellmModel; bedrock uses ambient AWS credentials."""
    if settings.llm_provider == "bedrock" and not settings.llm_api_key:
        return {}
    return {"api_key": settings.llm_api_key}


def model_for(agent_name: str, settings: Settings | None = None) -> LitellmModel:
    """Resolve the LiteLLM model for ``agent_name`` (FR-021)."""
    s = settings or get_settings()
    try:
        field = _AGENT_MODEL_FIELDS[agent_name]
    except KeyError:
        raise ValueError(f"unknown agent name: {agent_name!r}") from None
    model: str | None = getattr(s, field) or s.llm_model
    if not model:
        raise NotConfiguredError(
            "LLM", f"set LLM_MODEL (or AGENT_{agent_name.upper()}_MODEL)"
        )
    creds = _credential_kwargs(s)
    return LitellmModel(model=model, api_key=creds.get("api_key"))


def model_for_or_none(
    agent_name: str, settings: Settings | None = None
) -> LitellmModel | None:
    """Like :func:`model_for`, but None when no model is configured.

    Agent construction stays import-safe with zero configuration (tests
    inject FakeModel at run time); a live run without LLM_MODEL still fails
    loudly inside the SDK when the agent actually executes.
    """
    try:
        return model_for(agent_name, settings)
    except NotConfiguredError:
        return None


def max_turns(settings: Settings | None = None) -> int:
    """Per-run agent interaction budget (edge case: never loop forever)."""
    return (settings or get_settings()).agent_max_turns


def alignment_auto_match_threshold(settings: Settings | None = None) -> float:
    """Band (a) floor: similarity at or above this auto-matches (FR-007)."""
    return (settings or get_settings()).alignment_auto_match_threshold


def alignment_review_threshold(settings: Settings | None = None) -> float:
    """Band (b) floor: scores in [review, auto) require review (FR-007)."""
    return (settings or get_settings()).alignment_review_threshold


def parsing_review_confidence_threshold(
    settings: Settings | None = None,
) -> float:
    """Parses below this confidence flag the paper needs_review (FR-002)."""
    return (settings or get_settings()).parsing_review_confidence_threshold
