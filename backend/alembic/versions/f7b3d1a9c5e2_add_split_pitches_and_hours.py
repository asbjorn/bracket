"""split pitches, opening hours per pitch and per class, max matches per day, match started

Revision ID: f7b3d1a9c5e2
Revises: e2a7c5d9f3b1
Create Date: 2026-11-12 10:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "f7b3d1a9c5e2"
down_revision: str | None = "e2a7c5d9f3b1"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # A part of a split pitch belongs to the full pitch
    op.add_column("courts", sa.Column("parent_court_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "courts_parent_court_id_fkey",
        "courts",
        "courts",
        ["parent_court_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_courts_parent_court_id", "courts", ["parent_court_id"])

    # Time windows of the cup (both NULL), of one pitch, or of one class
    for column, table in (("court_id", "courts"), ("category_id", "categories")):
        op.add_column("time_windows", sa.Column(column, sa.BigInteger(), nullable=True))
        op.create_foreign_key(
            f"time_windows_{column}_fkey",
            "time_windows",
            table,
            [column],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index(f"ix_time_windows_{column}", "time_windows", [column])
    op.create_check_constraint(
        "time_windows_court_or_category_check",
        "time_windows",
        "court_id IS NULL OR category_id IS NULL",
    )

    op.add_column("categories", sa.Column("max_matches_per_day", sa.Integer(), nullable=True))
    op.add_column("matches", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("matches", "started_at")
    op.drop_column("categories", "max_matches_per_day")
    op.drop_constraint("time_windows_court_or_category_check", "time_windows")
    # Windows of pitches and classes can't exist without the columns
    op.execute("DELETE FROM time_windows WHERE court_id IS NOT NULL OR category_id IS NOT NULL")
    for column in ("category_id", "court_id"):
        op.drop_index(f"ix_time_windows_{column}", "time_windows")
        op.drop_constraint(f"time_windows_{column}_fkey", "time_windows")
        op.drop_column("time_windows", column)
    op.drop_index("ix_courts_parent_court_id", "courts")
    op.drop_constraint("courts_parent_court_id_fkey", "courts")
    op.drop_column("courts", "parent_court_id")
