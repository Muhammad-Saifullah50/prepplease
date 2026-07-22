"""Clerk JWT verification dependency with lazy user creation (FR-001)."""

from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer
from sqlalchemy import select

from exambrain_shared.config import Settings, get_settings
from exambrain_shared.db import get_session_factory
from exambrain_shared.models.course_core import User

bearer_scheme = HTTPBearer(auto_error=False)


async def resolve_current_user(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if not settings.clerk_secret_key:
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "reason": "CLERK_NOT_CONFIGURED"},
        )

    session_factory = get_session_factory(settings.database_url)

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
            detail={
                "error": "unauthorized",
                "reason": str(reason),
            },
        )

    clerk_id: str = state.payload.get("sub", "")
    if not clerk_id:
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "reason": "TOKEN_MISSING_SUB"},
        )

    email = state.payload.get("email", "")
    display_name = state.payload.get("name", "") or state.payload.get(
        "given_name", ""
    )

    async with session_factory() as session, session.begin():
        row = await session.scalar(
            select(User).where(User.clerk_id == clerk_id)
        )
        if row is not None:
            return {
                "id": row.id,
                "clerk_id": row.clerk_id,
                "email": row.email,
                "display_name": row.display_name,
                "is_active": row.is_active,
                "preferences": row.preferences,
            }

        user = User(
            clerk_id=clerk_id,
            email=email or f"{clerk_id}@clerk.example",
            display_name=display_name or clerk_id,
            is_active=True,
            preferences={},
        )
        session.add(user)
        await session.flush()
        return {
            "id": user.id,
            "clerk_id": user.clerk_id,
            "email": user.email,
            "display_name": user.display_name,
            "is_active": user.is_active,
            "preferences": user.preferences,
        }
