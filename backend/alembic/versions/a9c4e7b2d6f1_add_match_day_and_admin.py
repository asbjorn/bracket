"""match day and administration: class kind, squad size, team conflicts, club no-overlap,
jury members, fair play points, lots, prize ceremony offset

Revision ID: a9c4e7b2d6f1
Revises: f7b3d1a9c5e2
Create Date: 2026-11-12 10:00:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "a9c4e7b2d6f1"
down_revision: str | None = "f7b3d1a9c5e2"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "tournaments",
        sa.Column("ceremony_offset_minutes", sa.Integer(), server_default="15", nullable=False),
    )
    op.add_column("categories", sa.Column("kind", sa.Text(), nullable=True))
    op.add_column("categories", sa.Column("kind_note", sa.Text(), nullable=True))
    op.add_column("stage_item_inputs", sa.Column("lot_number", sa.Integer(), nullable=True))
    op.add_column(
        "participating_clubs",
        sa.Column("no_overlap", sa.Boolean(), server_default="f", nullable=False),
    )
    op.add_column(
        "rankings",
        sa.Column("fair_play_yellow_points", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "rankings",
        sa.Column("fair_play_red_points", sa.Integer(), server_default="3", nullable=False),
    )
    op.add_column("teams", sa.Column("squad_size", sa.Integer(), nullable=True))
    op.add_column(
        "jury_decisions",
        sa.Column(
            "member_ids", postgresql.ARRAY(sa.BigInteger()), server_default="{}", nullable=False
        ),
    )
    op.create_table(
        "team_conflicts",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("tournament_id", sa.BigInteger(), nullable=False),
        sa.Column("team1_id", sa.BigInteger(), nullable=False),
        sa.Column("team2_id", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("team1_id < team2_id", name="team_conflicts_ordered"),
        sa.ForeignKeyConstraint(["tournament_id"], ["tournaments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team1_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team2_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team1_id", "team2_id"),
    )
    op.create_index("ix_team_conflicts_id", "team_conflicts", ["id"])
    op.create_index("ix_team_conflicts_tournament_id", "team_conflicts", ["tournament_id"])
    op.create_table(
        "jury_members",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("tournament_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("club_name", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("role", sa.Text(), server_default="MEMBER", nullable=False),
        sa.Column(
            "created", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tournament_id"], ["tournaments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jury_members_id", "jury_members", ["id"])
    op.create_index("ix_jury_members_tournament_id", "jury_members", ["tournament_id"])


def downgrade() -> None:
    op.drop_table("jury_members")
    op.drop_table("team_conflicts")
    op.drop_column("jury_decisions", "member_ids")
    op.drop_column("teams", "squad_size")
    op.drop_column("rankings", "fair_play_red_points")
    op.drop_column("rankings", "fair_play_yellow_points")
    op.drop_column("participating_clubs", "no_overlap")
    op.drop_column("stage_item_inputs", "lot_number")
    op.drop_column("categories", "kind_note")
    op.drop_column("categories", "kind")
    op.drop_column("tournaments", "ceremony_offset_minutes")
