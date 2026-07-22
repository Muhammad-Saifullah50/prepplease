"""Dashboard, performance, and blueprint endpoints (FR-014, FR-015, FR-016)."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from course_core.auth import resolve_current_user
from exambrain_agents.repositories.course_core import CourseCoreRepository
from exambrain_shared.db import get_session_factory
from exambrain_shared.errors import ObjectNotFoundError

router = APIRouter(prefix="/v1", tags=["dashboard"])


@router.get("/dashboard/summary")
async def dashboard_summary(
    user: Annotated[dict[str, Any], Depends(resolve_current_user)],
) -> dict[str, Any]:
    session_factory = get_session_factory()
    repo = CourseCoreRepository(session_factory=session_factory)

    courses = await repo.list_courses(user["id"])

    result_courses = []
    for course in courses:
        blueprints = await repo.list_blueprints(course["id"])
        latest = blueprints[0] if blueprints else None
        results = await repo.list_results(course["id"])
        exam_count = len(results)
        avg_score = (
            sum(r["aggregate_score"] for r in results) / exam_count
            if exam_count
            else None
        )

        result_courses.append(
            {
                "course_id": str(course["id"]),
                "title": course["title"],
                "paper_count": course["paper_count"],
                "blueprint_version": latest["version"] if latest else None,
                "has_blueprint": latest is not None,
                "completed_exams": exam_count,
                "average_score": round(avg_score, 1) if avg_score is not None else None,
            }
        )

    return {"courses": result_courses}


@router.get("/courses/{course_id}/performance")
async def course_performance(
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

    results = await repo.list_results(course_id)
    exam_count = len(results)
    aggregate = (
        sum(r["aggregate_score"] for r in results) / exam_count
        if exam_count
        else 0
    )
    max_score = max((r["max_score"] for r in results), default=0)

    topic_scores: dict[str, list[float]] = {}
    for r in results:
        qs = r.get("question_scores", {})
        for topic_data in qs if isinstance(qs, list) else []:
            topic = topic_data.get("topic", "unknown")
            score = float(topic_data.get("score", 0))
            topic_scores.setdefault(topic, []).append(score)

    topic_breakdown = [
        {
            "topic": topic,
            "score": round(sum(scores) / len(scores), 1),
            "max": 100,
            "strength": "strong" if (sum(scores) / len(scores)) >= 70 else "weak",
        }
        for topic, scores in topic_scores.items()
    ]

    recent = [
        {
            "id": str(r["id"]),
            "score": r["aggregate_score"],
            "date": r["created_at"],
        }
        for r in results[:10]
    ]

    return {
        "aggregate_score": round(aggregate, 1),
        "max_score": max_score,
        "exam_count": exam_count,
        "topic_breakdown": topic_breakdown,
        "recent_exams": recent,
    }


@router.get("/courses/{course_id}/blueprint")
async def course_blueprint(
    course_id: uuid.UUID,
    user: Annotated[dict[str, Any], Depends(resolve_current_user)],
) -> dict[str, Any]:
    session_factory = get_session_factory()
    repo = CourseCoreRepository(session_factory=session_factory)

    blueprint = await repo.latest_blueprint(course_id)
    if blueprint is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "reason": "No blueprint available for this course",
            },
        )

    structure = blueprint.get("structure", {})
    return {
        "version": blueprint["version"],
        "sections": structure.get("sections", []),
        "topic_weights": structure.get("topic_weights", {}),
        "confidence_score": structure.get("confidence_score"),
        "created_at": blueprint.get("created_at"),
    }
