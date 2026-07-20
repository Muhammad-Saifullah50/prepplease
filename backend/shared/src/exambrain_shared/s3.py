"""Async streaming S3 adapter via aioboto3 (US4).

No client construction at import or ``__init__`` time; an aioboto3 client
is opened lazily inside each operation (async context manager) with
credentials read from settings at call time — rotation-safe (FR-018).
Provider failures map to distinguishable typed errors (FR-015) that never
embed secret values.
"""

import io
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, BinaryIO

from botocore.exceptions import ClientError

from exambrain_shared.config import Settings, get_settings
from exambrain_shared.errors import (
    CredentialError,
    NotConfiguredError,
    ObjectNotFoundError,
    PermissionDeniedError,
)

_DOWNLOAD_CHUNK_SIZE = 8 * 1024 * 1024  # 8 MiB — bounded memory (SC-006)

_NOT_FOUND_CODES = {"NoSuchKey", "404", "NotFound"}
_PERMISSION_CODES = {"AccessDenied", "403"}
_CREDENTIAL_CODES = {
    "ExpiredToken",
    "InvalidClientTokenId",
    "InvalidAccessKeyId",
    "SignatureDoesNotMatch",
}


@dataclass(frozen=True)
class ObjectInfo:
    """Metadata for one listed object."""

    key: str
    size: int
    last_modified: datetime


def _map_client_error(exc: ClientError, key: str | None = None) -> Exception:
    """Translate a botocore ClientError into a typed adapter error."""
    code = str(exc.response.get("Error", {}).get("Code", ""))
    if code in _NOT_FOUND_CODES:
        return ObjectNotFoundError(key or "<unknown>")
    if code in _PERMISSION_CODES:
        return PermissionDeniedError(f"S3 access denied ({code})")
    if code in _CREDENTIAL_CODES:
        return CredentialError(
            f"S3 credentials rejected ({code}) — check the configured "
            "AWS credential source"
        )
    fallback: Exception = exc
    return fallback


class S3Adapter:
    """Async S3 adapter with streaming transfers and typed errors."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._client_factory = client_factory

    @property
    def is_configured(self) -> bool:
        s = self._settings
        return bool(
            s.aws_access_key_id
            and s.aws_secret_access_key
            and s.aws_region
            and s.s3_bucket
        )

    def _require_config(self) -> str:
        if not self.is_configured:
            raise NotConfiguredError(
                "S3",
                "set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, "
                "and S3_BUCKET",
            )
        bucket = self._settings.s3_bucket
        assert bucket is not None
        return bucket

    def _client(self) -> Any:
        """Open an S3 client context — credentials read at call time."""
        if self._client_factory is not None:
            return self._client_factory()
        import aioboto3

        s = self._settings
        session = aioboto3.Session(
            aws_access_key_id=s.aws_access_key_id,
            aws_secret_access_key=s.aws_secret_access_key,
            region_name=s.aws_region,
        )
        return session.client("s3", endpoint_url=s.s3_endpoint_url)

    async def upload(self, key: str, data: "bytes | BinaryIO") -> None:
        """Upload an object, streaming file-likes via managed multipart."""
        bucket = self._require_config()
        fileobj: BinaryIO = io.BytesIO(data) if isinstance(data, bytes) else data
        async with self._client() as client:
            try:
                await client.upload_fileobj(fileobj, bucket, key)
            except ClientError as exc:
                raise _map_client_error(exc, key) from exc

    async def download(self, key: str, sink: "BinaryIO | None" = None) -> None:
        """Stream an object into ``sink`` in bounded chunks.

        ``sink`` is optional only so the not-configured check still fires
        first for legacy single-argument calls (FR-021); a configured
        download requires a sink.
        """
        bucket = self._require_config()
        if sink is None:
            raise TypeError("download() requires a sink; use download_bytes()")
        async with self._client() as client:
            try:
                response = await client.get_object(Bucket=bucket, Key=key)
            except ClientError as exc:
                raise _map_client_error(exc, key) from exc
            body = response["Body"]
            while True:
                chunk = await body.read(_DOWNLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                sink.write(chunk)

    async def download_bytes(self, key: str) -> bytes:
        """Download a (small) object fully into memory."""
        sink = io.BytesIO()
        await self.download(key, sink)
        return sink.getvalue()

    async def list_by_prefix(self, prefix: str) -> list[ObjectInfo]:
        """List all objects under ``prefix`` (paginated — complete listing)."""
        bucket = self._require_config()
        results: list[ObjectInfo] = []
        async with self._client() as client:
            try:
                paginator = client.get_paginator("list_objects_v2")
                async for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                    for obj in page.get("Contents", []):
                        results.append(
                            ObjectInfo(
                                key=obj["Key"],
                                size=obj["Size"],
                                last_modified=obj["LastModified"],
                            )
                        )
            except ClientError as exc:
                raise _map_client_error(exc) from exc
        return results

    async def delete(self, key: str) -> None:
        """Delete an object; deleting an absent key is a no-op (S3 semantics)."""
        bucket = self._require_config()
        async with self._client() as client:
            try:
                await client.delete_object(Bucket=bucket, Key=key)
            except ClientError as exc:
                raise _map_client_error(exc, key) from exc
