"""Credential manager: read-only validation and restart-free rotation (US5).

No client construction or network I/O at import or ``__init__`` time.
Validation uses only read-only AWS calls (``sts:GetCallerIdentity``,
``iam:SimulatePrincipalPolicy`` — FR-017). Secret values never appear in
``__repr__``, logs, or error messages; errors reference the credential
*source* only (FR-019).
"""

from collections.abc import Callable, Coroutine, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from botocore.exceptions import ClientError

from exambrain_shared.config import Settings, get_settings
from exambrain_shared.errors import CredentialError, NotConfiguredError

DEFAULT_ACTIONS: tuple[str, ...] = (
    "s3:GetObject",
    "s3:PutObject",
    "s3:DeleteObject",
    "s3:ListBucket",
    "bedrock:InvokeModel",
)

_CREDENTIAL_CODES = {
    "ExpiredToken",
    "InvalidClientTokenId",
    "SignatureDoesNotMatch",
    "AuthFailure",
    "UnrecognizedClientException",
}


@dataclass(frozen=True)
class CallerIdentity:
    """Identity of the configured AWS principal (no secret fields)."""

    account_id: str
    arn: str
    user_id: str


@dataclass(frozen=True)
class PermissionStatus:
    """Verification outcome for one IAM action."""

    action: str
    state: Literal["allowed", "denied", "cannot_verify"]


@dataclass(frozen=True)
class ValidationReport:
    """Full read-only validation result (FR-017)."""

    identity: CallerIdentity | None
    permissions: tuple[PermissionStatus, ...]


class CredentialManager:
    """Manages AWS credentials: validation, rotation, zero leakage."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        sts_client_factory: Callable[[], Any] | None = None,
        iam_client_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._sts_client_factory = sts_client_factory
        self._iam_client_factory = iam_client_factory

    def __repr__(self) -> str:  # never include credential values (FR-019)
        return (
            f"{type(self).__name__}(configured={self.is_configured}, "
            f"region={self._settings.aws_region!r})"
        )

    @property
    def is_configured(self) -> bool:
        s = self._settings
        return bool(s.aws_access_key_id and s.aws_secret_access_key and s.aws_region)

    def refresh(self) -> None:
        """Re-read credentials from the environment/.env source (FR-018).

        Bypasses the ``get_settings`` cache so rotated values at the source
        are picked up without a process restart.
        """
        self._settings = Settings()

    def _require_config(self) -> None:
        if not self.is_configured:
            raise NotConfiguredError(
                "IAM",
                "set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and AWS_REGION",
            )

    def _client(self, service: str) -> Any:
        """Open an AWS client context — credentials read at call time."""
        factory = (
            self._sts_client_factory if service == "sts" else self._iam_client_factory
        )
        if factory is not None:
            return factory()
        import aioboto3

        s = self._settings
        session = aioboto3.Session(
            aws_access_key_id=s.aws_access_key_id,
            aws_secret_access_key=s.aws_secret_access_key,
            region_name=s.aws_region,
        )
        return session.client(service)

    @staticmethod
    def _map_error(exc: ClientError) -> Exception:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code in _CREDENTIAL_CODES:
            return CredentialError(
                f"AWS credentials rejected ({code}) — check the configured "
                "credential source (environment / .env file)"
            )
        fallback: Exception = exc
        return fallback

    def validate_token(self, token: str) -> dict[str, Any]:
        """Legacy stub surface — out of AWS scope, retained for FR-021."""
        self._require_config()
        raise NotImplementedError("identity-token validation is not in scope")

    def get_caller_identity(self) -> "Coroutine[Any, Any, CallerIdentity]":
        """Resolve the configured principal via STS (read-only).

        Sync-checks configuration before creating the coroutine so the
        stub-era sync invocation still raises ``NotConfiguredError``
        immediately (FR-021).
        """
        self._require_config()
        return self._get_caller_identity()

    async def _get_caller_identity(self) -> CallerIdentity:
        async with self._client("sts") as sts:
            try:
                response = await sts.get_caller_identity()
            except ClientError as exc:
                raise self._map_error(exc) from exc
        return CallerIdentity(
            account_id=response["Account"],
            arn=response["Arn"],
            user_id=response["UserId"],
        )

    async def validate_permissions(
        self, actions: Sequence[str] | None = None
    ) -> ValidationReport:
        """Check each required permission read-only (FR-017).

        Uses ``iam:SimulatePrincipalPolicy``; if the caller lacks that
        permission, every action degrades to ``cannot_verify`` — never a
        false pass/fail.
        """
        self._require_config()
        action_list = tuple(actions or DEFAULT_ACTIONS)
        identity = await self.get_caller_identity()

        async with self._client("iam") as iam:
            try:
                response = await iam.simulate_principal_policy(
                    PolicySourceArn=identity.arn,
                    ActionNames=list(action_list),
                )
            except ClientError as exc:
                mapped = self._map_error(exc)
                if isinstance(mapped, CredentialError):
                    raise mapped from exc
                # Cannot simulate (e.g. AccessDenied) — degrade gracefully.
                return ValidationReport(
                    identity=identity,
                    permissions=tuple(
                        PermissionStatus(action=a, state="cannot_verify")
                        for a in action_list
                    ),
                )

        decisions = {
            r["EvalActionName"]: r["EvalDecision"]
            for r in response.get("EvaluationResults", [])
        }
        return ValidationReport(
            identity=identity,
            permissions=tuple(
                PermissionStatus(
                    action=a,
                    state=(
                        "allowed"
                        if decisions.get(a) == "allowed"
                        else "denied" if a in decisions else "cannot_verify"
                    ),
                )
                for a in action_list
            ),
        )


# Preserved name for existing imports and stub tests (FR-021).
IAMClient = CredentialManager
