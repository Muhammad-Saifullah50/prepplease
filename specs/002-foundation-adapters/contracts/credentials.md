# Contract: Credential Manager (`exambrain_shared.iam`)

Read-only credential validation, restart-free rotation, and zero-leak guarantees. Replaces the `IAMClient` stub in-place; existing surface (`is_configured`, `get_caller_identity`, `validate_token`) preserved with real implementations, plus new validation/rotation methods (FR-017–FR-020, FR-021).

## Interface

```python
class CredentialManager:  # exported alongside IAMClient (IAMClient = CredentialManager alias or subclass)
    def __init__(self, settings: Settings | None = None) -> None: ...
    @property
    def is_configured(self) -> bool: ...   # aws key id + secret + region

    def refresh(self) -> None: ...
        # re-reads credentials from the environment/.env source, bypassing the
        # settings cache — subsequent operations use new values (FR-018)

    async def get_caller_identity(self) -> CallerIdentity: ...
        # STS GetCallerIdentity (read-only; also proves credentials are live)

    async def validate_permissions(
        self, actions: Sequence[str] | None = None
    ) -> ValidationReport: ...
        # default action list: s3:GetObject, s3:PutObject, s3:DeleteObject,
        # s3:ListBucket, bedrock:InvokeModel
        # via iam:SimulatePrincipalPolicy — read-only, no mutating calls (FR-017)


@dataclass(frozen=True)
class CallerIdentity:
    account_id: str
    arn: str
    user_id: str

@dataclass(frozen=True)
class PermissionStatus:
    action: str
    state: Literal["allowed", "denied", "cannot_verify"]

@dataclass(frozen=True)
class ValidationReport:
    identity: CallerIdentity | None
    permissions: tuple[PermissionStatus, ...]
```

`validate_token` (stub legacy) remains but is out of AWS scope — retained raising `NotImplementedError` only if still unused by any caller, or removed if the existing test suite is the sole consumer and updated accordingly; decision at task time with minimal-diff rule. Existing `test_stubs.py` expectations for not-configured behavior must keep passing (FR-021).

## Error contract

| Condition | Raises / Result |
|---|---|
| Config absent | `NotConfiguredError("IAM", ...)` at call time |
| Expired/invalid credentials | `CredentialError` — message names the credential *source*, never the value (FR-019) |
| Caller lacks `iam:SimulatePrincipalPolicy` | no raise — affected actions report `state="cannot_verify"` (edge case: no false pass/fail) |
| Network failure | underlying connection error surfaced |

## Behavioral guarantees

- Validation performs only read-only cloud calls: `sts:GetCallerIdentity`, `iam:SimulatePrincipalPolicy` (FR-017); completes < 10 s (SC-007).
- `refresh()` + per-call credential reads mean rotation at the source requires no process restart; the S3 and LLM adapters read from the same settings source and inherit rotation (FR-018).
- No secret value ever appears in logs, `repr`, error messages, or exception chains; dataclasses exclude secret fields entirely (FR-019). Suite-wide log-capture test asserts no configured secret substring appears anywhere (SC-007).
- Credentials are never written to disk by the application; accepted sources are env vars and gitignored local env files only (FR-020).

## Test contract (simulated STS/IAM)

- Fake STS returning identity → `CallerIdentity` fields populated.
- Fake simulate-policy with mixed allow/deny → report states match per action.
- Fake raising AccessDenied on simulate-policy → all actions `cannot_verify`, no exception.
- Change env credential values + `refresh()` → subsequent fake call receives new values (no restart).
- Log capture across LLM/S3/IAM tests → zero occurrences of any secret string.
