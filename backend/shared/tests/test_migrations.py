"""Migration round-trip tests (marker ``migration`` — needs docker Postgres).

Per service: ``alembic upgrade head`` creates the expected tables, a
representative row inserts cleanly, and ``alembic downgrade base`` leaves
no orphaned objects. The ingestion DB additionally verifies the 1024-dim
vector column, cosine similarity ranking, and loud wrong-dimension failure
(spec US1 acceptance scenarios 1–4).
"""

import subprocess
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

pytestmark = pytest.mark.migration

BACKEND = Path(__file__).resolve().parents[2]

PG = "postgresql+psycopg://exambrain:exambrain@localhost:5432"
PG_ASYNC = "postgresql+asyncpg://exambrain:exambrain@localhost:5432"

SERVICES = {
    "course_core": {
        "dir": BACKEND / "services" / "course-core",
        "tables": {
            "users",
            "courses",
            "exam_blueprints",
            "results",
            "instructors",
            "instructor_resolutions",
        },
    },
    "ingestion": {
        "dir": BACKEND / "services" / "ingestion-pipeline",
        "tables": {"past_papers", "document_chunks"},
    },
    "exam_sim": {
        "dir": BACKEND / "services" / "exam-simulation",
        "tables": {"exam_sessions", "generated_exams"},
    },
}


def _alembic(service: str, *args: str) -> None:
    cfg = SERVICES[service]
    result = subprocess.run(
        ["uv", "run", "alembic", *args],
        cwd=cfg["dir"],
        env={
            "DATABASE_URL": f"{PG_ASYNC}/{service}",
            "PATH": __import__("os").environ["PATH"],
            "HOME": __import__("os").environ.get("HOME", "/tmp"),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"alembic {args} failed:\n{result.stderr}"


def _engine(db: str) -> Engine:
    return create_engine(f"{PG}/{db}")


def _table_names(engine: Engine) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                " AND tablename != 'alembic_version'"
            )
        )
        return {r[0] for r in rows}


@pytest.fixture(autouse=True)
def clean_slate() -> None:
    """Ensure every test starts and ends at downgrade base."""
    yield
    for service in SERVICES:
        _alembic(service, "downgrade", "base")


def test_course_core_round_trip() -> None:
    _alembic("course_core", "upgrade", "head")
    engine = _engine("course_core")
    assert _table_names(engine) == SERVICES["course_core"]["tables"]

    with engine.begin() as conn:
        user_id = conn.execute(
            text(
                "INSERT INTO users (email, display_name)"
                " VALUES ('a@b.c', 'A') RETURNING id"
            )
        ).scalar_one()
        course_id = conn.execute(
            text(
                "INSERT INTO courses (user_id, title)"
                f" VALUES ('{user_id}', 'Algorithms') RETURNING id"
            )
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO exam_blueprints (course_id, structure)"
                f" VALUES ('{course_id}', '{{}}')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO results (user_id, course_id, exam_session_id,"
                " question_scores, aggregate_score, max_score) VALUES"
                f" ('{user_id}', '{course_id}', '{uuid.uuid4()}', '{{}}', 10, 20)"
            )
        )

    # ON DELETE CASCADE: removing the user removes courses/results.
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM users"))
        assert conn.execute(text("SELECT count(*) FROM courses")).scalar_one() == 0
        assert conn.execute(text("SELECT count(*) FROM results")).scalar_one() == 0

    _alembic("course_core", "downgrade", "base")
    assert _table_names(engine) == set()
    engine.dispose()


def test_ingestion_round_trip_and_similarity() -> None:
    _alembic("ingestion", "upgrade", "head")
    engine = _engine("ingestion")
    assert _table_names(engine) == SERVICES["ingestion"]["tables"]

    course_id = uuid.uuid4()
    with engine.begin() as conn:
        paper_id = conn.execute(
            text(
                "INSERT INTO past_papers (course_id, s3_key)"
                f" VALUES ('{course_id}', 'courses/x/p.pdf') RETURNING id"
            )
        ).scalar_one()
        # Three chunks with distinct embedding directions for ranked similarity.
        for i in range(3):
            vec = [0.0] * 1024
            vec[i] = 1.0  # unit vector along axis i — distinct cosine distances
            if i > 0:
                vec[0] = 1.0 - i * 0.4  # decreasing alignment with the query
            conn.execute(
                text(
                    "INSERT INTO document_chunks"
                    " (course_id, past_paper_id, source_s3_key, content,"
                    " position, embedding) VALUES"
                    f" ('{course_id}', '{paper_id}', 'k', 'chunk {i}',"
                    f" {i}, '{vec}')"
                )
            )

    with engine.connect() as conn:
        query_vec = [1.0] + [0.0] * 1023
        rows = conn.execute(
            text(
                "SELECT content FROM document_chunks"
                f" WHERE embedding IS NOT NULL"
                f" ORDER BY embedding <=> '{query_vec}' LIMIT 3"
            )
        ).fetchall()
        assert rows[0][0] == "chunk 0"  # closest cosine match first

        # HNSW index exists on the embedding column.
        idx = conn.execute(
            text(
                "SELECT indexdef FROM pg_indexes"
                " WHERE tablename = 'document_chunks'"
                " AND indexdef ILIKE '%hnsw%'"
            )
        ).fetchall()
        assert idx, "HNSW index missing on document_chunks.embedding"

    # Wrong-dimension insert fails loudly.
    with engine.connect() as conn, pytest.raises(Exception, match="dimensions"):
        conn.execute(
            text(
                "INSERT INTO document_chunks"
                " (course_id, source_s3_key, content, position, embedding)"
                f" VALUES ('{course_id}', 'k', 'bad', 9, '{[1.0, 2.0]}')"
            )
        )

    _alembic("ingestion", "downgrade", "base")
    assert _table_names(engine) == set()
    engine.dispose()


def test_exam_sim_round_trip() -> None:
    _alembic("exam_sim", "upgrade", "head")
    engine = _engine("exam_sim")
    assert _table_names(engine) == SERVICES["exam_sim"]["tables"]

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO exam_sessions"
                " (user_id, course_id, exam_content, started_at) VALUES"
                f" ('{uuid.uuid4()}', '{uuid.uuid4()}', '{{}}', now())"
            )
        )
        # CHECK constraint rejects invalid status.
        with pytest.raises(Exception, match="ck_exam_sessions_status"):
            conn.execute(
                text(
                    "INSERT INTO exam_sessions"
                    " (user_id, course_id, exam_content, started_at, status)"
                    f" VALUES ('{uuid.uuid4()}', '{uuid.uuid4()}', '{{}}',"
                    " now(), 'bogus')"
                )
            )

    _alembic("exam_sim", "downgrade", "base")
    assert _table_names(engine) == set()
    engine.dispose()


def test_cross_service_isolation() -> None:
    """Each service's upgrade touches only its own database."""
    _alembic("course_core", "upgrade", "head")
    for other in ("ingestion", "exam_sim"):
        engine = _engine(other)
        assert _table_names(engine) == set(), f"{other} DB polluted"
        engine.dispose()
