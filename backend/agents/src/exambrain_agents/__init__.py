"""ExamBrain agents library.

Public API: three typed pipeline entry points (``ingest_course_file``,
``generate_exam``, ``evaluate_submission``), the agent output schemas, and
the :class:`FakeModel` test double. External trace export is disabled at
import time (FR-022) — agent runs are observed only through the platform's
structured logging.
"""

from agents import set_tracing_disabled

set_tracing_disabled(True)  # FR-022: no external trace export, ever

from exambrain_agents.pipelines.generate import (  # noqa: E402
    GeneratedExamRecord,
    generate_exam,
)
from exambrain_agents.pipelines.ingest import (  # noqa: E402
    IngestResult,
    ingest_course_file,
)

__all__ = [
    "GeneratedExamRecord",
    "IngestResult",
    "generate_exam",
    "ingest_course_file",
]
