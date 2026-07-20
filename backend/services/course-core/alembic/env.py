"""Async alembic environment for the course-core service (course_core DB)."""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

import exambrain_shared.models  # noqa: F401  — register all ORM models
from exambrain_shared.db import Base

SERVICE = "course_core"

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

DEFAULT_DATABASE_URL = (
    "postgresql+asyncpg://exambrain:exambrain@localhost:5432/course_core"
)
config.set_main_option(
    "sqlalchemy.url", os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
)

target_metadata = Base.metadata


def include_object(
    obj: object, name: str, type_: str, reflected: bool, compare_to: object
) -> bool:
    """Restrict autogenerate/upgrade to this service's tables (FR-004)."""
    if type_ == "table":
        return getattr(obj, "info", {}).get("service") == SERVICE
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no DBAPI connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        include_object=include_object,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations through it."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
