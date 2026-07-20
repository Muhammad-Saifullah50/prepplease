"""Matching-tool tests (T039, FR-005) — deterministic, no model."""

import uuid

from exambrain_agents.tools.matching import (
    list_known_instructors,
    normalize_name,
    score_name_candidates,
)
from tests.conftest import FakeCourseCoreRepo


class TestNormalizeName:
    def test_case_folding(self) -> None:
        assert normalize_name("ABDUL Rahman") == "abdul rahman"

    def test_strips_honorifics(self) -> None:
        assert normalize_name("Dr. Abdul Rahman") == "abdul rahman"
        assert normalize_name("Prof Abdul Rahman") == "abdul rahman"
        assert normalize_name("Professor Abdul Rahman") == "abdul rahman"
        assert normalize_name("Engr. Abdul Rahman") == "abdul rahman"
        assert normalize_name("Mr Abdul Rahman") == "abdul rahman"
        assert normalize_name("Ms. Ayesha Khan") == "ayesha khan"

    def test_strips_punctuation(self) -> None:
        assert normalize_name("A. Rahman") == "a rahman"
        assert normalize_name("Rahman, Abdul") == "rahman abdul"

    def test_collapses_whitespace(self) -> None:
        assert normalize_name("  abdul   rahman  ") == "abdul rahman"

    def test_idempotent(self) -> None:
        once = normalize_name("Dr. A. Rahman")
        assert normalize_name(once) == once


class TestScoreNameCandidates:
    def test_deterministic_and_sorted_desc(self) -> None:
        candidates = ["abdul rahman", "ayesha khan", "abdul raheem"]
        first = score_name_candidates("abdul rahman", candidates)
        second = score_name_candidates("abdul rahman", candidates)
        assert first == second
        scores = [c["score"] for c in first]
        assert scores == sorted(scores, reverse=True)
        assert first[0]["candidate"] == "abdul rahman"
        assert first[0]["score"] == 1.0

    def test_scores_in_unit_range(self) -> None:
        results = score_name_candidates("x y z", ["completely different name"])
        assert all(0.0 <= c["score"] <= 1.0 for c in results)

    def test_token_reorder_scores_high(self) -> None:
        results = score_name_candidates("rahman abdul", ["abdul rahman"])
        assert results[0]["score"] >= 0.9

    def test_empty_candidates(self) -> None:
        assert score_name_candidates("abdul rahman", []) == []


async def test_list_known_instructors_read_only_shape(
    course_repo: FakeCourseCoreRepo,
) -> None:
    iid = course_repo.add_instructor("abdul rahman", "Dr. Abdul Rahman")
    results = await list_known_instructors(repo=course_repo)
    assert results == [
        {
            "instructor_id": iid,
            "normalized_name": "abdul rahman",
            "display_name": "Dr. Abdul Rahman",
        }
    ]
    assert isinstance(results[0]["instructor_id"], uuid.UUID)
