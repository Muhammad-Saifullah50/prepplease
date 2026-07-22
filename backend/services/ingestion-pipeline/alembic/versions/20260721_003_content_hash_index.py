"""add content_hash, file_name, file_type, processing_completed_at to past_papers + unique index

Revision ID: 003_content_hash_index
Revises: 002_parsing_state
Create Date: 2026-07-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003_content_hash_index"
down_revision: str | None = "002_ingestion"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "past_papers",
        sa.Column(
            "content_hash",
            sa.Text(),
            nullable=True,
            comment="SHA-256 of file content for duplicate detection",
        ),
    )
    op.create_index(
        "ix_past_papers_content_hash",
        "past_papers",
        ["content_hash"],
        unique=True,
        postgresql_where=sa.text("content_hash IS NOT NULL"),
    )

    op.add_column(
        "past_papers",
        sa.Column(
            "file_name",
            sa.Text(),
            nullable=True,
            comment="Original upload filename",
        ),
    )

    op.add_column(
        "past_papers",
        sa.Column(
            "file_type",
            sa.Text(),
            nullable=True,
            comment="MIME type (application/pdf or application/vnd...pptx)",
        ),
    )

    op.add_column(
        "past_papers",
        sa.Column(
            "processing_completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When processing finished (completed or failed)",
        ),
    )


def downgrade() -> None:
    op.drop_column("past_papers", "processing_completed_at")
    op.drop_column("past_papers", "file_type")
    op.drop_column("past_papers", "file_name")
    op.drop_index("ix_past_papers_content_hash", table_name="past_papers")
    op.drop_column("past_papers", "content_hash")
