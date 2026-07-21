"""Typed errors raised at agent-pipeline boundaries (FR-023).

All types extend the shared ``RuntimeError``-based hierarchy in
``exambrain_shared.errors`` so callers can catch platform errors uniformly.
Messages never embed prompt/response/document text.
"""


class AgentTurnLimitError(RuntimeError):
    """An agent exceeded its ``max_turns`` interaction budget."""

    def __init__(self, agent_name: str, max_turns: int) -> None:
        super().__init__(f"agent '{agent_name}' exceeded its turn limit ({max_turns})")
        self.agent_name = agent_name
        self.max_turns = max_turns


class AgentOutputError(RuntimeError):
    """An agent's final output failed schema validation or was malformed."""

    def __init__(self, agent_name: str, detail: str | None = None) -> None:
        message = f"agent '{agent_name}' produced invalid output"
        if detail:
            message = f"{message}: {detail}"
        super().__init__(message)
        self.agent_name = agent_name


class ParsingFailedError(RuntimeError):
    """A document could not be parsed (encrypted, corrupt, or zero pages)."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"document parsing failed: {reason}")
        self.reason = reason


class ContentRequiredError(RuntimeError):
    """Exam generation was requested for a course with no ingested content."""

    def __init__(self, course_id: object) -> None:
        super().__init__(
            f"course {course_id} has no ingested course content; "
            "ingest course material before generating an exam"
        )


class BlueprintRequiredError(RuntimeError):
    """Exam generation was requested for a course with no blueprint."""

    def __init__(self, course_id: object) -> None:
        super().__init__(
            f"course {course_id} has no exam blueprint; "
            "ingest at least one past paper first"
        )


class UnsupportedFormatError(RuntimeError):
    """The stored file's format is not supported by ingestion this phase."""

    def __init__(self, s3_key: str) -> None:
        super().__init__(
            f"unsupported document format for '{s3_key}' (supported: .pdf, .pptx)"
        )
        self.s3_key = s3_key
