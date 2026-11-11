"""
The end of the cup: final placings per class, the prize ceremony and the medals.

Placings come from the last stage of a class: a knockout playoff gives 1st and 2nd from the
final and 3rd (and 4th) from the bronze final, or two shared 3rd places from the semifinals;
a group gives its table. Classes with hidden results (children's football) get no placings:
every player gets a medal.
"""

from collections.abc import Sequence
from datetime import timedelta
from typing import Any

from heliclockter import datetime_utc
from pydantic import BaseModel

from bracket.logic.ranking.calculation import determine_team_ranking_for_stage_item
from bracket.models.db.category import Category
from bracket.models.db.discipline import MatchCard
from bracket.models.db.match import Match
from bracket.models.db.ranking import Ranking
from bracket.models.db.stage_item import StageType
from bracket.models.db.team import FullTeamWithPlayers
from bracket.models.db.util import StageItemWithRounds, StageWithStageItems
from bracket.utils.id_types import CategoryId, StageItemId, TeamId

PODIUM_PLACES = 3


class Placing(BaseModel):
    place: int
    team_id: TeamId
    team_name: str


class Podium(BaseModel):
    """The placings of one playoff or group, e.g. "A-sluttspill" or "Pulje A"."""

    stage_item_id: StageItemId
    title: str
    knockout: bool
    # Done when all matches of the playoff or group are played
    complete: bool
    placings: list[Placing]


class MedalTeam(BaseModel):
    team_id: TeamId
    team_name: str
    squad_size: int | None


class ClassFinalResults(BaseModel):
    category_id: CategoryId
    name: str
    results_public: bool
    complete: bool
    last_match_end: datetime_utc | None
    ceremony_time: datetime_utc | None
    podiums: list[Podium]
    teams: list[MedalTeam]
    # Medals for the players of all teams whose squad size is known
    medal_count: int
    teams_without_squad_size: int


def team_of(input_: Any) -> tuple[TeamId, str] | None:
    team = getattr(input_, "team", None)
    return (team.id, team.name) if team is not None else None


def knockout_placings(stage_item: StageItemWithRounds) -> tuple[list[Placing], bool]:
    """1st/2nd from the final; 3rd/4th from the bronze final or shared 3rd from the semis."""
    rounds = sorted(stage_item.rounds, key=lambda r: r.id)
    if not rounds:
        return [], False
    last: Sequence[Match] = rounds[-1].matches
    final = next(
        (
            m
            for m in last
            if m.stage_item_input1_loser_from_match_id is None
            and m.stage_item_input2_loser_from_match_id is None
        ),
        None,
    )
    bronze = next((m for m in last if m is not final), None)
    placings: list[Placing] = []

    def add(place: int, input_: Any) -> None:
        team = team_of(input_)
        if team is not None:
            placings.append(Placing(place=place, team_id=team[0], team_name=team[1]))

    complete = final is not None and final.get_winner() is not None
    if final is not None and final.get_winner() is not None:
        add(1, final.get_winner())
        add(2, final.get_loser())
    if bronze is not None:
        complete = complete and bronze.get_winner() is not None
        if bronze.get_winner() is not None:
            add(3, bronze.get_winner())
            add(4, bronze.get_loser())
    elif len(rounds) > 1:
        # No bronze final: both semifinal losers share third place
        for semifinal in rounds[-2].matches:
            add(3, semifinal.get_loser())
    return placings, complete


def group_placings(
    stage_item: StageItemWithRounds, ranking: Ranking, cards: Sequence[MatchCard]
) -> tuple[list[Placing], bool]:
    inputs = {input_.id: input_ for input_ in stage_item.inputs}
    placings = []
    for input_id, stats in determine_team_ranking_for_stage_item(stage_item, ranking, cards):
        team = team_of(inputs[input_id])
        if team is not None and stats.position is not None:
            placings.append(Placing(place=stats.position, team_id=team[0], team_name=team[1]))
    matches = [m for r in stage_item.rounds for m in r.matches]
    return placings, all(m.played for m in matches)


def class_final_results(
    category: Category,
    stages: list[StageWithStageItems],
    teams: list[FullTeamWithPlayers],
    rankings: dict[StageItemId, Ranking],
    cards: Sequence[MatchCard],
    ceremony_offset_minutes: int,
) -> ClassFinalResults:
    class_stages = sorted((s for s in stages if s.category_id == category.id), key=lambda s: s.id)
    matches = [
        m for s in class_stages for item in s.stage_items for r in item.rounds for m in r.matches
    ]
    ends = [m.end_time for m in matches if m.start_time is not None]
    last_end = max(ends, default=None)

    podiums: list[Podium] = []
    if category.results_public and class_stages:
        for item in sorted(class_stages[-1].stage_items, key=lambda i: i.name):
            knockout = item.type is StageType.SINGLE_ELIMINATION
            placings, complete = (
                knockout_placings(item)
                if knockout
                else group_placings(item, rankings[item.id], cards)
            )
            podiums.append(
                Podium(
                    stage_item_id=item.id,
                    title=item.name,
                    knockout=knockout,
                    complete=complete,
                    placings=placings,
                )
            )

    class_teams = sorted(
        (t for t in teams if t.category_id == category.id), key=lambda t: t.name.casefold()
    )
    return ClassFinalResults(
        category_id=category.id,
        name=category.name,
        results_public=category.results_public,
        complete=len(matches) > 0 and all(m.played for m in matches),
        last_match_end=last_end,
        ceremony_time=(
            last_end + timedelta(minutes=ceremony_offset_minutes) if last_end is not None else None
        ),
        podiums=podiums,
        teams=[
            MedalTeam(team_id=t.id, team_name=t.name, squad_size=t.squad_size) for t in class_teams
        ],
        medal_count=sum(t.squad_size or 0 for t in class_teams),
        teams_without_squad_size=sum(1 for t in class_teams if t.squad_size is None),
    )
