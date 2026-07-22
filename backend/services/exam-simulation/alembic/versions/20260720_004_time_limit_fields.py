"""add time_limit_minutes to generated_exams

Revision ID: 004_exam_sim
Revises: 003_exam_sim
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004_exam_sim"
down_revision: str | None = "003_exam_sim"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "generated_exams",
        sa.Column("time_limit_minutes", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("generated_exams", "time_limit_minutes")
