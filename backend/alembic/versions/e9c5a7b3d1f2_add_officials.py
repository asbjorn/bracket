"""add officials (referees and match hosts), their matches and the hosts of the courts

Revision ID: e9c5a7b3d1f2
Revises: d7a3b9e5f1c8
Create Date: 2026-11-12 14:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "e9c5a7b3d1f2"
down_revision: str | None = "d7a3b9e5f1c8"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "officials",
        sa.Column("id", sa.BigInteger(), primary_key=True, index=True),
        sa.Column(
            "tournament_id",
            sa.BigInteger(),
            sa.ForeignKey("tournaments.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("level", sa.Text(), nullable=True),
        sa.Column("club_name", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("role", sa.Text(), server_default="REFEREE", nullable=False),
        sa.Column("fee_per_match", sa.Integer(), server_default="0", nullable=False),
        sa.Column("fee_per_day", sa.Integer(), server_default="0", nullable=False),
        sa.Column("active", sa.Boolean(), server_default="t", nullable=False),
        sa.Column(
            "created", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "match_officials",
        sa.Column("id", sa.BigInteger(), primary_key=True, index=True),
        sa.Column(
            "match_id",
            sa.BigInteger(),
            sa.ForeignKey("matches.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
        sa.Column(
            "official_id",
            sa.BigInteger(),
            sa.ForeignKey("officials.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
        sa.Column("role", sa.Text(), server_default="REFEREE", nullable=False),
        sa.UniqueConstraint("match_id", "official_id"),
    )
    op.create_index(
        "ix_match_officials_one_referee",
        "match_officials",
        ["match_id"],
        unique=True,
        postgresql_where=sa.text("role = 'REFEREE'"),
    )
    op.create_table(
        "court_hosts",
        sa.Column("id", sa.BigInteger(), primary_key=True, index=True),
        sa.Column(
            "tournament_id",
            sa.BigInteger(),
            sa.ForeignKey("tournaments.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
        sa.Column(
            "court_id",
            sa.BigInteger(),
            sa.ForeignKey("courts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "official_id",
            sa.BigInteger(),
            sa.ForeignKey("officials.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("court_hosts")
    op.drop_index("ix_match_officials_one_referee", table_name="match_officials")
    op.drop_table("match_officials")
    op.drop_table("officials")
