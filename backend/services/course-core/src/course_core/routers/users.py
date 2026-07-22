"""User profile endpoints (FR-004)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from course_core.auth import resolve_current_user
from exambrain_agents.repositories.course_core import CourseCoreRepository
from exambrain_shared.db import get_session_factory

router = APIRouter(prefix="/v1/users", tags=["users"])


@router.get("/me")
async def get_profile(
    user: Annotated[dict[str, Any], Depends(resolve_current_user)],
) -> dict[str, Any]:
    return {
        "id": str(user["id"]),
        "clerk_id": user["clerk_id"],
        "email": user["email"],
        "display_name": user["display_name"],
        "preferences": user.get("preferences", {}),
    }


@router.patch("/me")
async def update_profile(
    body: dict[str, Any],
    user: Annotated[dict[str, Any], Depends(resolve_current_user)],
) -> dict[str, Any]:
    session_factory = get_session_factory()
    repo = CourseCoreRepository(session_factory=session_factory)

    if "display_name" in body:
        await repo.update_user_from_webhook(
            user["clerk_id"],
            email=None,
            display_name=body["display_name"],
        )

    updated = await repo.find_user_by_clerk_id(user["clerk_id"])
    assert updated is not None
    return {
        "id": str(updated["id"]),
        "clerk_id": updated["clerk_id"],
        "email": updated["email"],
        "display_name": updated["display_name"],
        "preferences": updated.get("preferences", {}),
    }
