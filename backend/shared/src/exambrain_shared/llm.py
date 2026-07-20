"""LiteLLM client stub with deferred errors (FR-017).

No client construction or network I/O happens at import or ``__init__`` time.
Operations raise :class:`NotConfiguredError` when LLM config is absent.
"""

from typing import Any

from exambrain_shared.config import Settings, get_settings
from exambrain_shared.errors import NotConfiguredError


class LLMClient:
    """Stub LLM client (LiteLLM-backed in a future feature).

    Provider and model come exclusively from environment configuration
    (Constitution V — LLM abstraction).
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def is_configured(self) -> bool:
        s = self._settings
        return bool(s.llm_provider and s.llm_model and s.llm_api_key)

    def _require_config(self) -> None:
        if not self.is_configured:
            raise NotConfiguredError(
                "LLM",
                "set LLM_PROVIDER, LLM_MODEL, and LLM_API_KEY",
            )

    async def complete(self, prompt: str, **kwargs: Any) -> str:
        """Generate a completion (stub)."""
        self._require_config()
        raise NotImplementedError("LLM delegation not yet implemented")

    async def embed(self, text: str, **kwargs: Any) -> list[float]:
        """Generate an embedding (stub)."""
        self._require_config()
        raise NotImplementedError("LLM delegation not yet implemented")
