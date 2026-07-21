"""``generate_exam`` pipeline (contracts/pipelines.md, US3).

Loads the latest blueprint, runs the generator agent (which retrieves
grounding chunks itself), validates structure/citations/rubric against the
blueprint with one corrective retry, then persists (FR-011..FR-015).
"""

import math
from typing import Any, Literal
from uuid import UUID

from agents.models.interface import Model
from pydantic import BaseModel

from exambrain_agents.errors import BlueprintRequiredError, ContentRequiredError
from exambrain_agents.generator.agent import build_generator_agent, generator_input
from exambrain_agents.runner import run_agent
from exambrain_agents.schemas.blueprint import BlueprintStructure
from exambrain_agents.schemas.generation import GeneratedExam

MARKS_TOLERANCE = 0.01


class GeneratedExamRecord(BaseModel):
    """Persisted generated exam (contracts/pipelines.md)."""

    id: UUID
    course_id: UUID
    blueprint_id: UUID
    blueprint_version: int
    exam: GeneratedExam
    status: Literal["ready", "needs_review"]
    needs_review_reasons: list[str]


async def generate_exam(
    course_id: UUID,
    *,
    embedder: Any = None,
    ingestion_repo: Any = None,
    course_repo: Any = None,
    exam_sim_repo: Any = None,
    generator_model: Model | None = None,
) -> GeneratedExamRecord:
    """Generate and persist a blueprint-faithful mock exam (FR-011)."""
    if embedder is None:
        from exambrain_shared.llm import LLMClient

        embedder = LLMClient()
    if ingestion_repo is None:
        from exambrain_agents.repositories.ingestion import IngestionRepository

        ingestion_repo = IngestionRepository()
    if course_repo is None:
        from exambrain_agents.repositories.course_core import CourseCoreRepository

        course_repo = CourseCoreRepository()
    if exam_sim_repo is None:
        from exambrain_agents.repositories.exam_sim import ExamSimRepository

        exam_sim_repo = ExamSimRepository()

    blueprint_row = await course_repo.latest_blueprint(course_id)
    if blueprint_row is None:
        raise BlueprintRequiredError(course_id)
    if not await ingestion_repo.course_has_content(course_id):
        raise ContentRequiredError(course_id)

    blueprint = BlueprintStructure.model_validate(blueprint_row["structure"])
    agent = build_generator_agent(course_id, embedder=embedder, repo=ingestion_repo)

    async def validate(exam: GeneratedExam) -> list[str]:
        return await _validate_exam(exam, blueprint, course_id, ingestion_repo)

    # run_agent_with_corrective_retry takes a sync validator; run the async
    # citation check around it: first attempt, then one corrective retry.
    exam: GeneratedExam = await run_agent(
        agent, generator_input(blueprint_row["structure"]), model=generator_model
    )
    failures = await validate(exam)
    if failures:
        corrective = (
            generator_input(blueprint_row["structure"])
            + "\n\nYour previous output failed validation:\n"
            + "\n".join(f"- {f}" for f in failures)
            + "\nProduce a corrected exam that resolves every failure."
        )
        exam = await run_agent(agent, corrective, model=generator_model)
        failures = await validate(exam)

    reasons = list(failures)
    if exam.ungrounded_topics:
        reasons.extend(f"ungrounded topic: {topic}" for topic in exam.ungrounded_topics)
    status: Literal["ready", "needs_review"] = "needs_review" if reasons else "ready"

    exam_id = await exam_sim_repo.insert_generated_exam(
        {
            "course_id": course_id,
            "blueprint_id": blueprint_row["id"],
            "blueprint_version": blueprint_row["version"],
            "content": exam.model_dump(mode="json", exclude={"rubric"}),
            "rubric": [e.model_dump(mode="json") for e in exam.rubric],
            "status": status,
            "needs_review_reasons": reasons,
        }
    )
    return GeneratedExamRecord(
        id=exam_id,
        course_id=course_id,
        blueprint_id=blueprint_row["id"],
        blueprint_version=blueprint_row["version"],
        exam=exam,
        status=status,
        needs_review_reasons=reasons,
    )


async def _validate_exam(
    exam: GeneratedExam,
    blueprint: BlueprintStructure,
    course_id: UUID,
    ingestion_repo: Any,
) -> list[str]:
    """Structural + citation + rubric validation vs the blueprint (FR-014)."""
    failures: list[str] = []

    # Section layout: names, types, counts, marks.
    if len(exam.sections) != len(blueprint.sections):
        failures.append(
            f"section count {len(exam.sections)} != blueprint {len(blueprint.sections)}"
        )
    for exam_section, bp_section in zip(
        exam.sections, blueprint.sections, strict=False
    ):
        if exam_section.question_type != bp_section.question_type:
            failures.append(
                f"section '{exam_section.name}' type "
                f"'{exam_section.question_type}' != blueprint "
                f"'{bp_section.question_type}'"
            )
        if len(exam_section.questions) != bp_section.question_count:
            failures.append(
                f"section '{exam_section.name}' has "
                f"{len(exam_section.questions)} questions, blueprint requires "
                f"{bp_section.question_count}"
            )
        section_marks = sum(q.marks for q in exam_section.questions)
        if not math.isclose(
            section_marks, bp_section.total_marks, abs_tol=MARKS_TOLERANCE
        ):
            failures.append(
                f"section '{exam_section.name}' marks {section_marks} != "
                f"blueprint {bp_section.total_marks}"
            )

    # Total marks: internal sum and blueprint total.
    question_marks = sum(q.marks for s in exam.sections for q in s.questions)
    if not math.isclose(exam.total_marks, question_marks, abs_tol=MARKS_TOLERANCE):
        failures.append(
            f"total_marks {exam.total_marks} != sum of question marks {question_marks}"
        )
    if not math.isclose(
        exam.total_marks, blueprint.total_marks, abs_tol=MARKS_TOLERANCE
    ):
        failures.append(
            f"total_marks {exam.total_marks} != blueprint total {blueprint.total_marks}"
        )

    # Citations: every question cites ≥1 chunk that exists for the course.
    questions = [q for s in exam.sections for q in s.questions]
    cited = {c for q in questions for c in q.source_chunk_ids}
    existing = await ingestion_repo.existing_chunk_ids(course_id, list(cited))
    for question in questions:
        if not question.source_chunk_ids:
            failures.append(f"question {question.number} cites no chunks")
        elif not any(c in existing for c in question.source_chunk_ids):
            failures.append(f"question {question.number} cites unknown chunk ids")

    # Rubric covers every question exactly (FR-013).
    rubric_numbers = [e.question_number for e in exam.rubric]
    question_numbers = [q.number for q in questions]
    for number in question_numbers:
        if number not in rubric_numbers:
            failures.append(f"rubric entry missing for question {number}")
    for entry in exam.rubric:
        if not entry.expected_points:
            failures.append(
                f"rubric for question {entry.question_number} has no expected points"
            )
    return failures
