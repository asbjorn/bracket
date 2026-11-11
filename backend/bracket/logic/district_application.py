"""
The application to the district (krets, sent in FIKS): a summary of the cup from what Bracket
knows (playing days, courts, classes, teams, matches) plus the facts the organiser enters.
"""

from collections import Counter
from itertools import groupby

from bracket.database import database
from bracket.logic.public_info import get_rules
from bracket.models.db.district_application import (
    ApplicationClass,
    CourtCount,
    DistrictApplication,
    PlayingDay,
    TournamentDetails,
)
from bracket.models.db.stage_item import StageType
from bracket.models.db.team import PARTICIPATING_STATUSES
from bracket.models.db.time_window import TimeWindow
from bracket.schema import tournament_details
from bracket.sql.categories import get_all_categories_in_tournament
from bracket.sql.courts import get_all_courts_in_tournament
from bracket.sql.stages import get_full_tournament_details
from bracket.sql.time_windows import get_time_windows
from bracket.sql.tournaments import sql_get_tournament
from bracket.utils.cup_time import CUP_TIMEZONE
from bracket.utils.id_types import TournamentId

DETAIL_FIELDS = tuple(TournamentDetails.model_fields)


async def get_details(tournament_id: TournamentId) -> TournamentDetails:
    row = await database.fetch_one(
        tournament_details.select().where(tournament_details.c.tournament_id == tournament_id)
    )
    if row is None:
        return TournamentDetails()
    return TournamentDetails.model_validate({field: row[field] for field in DETAIL_FIELDS})


async def set_details(tournament_id: TournamentId, details: TournamentDetails) -> None:
    values = {field: getattr(details, field) or None for field in DETAIL_FIELDS}
    columns = ", ".join(DETAIL_FIELDS)
    placeholders = ", ".join(f":{field}" for field in DETAIL_FIELDS)
    updates = ", ".join(f"{field} = excluded.{field}" for field in DETAIL_FIELDS)
    await database.execute(
        f"""
        INSERT INTO tournament_details (tournament_id, {columns})
        VALUES (:tournament_id, {placeholders})
        ON CONFLICT (tournament_id) DO UPDATE SET {updates}
        """,
        values={"tournament_id": tournament_id, **values},
    )


def playing_days(windows: list[TimeWindow]) -> list[PlayingDay]:
    """Time windows per day in Norwegian time, e.g. 09:00-12:00 and 12:45-17:00."""
    local = sorted(
        (w.start_time.astimezone(CUP_TIMEZONE), w.end_time.astimezone(CUP_TIMEZONE))
        for w in windows
    )
    days = []
    for day, day_windows in groupby(local, key=lambda window: window[0].date()):
        spans = list(day_windows)
        days.append(
            PlayingDay(
                day=day,
                first_start=spans[0][0].strftime("%H:%M"),
                last_end=max(end for _, end in spans).strftime("%H:%M"),
                windows=[f"{start:%H:%M}-{end:%H:%M}" for start, end in spans],
            )
        )
    return days


async def get_team_counts(tournament_id: TournamentId) -> Counter[int | None]:
    rows = await database.fetch_all(
        """
        SELECT category_id, count(*) AS team_count FROM teams
        WHERE tournament_id = :tournament_id AND registration_status = any(:statuses)
        GROUP BY category_id
        """,
        values={
            "tournament_id": tournament_id,
            "statuses": sorted(status.value for status in PARTICIPATING_STATUSES),
        },
    )
    return Counter({row["category_id"]: int(row["team_count"]) for row in rows})


async def get_district_application(tournament_id: TournamentId) -> DistrictApplication:
    tournament = await sql_get_tournament(tournament_id)
    categories = await get_all_categories_in_tournament(tournament_id)
    stages = await get_full_tournament_details(tournament_id)
    courts = await get_all_courts_in_tournament(tournament_id)
    team_counts = await get_team_counts(tournament_id)

    match_counts: Counter[int | None] = Counter()
    with_playoffs: set[int | None] = set()
    for stage in stages:
        for item in stage.stage_items:
            match_counts[stage.category_id] += sum(len(r.matches) for r in item.rounds)
            if item.type is StageType.SINGLE_ELIMINATION:
                with_playoffs.add(stage.category_id)

    classes = [
        ApplicationClass(
            name=category.name,
            age=category.age,
            game_format=category.game_format,
            duration_minutes=category.duration_minutes or tournament.duration_minutes,
            margin_minutes=(
                category.margin_minutes
                if category.margin_minutes is not None
                else tournament.margin_minutes
            ),
            team_count=team_counts[category.id],
            max_teams=category.max_teams,
            entry_fee=category.entry_fee,
            results_public=category.results_public,
            has_playoffs=category.id in with_playoffs,
            match_count=match_counts[category.id],
        )
        for category in categories
    ]
    formats = Counter(court.game_format for court in courts)
    return DistrictApplication(
        tournament_name=tournament.name,
        details=await get_details(tournament_id),
        days=playing_days(await get_time_windows(tournament_id)),
        courts=[
            CourtCount(game_format=game_format, count=count)
            for game_format, count in sorted(
                formats.items(), key=lambda item: "" if item[0] is None else item[0].value
            )
        ],
        classes=classes,
        team_count=sum(team_counts.values()),
        match_count=sum(match_counts.values()),
        rules_text=(await get_rules(tournament_id)).text or None,
    )
