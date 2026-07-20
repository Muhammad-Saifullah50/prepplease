"""Deferred-error behavior of the IAM/LLM/S3 stubs (FR-017).

Importing the modules never raises; instantiating without config succeeds;
invoking any operation without config raises ``NotConfiguredError``.
"""

import pytest

from exambrain_shared.config import Settings
from exambrain_shared.errors import NotConfiguredError
from exambrain_shared.iam import IAMClient
from exambrain_shared.llm import LLMClient
from exambrain_shared.s3 import S3Adapter

EMPTY = Settings(_env_file=None, aws_access_key_id=None, llm_provider=None)


def test_import_and_instantiate_never_raises() -> None:
    """Constructing every stub with zero config must succeed (FR-005)."""
    assert not IAMClient(EMPTY).is_configured
    assert not LLMClient(EMPTY).is_configured
    assert not S3Adapter(EMPTY).is_configured


def test_iam_operations_raise_not_configured() -> None:
    client = IAMClient(EMPTY)
    with pytest.raises(NotConfiguredError, match="IAM is not configured"):
        client.validate_token("token")
    with pytest.raises(NotConfiguredError):
        client.get_caller_identity()


async def test_llm_operations_raise_not_configured() -> None:
    client = LLMClient(EMPTY)
    with pytest.raises(NotConfiguredError, match="LLM is not configured"):
        await client.complete("hello")
    with pytest.raises(NotConfiguredError):
        await client.embed("hello")


async def test_s3_operations_raise_not_configured() -> None:
    adapter = S3Adapter(EMPTY)
    with pytest.raises(NotConfiguredError, match="S3 is not configured"):
        await adapter.upload("key", b"data")
    with pytest.raises(NotConfiguredError):
        await adapter.download("key")
    with pytest.raises(NotConfiguredError):
        await adapter.delete("key")


def test_not_configured_error_is_runtime_error() -> None:
    assert issubclass(NotConfiguredError, RuntimeError)
    err = NotConfiguredError("IAM", "detail here")
    assert err.component == "IAM"
    assert "detail here" in str(err)
