"""Shared test fixtures: migration-marker gating and secret-leak capture.

Migration tests (marker ``migration``) require the docker-compose Postgres;
they are skipped automatically when it is unreachable so plain ``pytest``
runs stay hermetic (research R9). A suite-wide fixture captures all log
output and asserts no configured secret substring ever appears (SC-007).
"""

import logging
import socket

import pytest

POSTGRES_HOST = "localhost"
POSTGRES_PORT = 5432

# Secret values configured by tests; the suite-wide capture asserts none of
# these substrings ever reach a log line (FR-019, SC-007).
TRACKED_SECRETS: set[str] = {
    "fake-secret-value",  # test_llm.py / test_s3.py AWS secret
    "fake-secret-value-do-not-log",  # test_iam.py AWS secret
    "first-secret",  # test_iam.py rotation test
    "old-secret",  # test_iam.py rotation test
    "sk-x",  # test_llm.py API key
}


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


class _SecretScanHandler(logging.Handler):
    """Root-logger handler recording any log line containing a tracked secret."""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.leaks: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
        except Exception:  # pragma: no cover - defensive
            message = str(record.msg)
        for secret in TRACKED_SECRETS:
            if secret and secret in message:
                self.leaks.append(message)


@pytest.fixture(autouse=True, scope="session")
def no_secret_leak_in_logs() -> "logging.Handler":
    """Suite-wide guard: no configured secret substring in any log output."""
    handler = _SecretScanHandler()
    logging.getLogger().addHandler(handler)
    yield handler
    logging.getLogger().removeHandler(handler)
    assert not handler.leaks, f"secret values leaked into logs: {handler.leaks!r}"
