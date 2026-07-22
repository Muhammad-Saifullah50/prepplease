"""Clerk JWT verification dependency for ingestion-pipeline (FR-001).

NOTE: This service does NOT own the ``users`` table (it lives in course-core's
DB). We verify the JWT cryptographically and return the Clerk user ID without
any local DB lookup or user creation.
"""

from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer

from exambrain_shared.config import Settings, get_settings

bearer_scheme = HTTPBearer(auto_error=False)


async def require_auth(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if not settings.clerk_secret_key:
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "reason": "CLERK_NOT_CONFIGURED"},
        )

    try:
        from clerk_backend_api import (  # type: ignore[attr-defined]
            AuthenticateRequestOptions,
            authenticate_request,
        )

        state = authenticate_request(
            request,
            AuthenticateRequestOptions(
                secret_key=settings.clerk_secret_key,
                jwt_key=settings.clerk_jwt_key,
                authorized_parties=settings.clerk_authorized_parties,
                accepts_token=["session_token"],
            ),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "reason": "TOKEN_VALIDATION_FAILED"},
        ) from exc

    if not state.is_signed_in:
        reason = getattr(state, "reason", "unknown")
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "reason": str(reason)},
        )

    clerk_id: str = state.payload.get("sub", "")
    if not clerk_id:
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "reason": "TOKEN_MISSING_SUB"},
        )

    return {"clerk_id": clerk_id}
