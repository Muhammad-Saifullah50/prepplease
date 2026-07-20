"""Credential manager tests with fake STS/IAM clients (research R8/R9, US5)."""

import logging

import pytest
from botocore.exceptions import ClientError

from exambrain_shared.config import Settings
from exambrain_shared.errors import CredentialError, NotConfiguredError
from exambrain_shared.iam import (
    DEFAULT_ACTIONS,
    CallerIdentity,
    CredentialManager,
    IAMClient,
)

SECRET = "fake-secret-value-do-not-log"

CONFIGURED = Settings(
    _env_file=None,
    aws_access_key_id="AKIAFAKEFAKEFAKE",
    aws_secret_access_key=SECRET,
    aws_region="eu-west-1",
)
EMPTY = Settings(_env_file=None, aws_access_key_id=None)


def _client_error(code: str, operation: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, operation)


class FakeSTS:
    def __init__(self, *, error: ClientError | None = None) -> None:
        self.error = error
        self.credentials_seen: list[str | None] = []

    async def __aenter__(self) -> "FakeSTS":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def get_caller_identity(self) -> dict[str, str]:
        if self.error:
            raise self.error
        return {
            "Account": "123456789012",
            "Arn": "arn:aws:iam::123456789012:user/exambrain",
            "UserId": "AIDAEXAMPLE",
        }


class FakeIAM:
    def __init__(
        self,
        *,
        denied_actions: set[str] | None = None,
        error: ClientError | None = None,
    ) -> None:
        self.denied = denied_actions or set()
        self.error = error

    async def __aenter__(self) -> "FakeIAM":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def simulate_principal_policy(
        self, *, PolicySourceArn: str, ActionNames: list[str]
    ) -> dict[str, list[dict[str, str]]]:
        if self.error:
            raise self.error
        return {
            "EvaluationResults": [
                {
                    "EvalActionName": a,
                    "EvalDecision": "implicitDeny" if a in self.denied else "allowed",
                }
                for a in ActionNames
            ]
        }


def _manager(
    settings: Settings = CONFIGURED,
    sts: FakeSTS | None = None,
    iam: FakeIAM | None = None,
) -> CredentialManager:
    return CredentialManager(
        settings,
        sts_client_factory=lambda: sts or FakeSTS(),
        iam_client_factory=lambda: iam or FakeIAM(),
    )


async def test_get_caller_identity_returns_dataclass() -> None:
    manager = _manager(sts=FakeSTS())
    identity = await manager.get_caller_identity()
    assert isinstance(identity, CallerIdentity)
    assert identity.account_id == "123456789012"
    assert identity.arn.endswith("user/exambrain")
    assert identity.user_id == "AIDAEXAMPLE"


async def test_validate_permissions_mixed_allow_deny() -> None:
    denied = {"s3:DeleteObject"}
    manager = _manager(iam=FakeIAM(denied_actions=denied))
    report = await manager.validate_permissions()
    states = {p.action: p.state for p in report.permissions}
    assert set(states) == set(DEFAULT_ACTIONS)
    assert states["s3:DeleteObject"] == "denied"
    assert states["s3:GetObject"] == "allowed"
    assert states["bedrock:InvokeModel"] == "allowed"


async def test_simulate_access_denied_degrades_to_cannot_verify() -> None:
    manager = _manager(
        iam=FakeIAM(error=_client_error("AccessDenied", "SimulatePrincipalPolicy"))
    )
    report = await manager.validate_permissions()
    assert all(p.state == "cannot_verify" for p in report.permissions)


async def test_expired_credentials_raise_credential_error() -> None:
    manager = _manager(
        sts=FakeSTS(error=_client_error("ExpiredToken", "GetCallerIdentity"))
    )
    with pytest.raises(CredentialError) as excinfo:
        await manager.get_caller_identity()
    assert not isinstance(excinfo.value, NotConfiguredError)
    assert SECRET not in str(excinfo.value)


async def test_refresh_picks_up_rotated_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAOLDOLDOLDOLD")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "old-secret")
    monkeypatch.setenv("AWS_REGION", "eu-west-1")
    manager = CredentialManager(
        sts_client_factory=lambda: FakeSTS(), iam_client_factory=lambda: FakeIAM()
    )
    assert manager.is_configured
    first_key = manager._settings.aws_access_key_id

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIANEWNEWNEWNEW")
    manager.refresh()
    assert manager._settings.aws_access_key_id == "AKIANEWNEWNEWNEW"
    assert first_key != manager._settings.aws_access_key_id


def test_not_configured_and_iam_alias() -> None:
    manager = _manager(EMPTY)
    with pytest.raises(NotConfiguredError, match="IAM"):
        manager.validate_token("token")
    # IAMClient preserved for existing imports (FR-021).
    assert issubclass(IAMClient, CredentialManager) or IAMClient is CredentialManager


def test_repr_and_logs_never_contain_secrets(
    caplog: pytest.LogCaptureFixture,
) -> None:
    manager = _manager()
    assert SECRET not in repr(manager)
    assert SECRET not in str(manager)
    with caplog.at_level(logging.DEBUG):
        logging.getLogger("test").debug("manager state: %r", manager)
    assert SECRET not in caplog.text


async def test_rotation_flows_to_llm_and_s3_adapters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LLM/S3 adapters read credentials from settings at call time (FR-018)."""
    from exambrain_shared.llm import LLMClient
    from exambrain_shared.s3 import S3Adapter

    settings = Settings(
        _env_file=None,
        llm_provider="bedrock",
        llm_model="bedrock/model",
        aws_access_key_id="AKIAFIRST",
        aws_secret_access_key="first-secret",
        aws_region="eu-west-1",
        s3_bucket="b",
    )
    llm = LLMClient(settings)
    # Credential kwargs are computed per call from current settings.
    assert llm._credential_kwargs()["aws_access_key_id"] == "AKIAFIRST"
    object.__setattr__(settings, "aws_access_key_id", "AKIAROTATED")
    assert llm._credential_kwargs()["aws_access_key_id"] == "AKIAROTATED"

    s3 = S3Adapter(settings)
    assert s3._settings.aws_access_key_id == "AKIAROTATED"
