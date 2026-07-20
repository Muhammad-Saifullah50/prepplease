# Contract: File Storage (`exambrain_shared.s3`)

Async S3 adapter via aioboto3, streaming transfers. Replaces the stub in-place; existing surface (`S3Adapter`, `is_configured`, `upload`, `download`, `delete`) preserved, `list_by_prefix` added (FR-014, FR-021).

## Interface

```python
class S3Adapter:
    def __init__(self, settings: Settings | None = None) -> None: ...
    @property
    def is_configured(self) -> bool: ...
        # aws key id + secret + region + s3_bucket (endpoint_url optional, MinIO-ready)

    async def upload(self, key: str, data: bytes | BinaryIO) -> None: ...
        # bytes accepted for small payloads (back-compat with stub signature);
        # file-like streams via upload_fileobj (managed multipart — no whole-file buffering)

    async def download(self, key: str, sink: BinaryIO) -> None: ...
    async def download_bytes(self, key: str) -> bytes: ...
        # convenience for small objects; large files use download(sink) streaming

    async def list_by_prefix(self, prefix: str) -> list[ObjectInfo]: ...
        # paginated list_objects_v2 — complete listing regardless of count

    async def delete(self, key: str) -> None: ...


@dataclass(frozen=True)
class ObjectInfo:
    key: str
    size: int
    last_modified: datetime
```

Note: the stub's `download(key) -> bytes` becomes `download_bytes`; `download` gains a streaming sink. The stub always raised before returning, so no caller depends on the old shape; the not-configured behavior of every method is unchanged.

## Error contract (FR-015 — distinguishable types)

| Condition | Raises |
|---|---|
| Config absent | `NotConfiguredError("S3", ...)` — no network attempt (FR-016) |
| Key does not exist (download/delete-verify) | `ObjectNotFoundError(key)` |
| 403 / AccessDenied | `PermissionDeniedError` |
| Expired/invalid credentials | `CredentialError` (distinct from not-configured and network errors) |
| Network failure | underlying `botocore` connection error surfaced |

All new error types live in `exambrain_shared.errors` and never embed secret values in their messages.

## Behavioral guarantees

- No client construction at import/`__init__`; aioboto3 client opened lazily inside each operation (async context manager) with credentials read from settings at call time (rotation-safe, FR-018).
- Streaming: a 100 MB upload/download keeps process memory growth < 25 MB (SC-006) — chunked transfer via `upload_fileobj` / chunked `StreamingBody.read`.
- Concurrent uploads to one key: last-writer-wins, objects never partial (S3 PUT atomicity).
- Course files use key prefix convention `courses/{course_id}/...` (referenced by `past_papers.s3_key`, `document_chunks.source_s3_key`).

## Test contract (simulated backend)

- In-memory fake aioboto3 client: upload → list shows key → download matches byte-for-byte → delete → list empty.
- Download of missing key → `ObjectNotFoundError` (assert distinct from `NotConfiguredError`).
- Fake raising `ClientError(403)` → `PermissionDeniedError`; `ClientError(ExpiredToken)` → `CredentialError`.
- Empty settings → `NotConfiguredError`, zero fake invocations.
- Streaming test: 50 MB+ generated stream uploads via chunks without full materialization (assert fake received multiple parts / chunk reads).
