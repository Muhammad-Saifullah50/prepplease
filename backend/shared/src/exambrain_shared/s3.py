"""S3 adapter stub with deferred errors (FR-017).

No client construction or network I/O happens at import or ``__init__`` time.
Operations raise :class:`NotConfiguredError` when AWS/S3 config is absent.
"""

from exambrain_shared.config import Settings, get_settings
from exambrain_shared.errors import NotConfiguredError


class S3Adapter:
    """Stub S3 adapter. Real delegation lands in a future feature."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def is_configured(self) -> bool:
        s = self._settings
        return bool(
            s.aws_access_key_id
            and s.aws_secret_access_key
            and s.aws_region
            and s.s3_bucket
        )

    def _require_config(self) -> None:
        if not self.is_configured:
            raise NotConfiguredError(
                "S3",
                "set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, "
                "and S3_BUCKET",
            )

    async def upload(self, key: str, data: bytes) -> None:
        """Upload an object (stub)."""
        self._require_config()
        raise NotImplementedError("S3 delegation not yet implemented")

    async def download(self, key: str) -> bytes:
        """Download an object (stub)."""
        self._require_config()
        raise NotImplementedError("S3 delegation not yet implemented")

    async def delete(self, key: str) -> None:
        """Delete an object (stub)."""
        self._require_config()
        raise NotImplementedError("S3 delegation not yet implemented")
