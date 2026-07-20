"""Shared error types.

``NotConfiguredError`` is raised by adapters at *call* time when the
required configuration is absent (FR-017). Importing or instantiating
adapters never raises. The remaining types give callers distinguishable
failure modes without ever embedding secret values in messages.
"""


class NotConfiguredError(RuntimeError):
    """An operation was invoked on a stub whose configuration is absent."""

    def __init__(self, component: str, detail: str | None = None) -> None:
        message = f"{component} is not configured"
        if detail:
            message = f"{message}: {detail}"
        super().__init__(message)
        self.component = component


class ObjectNotFoundError(RuntimeError):
    """A storage object referenced by key does not exist."""

    def __init__(self, key: str) -> None:
        super().__init__(f"object not found: {key}")
        self.key = key


class PermissionDeniedError(RuntimeError):
    """The configured principal lacks permission for the operation."""


class CredentialError(RuntimeError):
    """Credentials are invalid or expired (distinct from not-configured).

    Messages reference the credential *source* only — never secret values.
    """


class TransientLLMError(RuntimeError):
    """A retryable LLM failure persisted past the bounded retry policy."""


class PermanentLLMError(RuntimeError):
    """A non-retryable LLM failure (auth, bad request, invalid model)."""
