"""Hermetic checks of the shared ORM models' metadata (US1, FR-004).

Verifies the service-tag partitioning convention and key schema properties
without a database connection.
"""

from sqlalchemy import CheckConstraint, UniqueConstraint

from exambrain_shared.models import (
    Base,
    Course,
    DocumentChunk,
    ExamBlueprint,
    ExamSession,
    PastPaper,
    Result,
    User,
)

EXPECTED_SERVICES = {
    "users": "course_core",
    "courses": "course_core",
    "exam_blueprints": "course_core",
    "results": "course_core",
    "past_papers": "ingestion",
    "document_chunks": "ingestion",
    "exam_sessions": "exam_sim",
    "generated_exams": "exam_sim",
}


def test_every_table_is_service_tagged() -> None:
    assert set(Base.metadata.tables) == set(EXPECTED_SERVICES)
    for name, table in Base.metadata.tables.items():
        assert table.info.get("service") == EXPECTED_SERVICES[name], name


def test_timestamp_mixin_columns_everywhere() -> None:
    for table in Base.metadata.tables.values():
        cols = set(table.columns.keys())
        assert {"id", "created_at", "updated_at"} <= cols, table.name


def test_blueprint_versioning_unique_constraint() -> None:
    constraints = {
        c.name
        for c in ExamBlueprint.__table__.constraints
        if isinstance(c, UniqueConstraint)
    }
    assert "uq_exam_blueprints_course_version" in constraints


def test_result_session_ref_unique() -> None:
    assert Result.__table__.columns["exam_session_id"].unique


def test_embedding_is_vector_1024() -> None:
    embedding = DocumentChunk.__table__.columns["embedding"]
    assert embedding.nullable
    assert getattr(embedding.type, "dim", None) == 1024


def test_status_check_constraints() -> None:
    paper_checks = {
        c.name
        for c in PastPaper.__table__.constraints
        if isinstance(c, CheckConstraint)
    }
    assert "ck_past_papers_processing_status" in paper_checks
    session_checks = {
        c.name
        for c in ExamSession.__table__.constraints
        if isinstance(c, CheckConstraint)
    }
    assert "ck_exam_sessions_status" in session_checks


def test_cascade_fks_within_course_core() -> None:
    for model, column in ((Course, "user_id"), (Result, "course_id")):
        fks = list(model.__table__.columns[column].foreign_keys)
        assert fks and fks[0].ondelete == "CASCADE", (model, column)


def test_identifier_only_cross_db_refs_have_no_fk() -> None:
    assert not list(PastPaper.__table__.columns["course_id"].foreign_keys)
    assert not list(ExamSession.__table__.columns["user_id"].foreign_keys)
    assert not list(User.__table__.columns["id"].foreign_keys)
