"""add instructors, instructor_resolutions, courses.instructor_id

Revision ID: 002_course_core
Revises: 001_course_core
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "002_course_core"
down_revision: str | None = "001_course_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "instructors",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("normalized_name", sa.Text(), nullable=False, unique=True),
        sa.Column("display_name", sa.Text(), nullable=False),
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
    )

    op.create_table(
        "instructor_resolutions",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "course_id",
            UUID(as_uuid=True),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("raw_name", sa.Text(), nullable=False),
        sa.Column("normalized_name", sa.Text(), nullable=False),
        sa.Column(
            "instructor_id",
            UUID(as_uuid=True),
            sa.ForeignKey("instructors.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False),
        sa.Column(
            "candidates",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "needs_review",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
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
            "outcome IN ('matched', 'created', 'needs_review')",
            name="ck_instructor_resolutions_outcome",
        ),
    )
    op.create_index(
        "ix_instructor_resolutions_course_id",
        "instructor_resolutions",
        ["course_id"],
    )

    op.add_column(
        "courses",
        sa.Column(
            "instructor_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "instructors.id",
                ondelete="SET NULL",
                name="fk_courses_instructor_id",
            ),
            nullable=True,
        ),
    )
    op.create_index("ix_courses_instructor_id", "courses", ["instructor_id"])


def downgrade() -> None:
    op.drop_index("ix_courses_instructor_id", table_name="courses")
    op.drop_column("courses", "instructor_id")
    op.drop_index(
        "ix_instructor_resolutions_course_id", table_name="instructor_resolutions"
    )
    op.drop_table("instructor_resolutions")
    op.drop_table("instructors")
