"""stage item inputs: a check that every row is one kind of input

Revision ID: d6e1f4a8b2c7
Revises: c5d9e3f7a1b6
Create Date: 2026-11-12 10:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "d6e1f4a8b2c7"
down_revision: str | None = "c5d9e3f7a1b6"
branch_labels: str | None = None
depends_on: str | None = None

CHECK = (
    "(best_from_stage_id IS NULL AND best_rank IS NULL"
    " AND (winner_from_stage_item_id IS NULL) = (winner_position IS NULL))"
    " OR (best_from_stage_id IS NOT NULL AND best_rank IS NOT NULL"
    " AND winner_position IS NOT NULL AND winner_from_stage_item_id IS NULL)"
)


def upgrade() -> None:
    # Repair rows left behind by editing a "best placed" slot by hand (they broke every page
    # of the tournament): the hand edit wins, the incomplete best-of fields go
    op.execute(
        """
        UPDATE stage_item_inputs
        SET best_from_stage_id = NULL, best_rank = NULL,
            winner_position = CASE
                WHEN winner_from_stage_item_id IS NULL THEN NULL ELSE winner_position END
        WHERE best_from_stage_id IS NOT NULL
        AND (best_rank IS NULL OR winner_position IS NULL OR winner_from_stage_item_id IS NOT NULL)
        """
    )
    op.execute(
        """
        UPDATE stage_item_inputs SET winner_position = NULL
        WHERE best_from_stage_id IS NULL AND winner_from_stage_item_id IS NULL
        AND winner_position IS NOT NULL
        """
    )
    op.create_check_constraint("stage_item_inputs_kind_check", "stage_item_inputs", CHECK)


def downgrade() -> None:
    op.drop_constraint("stage_item_inputs_kind_check", "stage_item_inputs", type_="check")
