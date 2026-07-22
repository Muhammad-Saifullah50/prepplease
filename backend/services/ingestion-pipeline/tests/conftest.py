"""pytest conftest — sets DATABASE_URL for ingestion-pipeline integration tests."""

import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://exambrain:exambrain@localhost:5432/ingestion",
)
