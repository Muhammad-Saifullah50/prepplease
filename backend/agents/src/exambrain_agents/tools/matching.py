"""Deterministic name-matching tools (contracts/tools.md, research R4).

``normalize_name`` is the single shared normalization definition (FR-005):
tools, pipeline, and repositories all use it. Scoring is rapidfuzz —
deterministic and testable without a model. All read-only (FR-019).
"""

import re
import uuid
from typing import Any

from rapidfuzz import fuzz

_HONORIFICS = frozenset(
    {
        "dr",
        "prof",
        "professor",
        "mr",
        "ms",
        "mrs",
        "miss",
        "engr",
        "sir",
        "madam",
    }
)
_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_name(raw: str) -> str:
    """Normalize an instructor name for comparison and storage (FR-005).

    Lowercase, strip honorifics/titles, strip punctuation, collapse
    whitespace. Pure and idempotent.
    """
    lowered = _PUNCTUATION.sub(" ", raw.lower())
    words = [w for w in lowered.split() if w not in _HONORIFICS]
    return " ".join(words)


def score_name_candidates(name: str, candidates: list[str]) -> list[dict[str, Any]]:
    """rapidfuzz similarity of ``name`` vs each candidate, sorted desc.

    Inputs are normalized first; scores are token_sort_ratio scaled to
    [0, 1]. The banding decision (FR-007) uses these scores and is
    re-enforced in pipeline validation.
    """
    normalized = normalize_name(name)
    scored = [
        {
            "candidate": candidate,
            "score": round(
                fuzz.token_sort_ratio(normalized, normalize_name(candidate)) / 100.0,
                4,
            ),
        }
        for candidate in candidates
    ]
    return sorted(scored, key=lambda c: (-c["score"], c["candidate"]))


async def list_known_instructors(
    course_context: uuid.UUID | None = None, *, repo: Any = None
) -> list[dict[str, Any]]:
    """Read-only query of stored instructors for candidate scoring."""
    if repo is None:
        from exambrain_agents.repositories.course_core import CourseCoreRepository

        repo = CourseCoreRepository()
    rows = await repo.list_instructors()
    return [
        {
            "instructor_id": row["id"],
            "normalized_name": row["normalized_name"],
            "display_name": row["display_name"],
        }
        for row in rows
    ]
