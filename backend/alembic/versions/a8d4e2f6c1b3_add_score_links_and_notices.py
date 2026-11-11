"""add score links (result entry without an account) and match day notices

Revision ID: a8d4e2f6c1b3
Revises: f3c7a1e9d2b4
Create Date: 2026-11-11 22:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "a8d4e2f6c1b3"
down_revision: str | None = "f3c7a1e9d2b4"
branch_labels: str | None = None
depends_on: str | None = None


def tournament_id_column() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(
        "tournament_id",
        sa.BigInteger(),
        sa.ForeignKey("tournaments.id", ondelete="CASCADE"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "score_links",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        tournament_id_column(),
        sa.Column(
            "court_id",
            sa.BigInteger(),
            sa.ForeignKey("courts.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column(
            "created", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_score_links_id", "score_links", ["id"])
    op.create_index("ix_score_links_tournament_id", "score_links", ["tournament_id"])

    op.create_table(
        "match_day_notices",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        tournament_id_column(),
        sa.Column(
            "court_id",
            sa.BigInteger(),
            sa.ForeignKey("courts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "score_link_id",
            sa.BigInteger(),
            sa.ForeignKey("score_links.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("delay_minutes", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "created", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("resolved", sa.Boolean(), server_default="f", nullable=False),
    )
    op.create_index("ix_match_day_notices_id", "match_day_notices", ["id"])
    op.create_index("ix_match_day_notices_tournament_id", "match_day_notices", ["tournament_id"])


def downgrade() -> None:
    op.drop_table("match_day_notices")
    op.drop_table("score_links")
