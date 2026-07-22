"""add deadline, finished_by, answers, time_limit_minutes to exam_sessions

Revision ID: 003_exam_sim
Revises: 002_exam_sim
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "003_exam_sim"
down_revision: str | None = "002_exam_sim"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "exam_sessions",
        sa.Column("generated_exam_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "exam_sessions",
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "exam_sessions",
        sa.Column("finished_by", sa.Text(), nullable=True),
    )
    op.add_column(
        "exam_sessions",
        sa.Column("answers", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "exam_sessions",
        sa.Column("time_limit_minutes", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_exam_sessions_finished_by",
        "exam_sessions",
        "finished_by IN ('manual', 'deadline', 'lockout')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_exam_sessions_finished_by", "exam_sessions")
    op.drop_column("exam_sessions", "time_limit_minutes")
    op.drop_column("exam_sessions", "answers")
    op.drop_column("exam_sessions", "finished_by")
    op.drop_column("exam_sessions", "deadline")
    op.drop_column("exam_sessions", "generated_exam_id")
