"""add clerk_id, is_active, preferences to users; archived_at, paper_count to courses

Revision ID: 003_foundation_services
Revises: 002_instructors
Create Date: 2026-07-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "003_foundation_services"
down_revision: str | None = "002_course_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "clerk_id",
            sa.Text(),
            nullable=True,
            comment="Clerk user ID (user_xxx)",
        ),
    )
    op.create_index("ix_users_clerk_id", "users", ["clerk_id"], unique=True)

    op.add_column(
        "users",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Soft-delete flag; false on user.deleted webhook",
        ),
    )

    op.add_column(
        "users",
        sa.Column(
            "preferences",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Notification preferences, theme, etc.",
        ),
    )

    op.add_column(
        "courses",
        sa.Column(
            "archived_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Non-null = soft-deleted/archived",
        ),
    )
    op.create_index(
        "ix_courses_archived_at",
        "courses",
        ["archived_at"],
        postgresql_where=sa.text("archived_at IS NULL"),
    )

    op.add_column(
        "courses",
        sa.Column(
            "paper_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Denormalized counter for dashboard",
        ),
    )


def downgrade() -> None:
    op.drop_column("courses", "paper_count")
    op.drop_index("ix_courses_archived_at", table_name="courses")
    op.drop_column("courses", "archived_at")
    op.drop_column("users", "preferences")
    op.drop_column("users", "is_active")
    op.drop_index("ix_users_clerk_id", table_name="users")
    op.drop_column("users", "clerk_id")
