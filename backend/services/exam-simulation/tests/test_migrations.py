"""Migration tests for the exam-sim ``generated_exams`` table (T029/T032).

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
PG = "postgresql+psycopg://exambrain:exambrain@localhost:5432/exam_sim"
PG_ASYNC = "postgresql+asyncpg://exambrain:exambrain@localhost:5432/exam_sim"


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


def test_generated_exams_round_trip() -> None:
    _alembic("upgrade", "head")
    engine = create_engine(PG)
    with engine.begin() as conn:
        exam_id = conn.execute(
            text(
                "INSERT INTO generated_exams"
                " (course_id, blueprint_id, blueprint_version, content, rubric)"
                " VALUES (gen_random_uuid(), gen_random_uuid(), 1,"
                " '{\"sections\": []}', '[]') RETURNING id"
            )
        ).scalar_one()
        row = conn.execute(
            text(
                "SELECT status, needs_review_reasons FROM generated_exams"
                f" WHERE id = '{exam_id}'"
            )
        ).one()
        assert row.status == "ready"  # server default
        assert row.needs_review_reasons == []

        # CHECK constraint rejects invalid status.
        with pytest.raises(Exception, match="ck_generated_exams_status"):
            conn.execute(
                text(
                    "INSERT INTO generated_exams"
                    " (course_id, blueprint_id, blueprint_version, content,"
                    " rubric, status) VALUES (gen_random_uuid(),"
                    " gen_random_uuid(), 1, '{}', '[]', 'bogus')"
                )
            )

    with engine.connect() as conn:
        for column in ("course_id", "status"):
            idx = conn.execute(
                text(
                    "SELECT indexdef FROM pg_indexes"
                    " WHERE tablename = 'generated_exams'"
                    f" AND indexdef ILIKE '%{column}%'"
                )
            ).fetchall()
            assert idx, f"index on generated_exams.{column} missing"

    _alembic("downgrade", "-1")
    with engine.connect() as conn:
        tables = {
            r[0]
            for r in conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            )
        }
    assert "generated_exams" not in tables
    engine.dispose()
