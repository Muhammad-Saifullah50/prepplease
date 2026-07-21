"""Migration tests for course-core instructors tables (T038/T041).

Marker ``migration`` — requires the docker-compose Postgres; skipped
automatically when unreachable (workspace conftest).
"""

import os
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.migration

SERVICE_DIR = Path(__file__).resolve().parents[1]
PG = "postgresql+psycopg://exambrain:exambrain@localhost:5432/course_core"
PG_ASYNC = "postgresql+asyncpg://exambrain:exambrain@localhost:5432/course_core"


def _alembic(*args: str) -> None:
    result = subprocess.run(
        ["uv", "run", "alembic", *args],
        cwd=SERVICE_DIR,
        env={
            "DATABASE_URL": PG_ASYNC,
            "PATH": os.environ["PATH"],
            "HOME": os.environ.get("HOME", "/tmp"),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"alembic {args} failed:\n{result.stderr}"


@pytest.fixture(autouse=True)
def clean_slate() -> None:
    yield
    _alembic("downgrade", "base")


def test_instructors_round_trip() -> None:
    _alembic("upgrade", "head")
    engine = create_engine(PG)

    with engine.begin() as conn:
        instructor_id = conn.execute(
            text(
                "INSERT INTO instructors (normalized_name, display_name)"
                " VALUES ('abdul rahman', 'Dr. Abdul Rahman') RETURNING id"
            )
        ).scalar_one()
        user_id = conn.execute(
            text(
                "INSERT INTO users (email, display_name)"
                " VALUES ('a@b.c', 'A') RETURNING id"
            )
        ).scalar_one()
        course_id = conn.execute(
            text(
                "INSERT INTO courses (user_id, title, instructor_id)"
                f" VALUES ('{user_id}', 'Algo', '{instructor_id}') RETURNING id"
            )
        ).scalar_one()
        # instructor_resolutions row with candidates JSONB.
        conn.execute(
            text(
                "INSERT INTO instructor_resolutions"
                " (course_id, raw_name, normalized_name, instructor_id,"
                " outcome, confidence, candidates, needs_review) VALUES"
                f" ('{course_id}', 'Dr. A. Rahman', 'a rahman',"
                f" '{instructor_id}', 'needs_review', 0.8,"
                " '[{\"score\": 0.8}]', true)"
            )
        )

    # UNIQUE on normalized_name.
    with (
        pytest.raises(Exception, match="unique|duplicate"),
        engine.begin() as conn,
    ):
        conn.execute(
            text(
                "INSERT INTO instructors (normalized_name, display_name)"
                " VALUES ('abdul rahman', 'A. Rahman')"
            )
        )

    # CHECK constraint on outcome.
    with (
        pytest.raises(Exception, match="ck_instructor_resolutions_outcome"),
        engine.begin() as conn,
    ):
        conn.execute(
            text(
                "INSERT INTO instructor_resolutions"
                " (course_id, raw_name, normalized_name, outcome, confidence)"
                f" VALUES ('{course_id}', 'x', 'x', 'bogus', 0.5)"
            )
        )

    # FK SET NULL: deleting the instructor clears the course link.
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM instructors"))
        remaining = conn.execute(text("SELECT instructor_id FROM courses")).scalar_one()
        assert remaining is None

    _alembic("downgrade", "-1")
    with engine.connect() as conn:
        tables = {
            r[0]
            for r in conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            )
        }
        cols = {
            r[0]
            for r in conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns"
                    " WHERE table_name = 'courses'"
                )
            )
        }
    assert "instructors" not in tables
    assert "instructor_resolutions" not in tables
    assert "instructor_id" not in cols
    engine.dispose()
