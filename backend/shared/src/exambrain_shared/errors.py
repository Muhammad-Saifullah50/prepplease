"""Shared stub error type.

``NotConfiguredError`` is raised by IAM/LLM/S3 stubs at *call* time when the
required configuration is absent (FR-017). Importing or instantiating stubs
never raises.
"""


class NotConfiguredError(RuntimeError):
    """An operation was invoked on a stub whose configuration is absent."""

    def __init__(self, component: str, detail: str | None = None) -> None:
        message = f"{component} is not configured"
        if detail:
            message = f"{message}: {detail}"
        super().__init__(message)
        self.component = component
