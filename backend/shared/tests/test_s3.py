"""S3 adapter tests with a hand-rolled in-memory fake aioboto3 client (US4).

The fake implements only the client methods the adapter uses. It is
injected via the adapter's client factory — no aioboto3 session, no network.
"""

import datetime
import io
from typing import Any

import pytest
from botocore.exceptions import ClientError

from exambrain_shared.config import Settings
from exambrain_shared.errors import (
    CredentialError,
    NotConfiguredError,
    ObjectNotFoundError,
    PermissionDeniedError,
)
from exambrain_shared.s3 import S3Adapter

CONFIGURED = Settings(
    _env_file=None,
    aws_access_key_id="AKIAFAKEFAKEFAKE",
    aws_secret_access_key="fake-secret-value",
    aws_region="eu-west-1",
    s3_bucket="exambrain-test",
)
EMPTY = Settings(_env_file=None, aws_access_key_id=None, s3_bucket=None)


def _client_error(code: str, operation: str = "GetObject") -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, operation)


class FakeStream:
    """Chunked async reader over stored bytes (mimics StreamingBody)."""

    def __init__(self, data: bytes) -> None:
        self._buffer = io.BytesIO(data)
        self.chunk_reads = 0

    async def read(self, size: int = -1) -> bytes:
        self.chunk_reads += 1
        return self._buffer.read(size)


class FakeS3Client:
    """In-memory async S3 client covering the methods the adapter uses."""

    def __init__(
        self, *, error: ClientError | None = None, page_size: int = 1000
    ) -> None:
        self.objects: dict[str, bytes] = {}
        self.error = error
        self.page_size = page_size
        self.upload_chunk_reads = 0

    async def __aenter__(self) -> "FakeS3Client":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    def _maybe_raise(self) -> None:
        if self.error is not None:
            raise self.error

    async def upload_fileobj(self, fileobj: Any, bucket: str, key: str) -> None:
        self._maybe_raise()
        chunks = []
        while True:
            chunk = fileobj.read(8 * 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
            self.upload_chunk_reads += 1
        self.objects[key] = b"".join(chunks)

    async def get_object(self, Bucket: str, Key: str) -> dict[str, Any]:
        self._maybe_raise()
        if Key not in self.objects:
            raise _client_error("NoSuchKey")
        return {"Body": FakeStream(self.objects[Key])}

    async def delete_object(self, Bucket: str, Key: str) -> None:
        self._maybe_raise()
        self.objects.pop(Key, None)

    def get_paginator(self, name: str) -> "FakePaginator":
        assert name == "list_objects_v2"
        return FakePaginator(self)


class FakePaginator:
    def __init__(self, client: FakeS3Client) -> None:
        self._client = client

    def paginate(self, *, Bucket: str, Prefix: str) -> "FakePageIterator":
        self._client._maybe_raise()
        matching = sorted(k for k in self._client.objects if k.startswith(Prefix))
        pages = []
        size = self._client.page_size
        for i in range(0, len(matching), size):
            pages.append(
                {
                    "Contents": [
                        {
                            "Key": k,
                            "Size": len(self._client.objects[k]),
                            "LastModified": datetime.datetime(
                                2026, 7, 20, tzinfo=datetime.UTC
                            ),
                        }
                        for k in matching[i : i + size]
                    ]
                }
            )
        if not pages:
            pages = [{}]  # S3 returns no Contents key when empty
        return FakePageIterator(pages)


class FakePageIterator:
    def __init__(self, pages: list[dict[str, Any]]) -> None:
        self._pages = pages

    def __aiter__(self) -> "FakePageIterator":
        self._it = iter(self._pages)
        return self

    async def __anext__(self) -> dict[str, Any]:
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration from None


@pytest.fixture
def fake() -> FakeS3Client:
    return FakeS3Client()


@pytest.fixture
def adapter(fake: FakeS3Client) -> S3Adapter:
    return S3Adapter(CONFIGURED, client_factory=lambda: fake)


async def test_full_object_lifecycle(adapter: S3Adapter, fake: FakeS3Client) -> None:
    payload = b"exam paper content" * 100
    await adapter.upload("courses/abc/paper.pdf", payload)

    listed = await adapter.list_by_prefix("courses/abc/")
    assert [o.key for o in listed] == ["courses/abc/paper.pdf"]
    assert listed[0].size == len(payload)

    assert await adapter.download_bytes("courses/abc/paper.pdf") == payload
    sink = io.BytesIO()
    await adapter.download("courses/abc/paper.pdf", sink)
    assert sink.getvalue() == payload

    await adapter.delete("courses/abc/paper.pdf")
    assert await adapter.list_by_prefix("courses/abc/") == []


async def test_paginated_listing(fake: FakeS3Client) -> None:
    fake.page_size = 2
    adapter = S3Adapter(CONFIGURED, client_factory=lambda: fake)
    for i in range(5):
        await adapter.upload(f"courses/x/f{i}.pdf", b"d")
    listed = await adapter.list_by_prefix("courses/x/")
    assert len(listed) == 5  # complete across 3 pages


async def test_missing_key_raises_object_not_found(adapter: S3Adapter) -> None:
    with pytest.raises(ObjectNotFoundError) as excinfo:
        await adapter.download_bytes("does/not/exist")
    assert not isinstance(excinfo.value, NotConfiguredError)


async def test_access_denied_maps_to_permission_denied(fake: FakeS3Client) -> None:
    fake.error = _client_error("AccessDenied")
    adapter = S3Adapter(CONFIGURED, client_factory=lambda: fake)
    with pytest.raises(PermissionDeniedError):
        await adapter.download_bytes("k")


async def test_expired_token_maps_to_credential_error(fake: FakeS3Client) -> None:
    fake.error = _client_error("ExpiredToken")
    adapter = S3Adapter(CONFIGURED, client_factory=lambda: fake)
    with pytest.raises(CredentialError):
        await adapter.upload("k", b"d")


async def test_not_configured_raises_with_no_client_construction() -> None:
    def _explode() -> object:
        raise AssertionError("client factory must not be called")

    adapter = S3Adapter(EMPTY, client_factory=_explode)
    with pytest.raises(NotConfiguredError, match="S3"):
        await adapter.upload("k", b"d")
    with pytest.raises(NotConfiguredError):
        await adapter.download_bytes("k")
    with pytest.raises(NotConfiguredError):
        await adapter.download("k", io.BytesIO())
    with pytest.raises(NotConfiguredError):
        await adapter.list_by_prefix("p")
    with pytest.raises(NotConfiguredError):
        await adapter.delete("k")


async def test_streaming_upload_consumed_in_chunks(
    adapter: S3Adapter, fake: FakeS3Client
) -> None:
    """A large file-like uploads via multiple chunk reads (SC-006 proxy)."""
    size = 50 * 1024 * 1024  # 50 MB
    source = io.BytesIO(b"\x00" * size)
    await adapter.upload("big/file.bin", source)
    assert fake.upload_chunk_reads > 1  # streamed, not one whole-file read
    assert len(fake.objects["big/file.bin"]) == size
