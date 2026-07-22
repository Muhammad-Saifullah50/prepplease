"""pytest fixtures for exam-simulation tests."""

import pytest


@pytest.fixture
def redis_url() -> str:
    return "redis://localhost:6379/9"


@pytest.fixture
async def attempt_state_cache(redis_url: str):
    from exambrain_shared.redis import AttemptStateCache

    cache = AttemptStateCache()
    try:
        yield cache
    finally:
        await cache.aclose()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
