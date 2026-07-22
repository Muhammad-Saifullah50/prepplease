# Research: Foundation Services

## Clerk Python Backend SDK Integration

### Decision

Use the official `clerk-backend-api` package (PyPI: `clerk-backend-api`) for all server-side authentication.

### Rationale

Clerk's official Python SDK (released October 2024, GA by mid-2025) provides:
- `authenticate_request()` — JWT verification from FastAPI `Request` objects without manual JWKS fetching
- `AuthenticateRequestOptions` — configurable `secret_key`, `jwt_key` (PEM for networkless verification), `authorized_parties` (CSRF protection via `azp` claim check)
- `RequestState` — returned object with `is_signed_in`, `payload` (claims), `reason` (enum for error type)
- `Clerk` client class — for Backend API calls (user profile, org memberships) with async support

### Alternatives Considered

| Alternative | Why Rejected |
|---|---|
| `fastapi-clerk-auth` (community package, OSSMafia) | Third-party, slower to update, adds unnecessary abstraction over Clerk's own SDK |
| Manual JWT verification with `python-jose` + JWKS endpoint | More code to maintain, no SDK-level `azp`/`authorized_parties` validation, no Backend API client |
| `Auth0` / `Supabase` | Spec mandates Clerk as sole auth provider |

### Integration Pattern for FastAPI

```python
from clerk_backend_api import AuthenticateRequestOptions, authenticate_request
from fastapi import Depends, HTTPException, Request

def require_auth(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> RequestState:
    state = authenticate_request(
        request,
        AuthenticateRequestOptions(
            secret_key=settings.clerk_secret_key,
            jwt_key=settings.clerk_jwt_key,
            authorized_parties=settings.clerk_authorized_parties,
            accepts_token=["session_token"],
        ),
    )
    if not state.is_signed_in:
        raise HTTPException(status_code=401, detail="unauthorized")
    return state
```

Key details:
- FastAPI `Request` satisfies Clerk's `Requestish` protocol directly (has `.headers` mapping)
- `accepts_token=["session_token"]` restricts to user sessions (not M2M)
- `jwt_key` enables networkless local signature verification (no JWKS fetch per request)
- `authorized_parties` prevents CSRF by validating the `azp` claim
- Test via `app.dependency_overrides[require_auth] = lambda: fake_state`

### Clerk Webhook Handling

- Clerk uses Svix for webhook signing (standard `svix-id`, `svix-timestamp`, `svix-signature` headers)
- The `clerk-backend-api` package does NOT include webhook verification; use `svix` PyPI package directly
- Events to handle: `user.created`, `user.updated`, `user.deleted`
- `user.deleted` → soft-mark local record (set `is_active=False`), never hard-delete
- Lazy user creation: if an authenticated request arrives for a Clerk user ID not yet in local DB, create the record on the fly (FR-003)

### Async File Upload to S3

- Use existing `S3Adapter` from `exambrain-shared` (wraps aioboto3)
- Streaming upload: `UploadFile` from FastAPI → read in chunks → stream to S3 via `upload_fileobj`
- Content hash (SHA-256) computed during upload stream for duplicate detection
- Reject unsupported types (not PDF/PPTX) and oversized files (>50MB) before S3 upload
- Return tracking ID immediately; processing runs as background asyncio task

### Background Task Pattern

- Use `asyncio.create_task()` in the upload endpoint for lightweight background processing
- Not suitable for production at scale, but acceptable for MVP (< 1000 users)
- Processing: call `ingest_course_file()` from `exambrain_agents.pipelines.ingest`
- Per-course serialization: use advisory lock (`pg_advisory_xact_lock`) via existing pattern in `CourseCoreRepository.write_blueprint_version`
- Queue subsequent uploads for the same course — only one blueprint-modifying run at a time
- Status tracked in `PastPaper.processing_status` (pending → processing → completed/failed)

### Repository Layer

- Service handlers use existing repositories in `exambrain_agents.repositories`
- `CourseCoreRepository`: `get_course`, `list_courses`, `create_course`, `update_course`, `soft_delete_course`, `latest_blueprint`, `upsert_result`
- `IngestionRepository`: `get_paper`, `mark_processing`, `mark_completed`, `mark_failed`

### Testing Strategy

- FastAPI `TestClient` or `httpx.AsyncClient` with `ASGITransport`
- Auth: override `require_auth` dependency with `app.dependency_overrides` — return fake `RequestState` with `sub="user_fake123"`
- 401 tests: remove override, verify real auth rejection
- Upload tests: use `BytesIO` with fake PDF bytes; mock `S3Adapter` and `ingest_course_file`
- DB: use existing test DB setup (migration gate in conftest.py)

