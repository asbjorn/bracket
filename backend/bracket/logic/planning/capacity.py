"""
Capacity calculator: does a planned cup fit the courts and playing hours?

Works before any team is registered. The classes are described by numbers (teams, group size,
playoffs, timing); the matches that would result are planned with the real scheduler, so rest,
game formats and the order of stages are taken into account.
"""

from collections import Counter
from datetime import date
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, Field, model_validator

from bracket.logic.planning.propose import ScheduleProposal, to_proposal
from bracket.logic.planning.scheduler import (
    CourtToPlan,
    Dependency,
    MatchToPlan,
    ScheduleResult,
    Window,
    schedule_matches,
)
from bracket.logic.scheduling.cup_structure import (
    MAX_TEAMS_PER_PLAYOFF,
    PLAYOFF_NAMES,
    PlayoffPreset,
    split_into_groups,
    split_placings,
)
from bracket.logic.scheduling.elimination import (
    MIN_TEAMS_THIRD_PLACE_MATCH,
    FromMatch,
    plan_single_elimination,
)
from bracket.logic.scheduling.round_robin import get_round_robin_combinations
from bracket.models.db.category import (
    MAX_MATCHES_PER_DAY_LIMIT,
    YOUTH_FOOTBALL_MIN_AGE,
    max_matches_per_day_for_age,
)
from bracket.models.db.game_format import GameFormat
from bracket.models.db.time_window import MAX_TIME_WINDOWS, TimeWindowBody
from bracket.utils.cup_time import cup_day
from bracket.utils.id_types import CourtId, MatchId
from bracket.utils.text import SingleLine

MAX_TEAMS_TOTAL = 600
MAX_COURTS = 100
MIN_MATCHES_PER_TEAM = 3
MIN_MATCHES_MAX_AGE = 13
# Many teams aged 10-13 manage 4-5 matches a day before concentration drops (AreaCopa)
MAX_MATCHES_PER_DAY_AGES = (10, 13)
MAX_MATCHES_PER_DAY = 5


class CapacityClass(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=50), SingleLine]
    age: int | None = Field(default=None, ge=4, le=99)
    team_count: int = Field(ge=2, le=128)
    group_size: int = Field(ge=2, le=10)
    playoffs: PlayoffPreset = PlayoffPreset.NONE
    # Instead of a preset: which placings go to which playoff, e.g. [[1, 2]] for only the top 2
    playoff_placings: list[list[int]] | None = None
    third_place_match: bool = False

    def get_playoffs(self, group_sizes: list[int]) -> list[list[int]]:
        """The placings of every playoff that has at least two teams."""
        smallest_group = min(group_sizes)
        if self.playoff_placings is not None:
            all_placings = [
                [placing for placing in placings if placing <= smallest_group]
                for placings in self.playoff_placings
            ]
        else:
            all_placings = split_placings(smallest_group, self.playoffs.playoff_count)
        return [placings for placings in all_placings if len(group_sizes) * len(placings) >= 2]

    @model_validator(mode="after")
    def check_playoffs(self) -> Self:
        if self.group_size > self.team_count:
            raise ValueError(
                f"{self.name}: a group can't have more teams ({self.group_size}) "
                f"than the class ({self.team_count})"
            )
        if self.playoff_placings is not None:
            placings = [placing for playoff in self.playoff_placings for placing in playoff]
            if len(self.playoff_placings) > len(PLAYOFF_NAMES):
                raise ValueError(f"{self.name}: at most {len(PLAYOFF_NAMES)} playoffs")
            if len(placings) != len(set(placings)) or not all(1 <= p <= 10 for p in placings):
                raise ValueError(f"{self.name}: each placing (1-10) can only go to one playoff")
        group_sizes = split_into_groups(self.team_count, self.group_size)
        if any(
            len(group_sizes) * len(placings) > MAX_TEAMS_PER_PLAYOFF
            for placings in self.get_playoffs(group_sizes)
        ):
            raise ValueError(
                f"{self.name}: a playoff can have at most {MAX_TEAMS_PER_PLAYOFF} teams, "
                "split it into more playoffs"
            )
        return self

    @property
    def has_playoffs(self) -> bool:
        if self.playoff_placings is not None:
            return any(self.playoff_placings)
        return self.playoffs != PlayoffPreset.NONE

    duration_minutes: int = Field(ge=1, le=240)
    margin_minutes: int = Field(default=0, ge=0, le=120)
    min_rest_minutes: int = Field(default=0, ge=0, le=600)
    game_format: GameFormat | None = None
    # At most this many matches per team per day; `None`: the default for the age
    max_matches_per_day: int | None = Field(default=None, ge=1, le=MAX_MATCHES_PER_DAY_LIMIT)
    # The days/hours the class plays; empty: whenever the cup plays
    time_windows: list[TimeWindowBody] = Field(default=[], max_length=MAX_TIME_WINDOWS)

    def get_max_matches_per_day(self) -> int | None:
        if self.max_matches_per_day is not None:
            return self.max_matches_per_day
        return max_matches_per_day_for_age(self.age)

    def get_windows(self) -> tuple[Window, ...] | None:
        if len(self.time_windows) < 1:
            return None
        return tuple(Window(w.start_time, w.end_time) for w in self.time_windows)


class CapacityCourts(BaseModel):
    """`count` pitches; with `split_into`, each is a full pitch split into parts."""

    count: int = Field(ge=1, le=MAX_COURTS)
    game_format: GameFormat | None = None
    split_into: int | None = Field(default=None, ge=2, le=4)
    part_format: GameFormat | None = None


class CapacityBody(BaseModel):
    classes: list[CapacityClass] = Field(min_length=1, max_length=40)
    courts: list[CapacityCourts] = Field(min_length=1, max_length=10)
    time_windows: list[TimeWindowBody] = Field(min_length=1, max_length=60)
    stage_buffer_minutes: int = Field(default=10, ge=0, le=600)

    @model_validator(mode="after")
    def check_size(self) -> Self:
        if sum(c.team_count for c in self.classes) > MAX_TEAMS_TOTAL:
            raise ValueError(f"The calculator handles at most {MAX_TEAMS_TOTAL} teams")
        if sum(c.count * (1 + (c.split_into or 0)) for c in self.courts) > MAX_COURTS:
            raise ValueError(f"The calculator handles at most {MAX_COURTS} courts")
        return self


class CapacityWarning(StrEnum):
    TOO_FEW_MATCHES = "TOO_FEW_MATCHES"
    TOO_MANY_MATCHES_PER_DAY = "TOO_MANY_MATCHES_PER_DAY"
    PLAYOFFS_IN_CHILDRENS_FOOTBALL = "PLAYOFFS_IN_CHILDRENS_FOOTBALL"


class CapacityClassResult(BaseModel):
    name: str
    group_sizes: list[int]
    group_matches: int
    playoff_team_counts: list[int]
    playoff_matches: int
    min_matches_per_team: int
    max_matches_per_team: int
    # The most group matches a team plays on one day in the calculated plan
    max_matches_per_team_per_day: int
    warnings: list[CapacityWarning]


class MatchesOnDay(BaseModel):
    day: date
    matches: int


class CapacityResult(BaseModel):
    classes: list[CapacityClassResult]
    schedule: ScheduleProposal
    # How the planned matches are spread over the days (in Norwegian time)
    matches_per_day: list[MatchesOnDay]


class MatchFactory:
    """Creates the planned matches of one class, with ids unique over all classes."""

    def __init__(self, cup_class: CapacityClass, next_id: list[int]) -> None:
        self.cup_class = cup_class
        self.next_id = next_id

    def create(
        self, teams: frozenset[str], dependencies: tuple[Dependency, ...], priority: tuple[int, ...]
    ) -> MatchToPlan:
        self.next_id[0] += 1
        return MatchToPlan(
            id=MatchId(self.next_id[0]),
            duration_minutes=self.cup_class.duration_minutes,
            margin_minutes=self.cup_class.margin_minutes,
            teams=teams,
            rest_minutes=self.cup_class.min_rest_minutes,
            game_format=self.cup_class.game_format,
            dependencies=dependencies,
            priority=priority,
            windows=self.cup_class.get_windows(),
            max_per_day=self.cup_class.get_max_matches_per_day(),
        )


def group_matches(
    factory: MatchFactory, group_sizes: list[int], class_index: int
) -> list[MatchToPlan]:
    """Round robin matches; teams are named per class, group and slot, e.g. "0:2:1"."""
    matches: list[MatchToPlan] = []
    for group_index, size in enumerate(group_sizes):
        for round_index, round_ in enumerate(get_round_robin_combinations(size)):
            for team1, team2 in round_:
                if team1 < size and team2 < size:
                    teams = frozenset(
                        {
                            f"{class_index}:{group_index}:{team1}",
                            f"{class_index}:{group_index}:{team2}",
                        }
                    )
                    matches.append(
                        factory.create(teams, (), (0, round_index, class_index, group_index))
                    )
    return matches


def playoff_matches(
    factory: MatchFactory,
    team_count: int,
    group_match_ids: list[MatchId],
    stage_buffer_minutes: int,
    position: tuple[int, int],
) -> list[MatchToPlan]:
    """
    A knockout playoff: the first matches wait for the whole group stage plus the buffer,
    later rounds for the matches they get their teams from. `position` is (class, playoff).
    """
    cup_class = factory.cup_class
    third_place = cup_class.third_place_match and team_count >= MIN_TEAMS_THIRD_PLACE_MATCH
    class_index, playoff_index = position
    matches: list[MatchToPlan] = []
    planned_ids: list[list[MatchId]] = []
    for round_index, planned_round in enumerate(
        plan_single_elimination(team_count, third_place_match=third_place)
    ):
        planned_ids.append([])
        for match_index, sources in enumerate(planned_round):
            dependencies: list[Dependency] = []
            for source in sources:
                if isinstance(source, FromMatch):
                    feeder = planned_ids[source.round_index][source.match_index]
                    dependencies.append(Dependency(feeder, cup_class.min_rest_minutes))
                else:
                    delay = max(stage_buffer_minutes, cup_class.min_rest_minutes)
                    dependencies += [Dependency(g, delay) for g in group_match_ids]
            match = factory.create(
                frozenset({f"{class_index}:p{playoff_index}:{round_index}:{match_index}"}),
                tuple(dict.fromkeys(dependencies)),
                (1, round_index, class_index, playoff_index),
            )
            matches.append(match)
            planned_ids[-1].append(match.id)
    return matches


def class_warnings(
    cup_class: CapacityClass, min_matches: int, max_per_day: int
) -> list[CapacityWarning]:
    """`max_per_day`: the most matches a team plays on one day in the calculated plan."""
    if cup_class.age is None:
        return []
    warnings: list[CapacityWarning] = []
    if cup_class.age <= MIN_MATCHES_MAX_AGE and min_matches < MIN_MATCHES_PER_TEAM:
        warnings.append(CapacityWarning.TOO_FEW_MATCHES)
    if cup_class.age < YOUTH_FOOTBALL_MIN_AGE and cup_class.has_playoffs:
        warnings.append(CapacityWarning.PLAYOFFS_IN_CHILDRENS_FOOTBALL)
    low, high = MAX_MATCHES_PER_DAY_AGES
    if low <= cup_class.age <= high and max_per_day > MAX_MATCHES_PER_DAY:
        warnings.append(CapacityWarning.TOO_MANY_MATCHES_PER_DAY)
    return warnings


def max_matches_per_team_per_day(
    class_index: int, matches: list[MatchToPlan], result: ScheduleResult
) -> int:
    """Group matches only: the teams of the playoffs aren't known before the cup."""
    counts: Counter[tuple[str, date]] = Counter()
    for match in matches:
        assignment = result.assignments.get(match.id)
        if assignment is None:
            continue
        for team in match.teams:
            if team.startswith(f"{class_index}:") and ":p" not in team:
                counts[(team, cup_day(assignment.start))] += 1
    return max(counts.values(), default=0)


def class_matches(
    cup_class: CapacityClass, class_index: int, stage_buffer_minutes: int, next_id: list[int]
) -> tuple[list[MatchToPlan], CapacityClassResult]:
    """The matches of one class: round robin groups, then the playoffs."""
    factory = MatchFactory(cup_class, next_id)
    group_sizes = split_into_groups(cup_class.team_count, cup_class.group_size)
    matches = group_matches(factory, group_sizes, class_index)
    group_match_ids = [match.id for match in matches]

    playoff_placings = cup_class.get_playoffs(group_sizes)
    playoff_team_counts = [len(group_sizes) * len(placings) for placings in playoff_placings]
    playoffs = [
        playoff_matches(
            factory, count, group_match_ids, stage_buffer_minutes, (class_index, playoff_index)
        )
        for playoff_index, count in enumerate(playoff_team_counts)
    ]
    for playoff in playoffs:
        matches += playoff

    # The bronze final is played in the final round, so it adds no round
    playoff_rounds = [len(plan_single_elimination(count)) for count in playoff_team_counts]
    placings_in_playoffs = {placing for placings in playoff_placings for placing in placings}
    all_placings_play_off = placings_in_playoffs >= set(range(1, min(group_sizes) + 1))
    # Every team plays its group; with playoffs for all placings, at least one more match
    min_matches = min(group_sizes) - 1 + (1 if all_placings_play_off else 0)
    max_matches = max(group_sizes) - 1 + max(playoff_rounds, default=0)

    return matches, CapacityClassResult(
        name=cup_class.name,
        group_sizes=group_sizes,
        group_matches=len(group_match_ids),
        playoff_team_counts=playoff_team_counts,
        playoff_matches=sum(len(playoff) for playoff in playoffs),
        min_matches_per_team=min_matches,
        max_matches_per_team=max_matches,
        # Known once the matches are planned (see calculate_capacity)
        max_matches_per_team_per_day=0,
        warnings=[],
    )


def calculate_capacity(body: CapacityBody) -> CapacityResult:
    next_id = [0]
    matches: list[MatchToPlan] = []
    plans: list[tuple[CapacityClass, list[MatchToPlan], CapacityClassResult]] = []
    for class_index, cup_class in enumerate(body.classes):
        class_plan, class_result = class_matches(
            cup_class, class_index, body.stage_buffer_minutes, next_id
        )
        matches += class_plan
        plans.append((cup_class, class_plan, class_result))

    courts = capacity_courts(body.courts)
    windows = [Window(w.start_time, w.end_time) for w in body.time_windows]
    result = schedule_matches(matches, courts, windows)
    proposal = to_proposal(matches, courts, windows, result, uses_default_window=False)
    class_results = []
    for class_index, (cup_class, class_plan, class_result) in enumerate(plans):
        per_day = max_matches_per_team_per_day(class_index, class_plan, result)
        class_results.append(
            class_result.model_copy(
                update={
                    "max_matches_per_team_per_day": per_day,
                    "warnings": class_warnings(
                        cup_class, class_result.min_matches_per_team, per_day
                    ),
                }
            )
        )
    days = Counter(cup_day(assignment.start) for assignment in result.assignments.values())
    return CapacityResult(
        classes=class_results,
        schedule=proposal.model_copy(update={"matches": []}),
        matches_per_day=[MatchesOnDay(day=day, matches=days[day]) for day in sorted(days)],
    )


def capacity_courts(groups: list[CapacityCourts]) -> list[CourtToPlan]:
    """The courts of the calculation; a split pitch is the full pitch plus its parts."""
    courts: list[CourtToPlan] = []
    for index, group in enumerate(groups, start=1):
        for number in range(group.count):
            full = CourtToPlan(CourtId(index * 1000 + number * 10), group.game_format)
            courts.append(full)
            courts += [
                CourtToPlan(CourtId(full.id + part), group.part_format, parent_id=full.id)
                for part in range(1, (group.split_into or 0) + 1)
            ]
    return courts
