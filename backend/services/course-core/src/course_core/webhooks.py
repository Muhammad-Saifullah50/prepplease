"""Clerk webhook handler for user lifecycle sync (FR-002, FR-021)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request

from exambrain_agents.repositories.course_core import CourseCoreRepository
from exambrain_shared.config import Settings, get_settings
from exambrain_shared.db import get_session_factory

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])

_EVENT_TYPES = frozenset({"user.created", "user.updated", "user.deleted"})


@router.post("/clerk")
async def clerk_webhook(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if not settings.clerk_webhook_signing_secret:
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "reason": "WEBHOOK_NOT_CONFIGURED"},
        )

    body = await request.body()
    svix_id = request.headers.get("svix-id", "")
    svix_timestamp = request.headers.get("svix-timestamp", "")
    svix_signature = request.headers.get("svix-signature", "")

    if not svix_id or not svix_timestamp or not svix_signature:
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "reason": "MISSING_SVIX_HEADERS"},
        )

    try:
        from svix import Webhook

        wh = Webhook(settings.clerk_webhook_signing_secret)
        payload = wh.verify(body, {
            "svix-id": svix_id,
            "svix-timestamp": svix_timestamp,
            "svix-signature": svix_signature,
        })
    except Exception:
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "reason": "INVALID_SVIX_SIGNATURE"},
        ) from None

    event_type = payload.get("type", "")
    if event_type not in _EVENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "validation_error",
                "reason": f"Unknown event type: {event_type}",
            },
        )

    data = payload.get("data", {})
    clerk_id = data.get("id", "")
    if not clerk_id:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "validation_error",
                "reason": "Missing user id in payload",
            },
        )

    session_factory = get_session_factory()
    repo = CourseCoreRepository(session_factory=session_factory)

    if event_type == "user.deleted":
        await repo.deactivate_user(clerk_id)
    elif event_type in ("user.created", "user.updated"):
        email = ""
        email_addresses = data.get("email_addresses", [])
        if email_addresses:
            email = email_addresses[0].get("email_address", "")

        first_name = data.get("first_name", "")
        last_name = data.get("last_name", "")
        display_name = f"{first_name} {last_name}".strip() or ""

        existing = await repo.find_user_by_clerk_id(clerk_id)
        if existing is not None:
            await repo.update_user_from_webhook(
                clerk_id, email=email, display_name=display_name
            )
        else:
            await repo.create_user(clerk_id, email, display_name)

    return {"status": "ok"}
