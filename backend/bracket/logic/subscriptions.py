from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import HTTPException
from heliclockter import datetime_utc
from pydantic import BaseModel

from bracket.config import config
from bracket.models.db.account import UserAccountType
from bracket.models.db.club import ClubCreateBody
from bracket.models.db.ranking import RankingCreateBody
from bracket.models.db.tournament import TournamentBody
from bracket.sql.clubs import create_club
from bracket.sql.rankings import sql_create_ranking
from bracket.sql.tournaments import sql_create_tournament
from bracket.utils.id_types import UserId

if TYPE_CHECKING:
    from bracket.models.db.user import UserBase


class Subscription(BaseModel):
    max_teams: int
    max_players: int
    max_clubs: int
    max_tournaments: int
    max_courts: int
    max_stages: int
    max_stage_items: int
    max_rounds: int
    max_rankings: int
    max_categories: int


demo_subscription = Subscription(
    max_teams=8,
    max_players=16,
    max_clubs=1,
    max_tournaments=2,
    max_courts=4,
    max_stages=4,
    max_stage_items=6,
    max_rounds=6,
    max_rankings=2,
    max_categories=4,
)


regular_subscription = Subscription(
    max_teams=config.limit_max_teams,
    max_players=config.limit_max_players,
    max_clubs=config.limit_max_clubs,
    max_tournaments=config.limit_max_tournaments,
    max_courts=config.limit_max_courts,
    max_stages=config.limit_max_stages,
    max_stage_items=config.limit_max_stage_items,
    max_rounds=config.limit_max_rounds,
    max_rankings=config.limit_max_rankings,
    max_categories=config.limit_max_categories,
)

subscription_lookup = {
    UserAccountType.DEMO: demo_subscription,
    UserAccountType.REGULAR: regular_subscription,
}


def check_requirement(array: list[Any], user: UserBase, attribute: str, additions: int = 1) -> None:
    subscription = subscription_lookup[user.account_type]
    constraint: int = getattr(subscription, attribute)
    if len(array) + additions > constraint:
        raise HTTPException(
            400,
            f"Your `{user.account_type.value}` subscription allows a maximum of "
            f"{constraint} {attribute.replace('max_', '')}.",
        )


async def setup_demo_account(user_id: UserId) -> None:
    club = ClubCreateBody(name="Demo Club")
    club_inserted = await create_club(club, user_id)

    tournament = TournamentBody(
        name="Demo Tournament",
        club_id=club_inserted.id,
        start_time=datetime_utc.future(hours=1),
        dashboard_public=False,
        players_can_be_in_multiple_teams=False,
        auto_assign_courts=True,
        duration_minutes=10,
        margin_minutes=5,
    )
    tournament_id = await sql_create_tournament(tournament)

    ranking = RankingCreateBody()
    await sql_create_ranking(tournament_id=tournament_id, ranking_body=ranking, position=0)
