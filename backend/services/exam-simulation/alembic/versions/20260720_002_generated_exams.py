"""create generated_exams (Phase 2 agents)

Revision ID: 002_exam_sim
Revises: 001_exam_sim
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "002_exam_sim"
down_revision: str | None = "001_exam_sim"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "generated_exams",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # Identifier-only refs to the course-core DB (no cross-DB FKs).
        sa.Column("course_id", UUID(as_uuid=True), nullable=False),
        sa.Column("blueprint_id", UUID(as_uuid=True), nullable=False),
        sa.Column("blueprint_version", sa.Integer(), nullable=False),
        sa.Column("content", JSONB(), nullable=False),
        sa.Column("rubric", JSONB(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'ready'"),
        ),
        sa.Column(
            "needs_review_reasons",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('ready', 'needs_review')",
            name="ck_generated_exams_status",
        ),
    )
    op.create_index("ix_generated_exams_course_id", "generated_exams", ["course_id"])
    op.create_index("ix_generated_exams_status", "generated_exams", ["status"])


def downgrade() -> None:
    op.drop_index("ix_generated_exams_status", table_name="generated_exams")
    op.drop_index("ix_generated_exams_course_id", table_name="generated_exams")
    op.drop_table("generated_exams")
