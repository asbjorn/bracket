"""add participating clubs: teams belong to a club (instead of a free-text club name)

Revision ID: c5d9e3f7a1b6
Revises: b4c8d2e6f0a7
Create Date: 2026-11-12 10:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "c5d9e3f7a1b6"
down_revision: str | None = "b4c8d2e6f0a7"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "participating_clubs",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("tournament_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tournament_id"], ["tournaments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_participating_clubs_id", "participating_clubs", ["id"])
    op.create_index(
        "ix_participating_clubs_tournament_id", "participating_clubs", ["tournament_id"]
    )
    op.create_index(
        "ix_participating_clubs_tournament_id_lower_name",
        "participating_clubs",
        ["tournament_id", sa.text("lower(name)")],
        unique=True,
    )
    op.add_column("teams", sa.Column("club_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "teams_club_id_fkey",
        "teams",
        "participating_clubs",
        ["club_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_teams_club_id", "teams", ["club_id"])

    # One club per distinct club name in a tournament (ignoring case and spaces around it);
    # the first spelling that was used becomes the club's name
    op.execute(
        """
        INSERT INTO participating_clubs (tournament_id, name)
        SELECT DISTINCT ON (tournament_id, lower(trim(club_name)))
            tournament_id, trim(club_name)
        FROM teams
        WHERE club_name IS NOT NULL AND trim(club_name) != ''
        ORDER BY tournament_id, lower(trim(club_name)), id
        """
    )
    op.execute(
        """
        UPDATE teams SET club_id = pc.id
        FROM participating_clubs pc
        WHERE pc.tournament_id = teams.tournament_id
        AND lower(pc.name) = lower(trim(teams.club_name))
        """
    )
    op.drop_column("teams", "club_name")


def downgrade() -> None:
    op.add_column("teams", sa.Column("club_name", sa.String(), nullable=True))
    op.execute(
        """
        UPDATE teams SET club_name = pc.name
        FROM participating_clubs pc WHERE pc.id = teams.club_id
        """
    )
    op.drop_index("ix_teams_club_id", table_name="teams")
    op.drop_constraint("teams_club_id_fkey", "teams", type_="foreignkey")
    op.drop_column("teams", "club_id")
    op.drop_index("ix_participating_clubs_tournament_id_lower_name", "participating_clubs")
    op.drop_index("ix_participating_clubs_tournament_id", "participating_clubs")
    op.drop_index("ix_participating_clubs_id", "participating_clubs")
    op.drop_table("participating_clubs")
