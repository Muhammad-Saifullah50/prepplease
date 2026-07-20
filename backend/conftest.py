"""Workspace-wide pytest hooks.

Gates ``migration``-marked tests (anywhere in the workspace — root tests
and per-service tests) on the local docker Postgres being reachable, so a
plain ``uv run pytest`` stays hermetic (SC-007).
"""

import socket

import pytest

POSTGRES_HOST = "localhost"
POSTGRES_PORT = 5432


def _postgres_reachable() -> bool:
    try:
        with socket.create_connection((POSTGRES_HOST, POSTGRES_PORT), timeout=1):
            return True
    except OSError:
        return False


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip ``migration``-marked tests when local Postgres is unreachable."""
    if _postgres_reachable():
        return
    skip = pytest.mark.skip(reason="local Postgres unreachable — start docker stack")
    for item in items:
        if "migration" in item.keywords:
            item.add_marker(skip)
