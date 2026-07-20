"""add past_papers.parsing_confidence + needs_review (Phase 2 agents)

Revision ID: 002_ingestion
Revises: 001_ingestion
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002_ingestion"
down_revision: str | None = "001_ingestion"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "past_papers",
        sa.Column("parsing_confidence", sa.Numeric(4, 3), nullable=True),
    )
    op.add_column(
        "past_papers",
        sa.Column(
            "needs_review",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    # Blueprint-eligibility filter: completed AND NOT needs_review (FR-009).
    op.create_index("ix_past_papers_needs_review", "past_papers", ["needs_review"])


def downgrade() -> None:
    op.drop_index("ix_past_papers_needs_review", table_name="past_papers")
    op.drop_column("past_papers", "needs_review")
    op.drop_column("past_papers", "parsing_confidence")
