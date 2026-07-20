"""Migration tests for the ingestion DB parsing-state columns (T013/T019).

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
PG = "postgresql+psycopg://exambrain:exambrain@localhost:5432/ingestion"
PG_ASYNC = "postgresql+asyncpg://exambrain:exambrain@localhost:5432/ingestion"


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


def test_parsing_state_columns_round_trip() -> None:
    """002 adds parsing_confidence + needs_review with the right defaults."""
    _alembic("upgrade", "head")
    engine = create_engine(PG)
    with engine.begin() as conn:
        paper_id = conn.execute(
            text(
                "INSERT INTO past_papers (course_id, s3_key)"
                " VALUES (gen_random_uuid(), 'k.pdf') RETURNING id"
            )
        ).scalar_one()
        row = conn.execute(
            text(
                "SELECT parsing_confidence, needs_review FROM past_papers"
                f" WHERE id = '{paper_id}'"
            )
        ).one()
        assert row.parsing_confidence is None  # NULL until parsed
        assert row.needs_review is False  # server default

        conn.execute(
            text(
                "UPDATE past_papers SET parsing_confidence = 0.875,"
                f" needs_review = true WHERE id = '{paper_id}'"
            )
        )
        row = conn.execute(
            text(
                "SELECT parsing_confidence, needs_review FROM past_papers"
                f" WHERE id = '{paper_id}'"
            )
        ).one()
        assert float(row.parsing_confidence) == 0.875
        assert row.needs_review is True

    with engine.connect() as conn:
        # needs_review is indexed for the blueprint-eligibility filter.
        idx = conn.execute(
            text(
                "SELECT indexdef FROM pg_indexes"
                " WHERE tablename = 'past_papers'"
                " AND indexdef ILIKE '%needs_review%'"
            )
        ).fetchall()
        assert idx, "needs_review index missing on past_papers"

    # Downgrade to 001 removes the columns but keeps the table.
    _alembic("downgrade", "-1")
    with engine.connect() as conn:
        cols = {
            r[0]
            for r in conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns"
                    " WHERE table_name = 'past_papers'"
                )
            )
        }
    assert "parsing_confidence" not in cols
    assert "needs_review" not in cols
    engine.dispose()
