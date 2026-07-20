"""IAM validation stub with deferred errors (FR-017).

No client construction or network I/O happens at import or ``__init__`` time.
Operations raise :class:`NotConfiguredError` when AWS config is absent.
"""

from typing import Any

from exambrain_shared.config import Settings, get_settings
from exambrain_shared.errors import NotConfiguredError


class IAMClient:
    """Stub IAM client. Real delegation lands in a future feature."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def is_configured(self) -> bool:
        s = self._settings
        return bool(s.aws_access_key_id and s.aws_secret_access_key and s.aws_region)

    def _require_config(self) -> None:
        if not self.is_configured:
            raise NotConfiguredError(
                "IAM",
                "set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and AWS_REGION",
            )

    def validate_token(self, token: str) -> dict[str, Any]:
        """Validate an identity token (stub)."""
        self._require_config()
        raise NotImplementedError("IAM delegation not yet implemented")

    def get_caller_identity(self) -> dict[str, Any]:
        """Return the caller identity (stub)."""
        self._require_config()
        raise NotImplementedError("IAM delegation not yet implemented")
