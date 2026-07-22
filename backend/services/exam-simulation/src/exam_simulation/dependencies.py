"""Dependency injection: auth middleware stubs, repo injection."""

import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from exambrain_shared.db import get_session as get_db
from exambrain_shared.redis import AttemptStateCache


async def get_current_user(request: Request) -> uuid.UUID:
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Id header",
        )
    try:
        return uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid X-User-Id header",
        )


async def get_attempt_state_cache() -> AsyncGenerator[AttemptStateCache, None]:
    cache = AttemptStateCache()
    try:
        yield cache
    finally:
        await cache.aclose()
