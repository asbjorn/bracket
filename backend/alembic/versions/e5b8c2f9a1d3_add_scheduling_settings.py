"""add scheduling settings: time windows, class timing and formats, court formats

Revision ID: e5b8c2f9a1d3
Revises: d9a2b6c1e4f7
Create Date: 2026-11-11 18:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "e5b8c2f9a1d3"
down_revision: str | None = "d9a2b6c1e4f7"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "tournaments",
        sa.Column("min_rest_minutes", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "tournaments",
        sa.Column("stage_buffer_minutes", sa.Integer(), server_default="10", nullable=False),
    )
    for column in ("duration_minutes", "margin_minutes", "min_rest_minutes"):
        op.add_column("categories", sa.Column(column, sa.Integer(), nullable=True))
    op.add_column("categories", sa.Column("game_format", sa.Text(), nullable=True))
    op.add_column("courts", sa.Column("game_format", sa.Text(), nullable=True))

    op.create_table(
        "time_windows",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("tournament_id", sa.BigInteger(), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tournament_id"], ["tournaments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_time_windows_id"), "time_windows", ["id"], unique=False)
    op.create_index(
        op.f("ix_time_windows_tournament_id"), "time_windows", ["tournament_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_time_windows_tournament_id"), table_name="time_windows")
    op.drop_index(op.f("ix_time_windows_id"), table_name="time_windows")
    op.drop_table("time_windows")
    op.drop_column("courts", "game_format")
    op.drop_column("categories", "game_format")
    for column in ("min_rest_minutes", "margin_minutes", "duration_minutes"):
        op.drop_column("categories", column)
    op.drop_column("tournaments", "stage_buffer_minutes")
    op.drop_column("tournaments", "min_rest_minutes")
