"""pytest conftest — DATABASE_URL + ensure_test_user for course-core."""

import os
import uuid

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://exambrain:exambrain@localhost:5432/course_core",
)

TEST_USER_CLERK_ID = "user_test123"
TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

TEST_USER: dict = {
    "id": TEST_USER_ID,
    "clerk_id": TEST_USER_CLERK_ID,
    "email": "test@example.com",
    "display_name": "Test User",
    "preferences": {},
}

_SYNC_DB_URL = "postgresql+psycopg://exambrain:exambrain@localhost:5432/course_core"


@pytest.fixture(autouse=True)
def ensure_test_user() -> None:
    """Synchronous fixture: creates the test user if the users table exists."""
    from sqlalchemy import create_engine, text

    engine = create_engine(_SYNC_DB_URL)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO users (id, clerk_id, email, display_name, "
                    "is_active, preferences) "
                    "VALUES (:id, :clerk_id, :email, :display_name, true, '{}') "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {
                    "id": TEST_USER_ID,
                    "clerk_id": TEST_USER_CLERK_ID,
                    "email": "test@example.com",
                    "display_name": "Test User",
                },
            )
    except Exception:
        pass  # tables may not exist (e.g. during migration tests)
    finally:
        engine.dispose()
