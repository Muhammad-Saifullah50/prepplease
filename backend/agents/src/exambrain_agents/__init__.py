"""ExamBrain agents library.

Public API: three typed pipeline entry points (``ingest_course_file``,
``generate_exam``, ``evaluate_submission``), the agent output schemas, and
the :class:`FakeModel` test double. External trace export is disabled at
import time (FR-022) — agent runs are observed only through the platform's
structured logging.
"""

from agents import set_tracing_disabled

set_tracing_disabled(True)  # FR-022: no external trace export, ever

from exambrain_agents.pipelines.evaluate import (  # noqa: E402
    EvaluationRecord,
    SubmittedAnswer,
    evaluate_submission,
)
from exambrain_agents.pipelines.generate import (  # noqa: E402
    GeneratedExamRecord,
    generate_exam,
)
from exambrain_agents.pipelines.ingest import (  # noqa: E402
    IngestResult,
    ingest_course_file,
)
from exambrain_agents.schemas.alignment import (  # noqa: E402
    Candidate,
    InstructorResolution,
)
from exambrain_agents.schemas.blueprint import (  # noqa: E402
    BlueprintSection,
    BlueprintStructure,
    PaperEvidence,
    TopicWeight,
)
from exambrain_agents.schemas.evaluation import (  # noqa: E402
    EvaluationOutput,
    QuestionScore,
)
from exambrain_agents.schemas.generation import (  # noqa: E402
    ExamQuestion,
    ExamSection,
    GeneratedExam,
    RubricEntry,
)
from exambrain_agents.schemas.parsing import (  # noqa: E402
    ParsedDocument,
    ParsedQuestion,
    ParsedSection,
    ParsedSlide,
)
from exambrain_agents.testing import (  # noqa: E402
    FakeModel,
    FinalOutput,
    ToolCall,
)

__all__ = [
    # Pipelines (FR-020)
    "evaluate_submission",
    "generate_exam",
    "ingest_course_file",
    "EvaluationRecord",
    "GeneratedExamRecord",
    "IngestResult",
    "SubmittedAnswer",
    # Agent output schemas
    "BlueprintSection",
    "BlueprintStructure",
    "Candidate",
    "EvaluationOutput",
    "ExamQuestion",
    "ExamSection",
    "GeneratedExam",
    "InstructorResolution",
    "PaperEvidence",
    "ParsedDocument",
    "ParsedQuestion",
    "ParsedSection",
    "ParsedSlide",
    "QuestionScore",
    "RubricEntry",
    "TopicWeight",
    # Testing (FR-024)
    "FakeModel",
    "FinalOutput",
    "ToolCall",
]
