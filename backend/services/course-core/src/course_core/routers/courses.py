"""Course CRUD endpoints (FR-005, FR-006, FR-007)."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from course_core.auth import resolve_current_user
from exambrain_agents.repositories.course_core import CourseCoreRepository
from exambrain_shared.db import get_session_factory
from exambrain_shared.errors import ObjectNotFoundError

router = APIRouter(prefix="/v1/courses", tags=["courses"])


@router.post("", status_code=201)
async def create_course(
    body: dict[str, Any],
    user: Annotated[dict[str, Any], Depends(resolve_current_user)],
) -> dict[str, Any]:
    session_factory = get_session_factory()
    repo = CourseCoreRepository(session_factory=session_factory)

    course = await repo.create_course(
        user_id=user["id"],
        title=body.get("title", ""),
        code=body.get("code"),
        instructor_name=body.get("instructor_name"),
    )
    return course


@router.get("")
async def list_courses(
    user: Annotated[dict[str, Any], Depends(resolve_current_user)],
    include_archived: bool = False,
) -> dict[str, Any]:
    session_factory = get_session_factory()
    repo = CourseCoreRepository(session_factory=session_factory)

    courses = await repo.list_courses(user["id"], include_archived=include_archived)
    return {"courses": courses}


@router.get("/{course_id}")
async def get_course(
    course_id: uuid.UUID,
    user: Annotated[dict[str, Any], Depends(resolve_current_user)],
) -> dict[str, Any]:
    session_factory = get_session_factory()
    repo = CourseCoreRepository(session_factory=session_factory)

    try:
        course = await repo.get_course(course_id)
    except ObjectNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "reason": "Course not found"},
        ) from None

    if course.get("user_id") != user["id"]:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "reason": "not_course_owner"},
        )

    blueprints = await repo.list_blueprints(course_id)
    latest = blueprints[0] if blueprints else None
    results = await repo.list_results(course_id)
    exam_count = len(results)

    return {
        "id": str(course["id"]),
        "title": course["title"],
        "code": course["code"],
        "instructor_name": course["instructor_name"],
        "instructor_id": (
            str(course["instructor_id"]) if course.get("instructor_id") else None
        ),
        "paper_count": course["paper_count"],
        "archived_at": course.get("archived_at"),
        "blueprint_summary": latest,
        "exam_count": exam_count,
    }


@router.patch("/{course_id}")
async def update_course(
    course_id: uuid.UUID,
    body: dict[str, Any],
    user: Annotated[dict[str, Any], Depends(resolve_current_user)],
) -> dict[str, Any]:
    session_factory = get_session_factory()
    repo = CourseCoreRepository(session_factory=session_factory)

    try:
        course = await repo.get_course(course_id)
    except ObjectNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "reason": "Course not found"},
        ) from None

    if course.get("user_id") != user["id"]:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "reason": "not_course_owner"},
        )

    kwargs = {}
    for field in ("title", "code", "instructor_name"):
        if field in body:
            kwargs[field] = body[field]

    updated = await repo.update_course(course_id, **kwargs)
    return updated


@router.delete("/{course_id}", status_code=204)
async def archive_course(
    course_id: uuid.UUID,
    user: Annotated[dict[str, Any], Depends(resolve_current_user)],
) -> None:
    session_factory = get_session_factory()
    repo = CourseCoreRepository(session_factory=session_factory)

    try:
        course = await repo.get_course(course_id)
    except ObjectNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "reason": "Course not found"},
        ) from None

    if course.get("user_id") != user["id"]:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "reason": "not_course_owner"},
        )

    try:
        await repo.soft_delete_course(course_id)
    except ValueError:
        raise HTTPException(
            status_code=409,
            detail={"error": "conflict", "reason": "already_archived"},
        ) from None


@router.get("/{course_id}/blueprints")
async def blueprint_history(
    course_id: uuid.UUID,
    user: Annotated[dict[str, Any], Depends(resolve_current_user)],
) -> dict[str, Any]:
    session_factory = get_session_factory()
    repo = CourseCoreRepository(session_factory=session_factory)

    blueprints = await repo.list_blueprints(course_id)
    return {
        "blueprints": [
            {
                "version": b["version"],
                "created_at": b["created_at"],
                "confidence_score": b.get("confidence_score"),
            }
            for b in blueprints
        ]
    }
