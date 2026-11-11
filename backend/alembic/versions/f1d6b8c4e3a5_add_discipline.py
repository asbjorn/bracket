"""add discipline: cards per match, suspension settings and the jury's decisions

Revision ID: f1d6b8c4e3a5
Revises: e9c5a7b3d1f2
Create Date: 2026-11-12 16:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "f1d6b8c4e3a5"
down_revision: str | None = "e9c5a7b3d1f2"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "tournaments",
        sa.Column("suspension_matches_per_red", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "tournaments", sa.Column("yellow_cards_for_suspension", sa.Integer(), nullable=True)
    )
    op.create_table(
        "match_cards",
        sa.Column("id", sa.BigInteger(), primary_key=True, index=True),
        sa.Column(
            "tournament_id",
            sa.BigInteger(),
            sa.ForeignKey("tournaments.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
        sa.Column(
            "match_id",
            sa.BigInteger(),
            sa.ForeignKey("matches.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
        sa.Column(
            "team_id",
            sa.BigInteger(),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("player_name", sa.Text(), nullable=False),
        sa.Column(
            "player_id",
            sa.BigInteger(),
            sa.ForeignKey("players.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("card_type", sa.Text(), nullable=False),
        sa.Column("minute", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "jury_decisions",
        sa.Column("id", sa.BigInteger(), primary_key=True, index=True),
        sa.Column(
            "tournament_id",
            sa.BigInteger(),
            sa.ForeignKey("tournaments.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
        sa.Column(
            "match_id",
            sa.BigInteger(),
            sa.ForeignKey("matches.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "team_id",
            sa.BigInteger(),
            sa.ForeignKey("teams.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "card_id",
            sa.BigInteger(),
            sa.ForeignKey("match_cards.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("suspension_change", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "decided_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "decided_by",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("jury_decisions")
    op.drop_table("match_cards")
    op.drop_column("tournaments", "yellow_cards_for_suspension")
    op.drop_column("tournaments", "suspension_matches_per_red")
