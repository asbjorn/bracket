"""
Information for the public pages: the announcement banner, delays reported from the pitches,
the rules sheet and a calendar feed per team. Results of classes with hidden results never
appear here (NFF: no results for children's football).
"""

from datetime import timedelta

from fastapi import HTTPException
from heliclockter import datetime_utc
from starlette import status

from bracket.database import database
from bracket.logic.ical import CalendarEvent, build_calendar
from bracket.logic.walkovers import team_of
from bracket.models.db.public_info import (
    Announcement,
    AnnouncementLevel,
    PublicDelay,
    PublicNotices,
    Rules,
)
from bracket.sql.categories import get_all_categories_in_tournament
from bracket.sql.stages import get_full_tournament_details
from bracket.sql.teams import get_team_by_id
from bracket.sql.tournaments import sql_get_tournament
from bracket.utils.id_types import TeamId, TournamentId

# Delays reported from a pitch are shown publicly this long, unless resolved before
PUBLIC_DELAY_HOURS = 3


async def get_announcement(tournament_id: TournamentId) -> Announcement | None:
    row = await database.fetch_one(
        """
        SELECT announcement_text, announcement_level, announcement_until
        FROM tournaments WHERE id = :tournament_id
        """,
        values={"tournament_id": tournament_id},
    )
    values = dict(row._mapping) if row is not None else {}
    if values.get("announcement_text") is None:
        return None
    return Announcement(
        text=values["announcement_text"],
        level=AnnouncementLevel(values["announcement_level"] or AnnouncementLevel.INFO),
        until=values["announcement_until"],
    )


async def set_announcement(tournament_id: TournamentId, announcement: Announcement | None) -> None:
    await database.execute(
        """
        UPDATE tournaments
        SET announcement_text = :text, announcement_level = :level, announcement_until = :until
        WHERE id = :tournament_id
        """,
        values={
            "tournament_id": tournament_id,
            "text": announcement.text if announcement else None,
            "level": announcement.level.value if announcement else None,
            "until": announcement.until if announcement else None,
        },
    )


async def get_public_notices(tournament_id: TournamentId, now: datetime_utc) -> PublicNotices:
    announcement = await get_announcement(tournament_id)
    if announcement is not None and announcement.until is not None and announcement.until <= now:
        announcement = None

    rows = await database.fetch_all(
        """
        SELECT courts.name AS court_name, notices.delay_minutes, notices.created
        FROM match_day_notices notices
        LEFT JOIN courts ON courts.id = notices.court_id
        WHERE notices.tournament_id = :tournament_id
        AND NOT notices.resolved
        AND notices.delay_minutes IS NOT NULL
        AND notices.created > :since
        ORDER BY notices.created DESC
        LIMIT 20
        """,
        values={"tournament_id": tournament_id, "since": now - timedelta(hours=PUBLIC_DELAY_HOURS)},
    )
    delays = [PublicDelay.model_validate(dict(row._mapping)) for row in rows]
    return PublicNotices(announcement=announcement, delays=delays)


async def get_rules(tournament_id: TournamentId) -> Rules:
    text = await database.fetch_val(
        "SELECT rules_text FROM tournaments WHERE id = :tournament_id",
        values={"tournament_id": tournament_id},
    )
    return Rules(text=text or "")


async def set_rules(tournament_id: TournamentId, rules: Rules) -> None:
    await database.execute(
        "UPDATE tournaments SET rules_text = :text WHERE id = :tournament_id",
        values={"tournament_id": tournament_id, "text": rules.text.strip() or None},
    )


async def team_calendar(tournament_id: TournamentId, team_id: TeamId, now: datetime_utc) -> str:
    """The scheduled matches of a team as an iCalendar feed; scores only for public classes."""
    team = await get_team_by_id(team_id, tournament_id)
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Could not find the team")
    tournament = await sql_get_tournament(tournament_id)
    categories = {c.id: c for c in await get_all_categories_in_tournament(tournament_id)}

    events: list[CalendarEvent] = []
    for stage in await get_full_tournament_details(tournament_id):
        category = categories.get(stage.category_id) if stage.category_id is not None else None
        results_public = category is None or category.results_public
        for stage_item in stage.stage_items:
            for round_ in stage_item.rounds:
                for match in round_.matches:
                    (team1_id, team1), (team2_id, team2) = (
                        team_of(match.stage_item_input1),
                        team_of(match.stage_item_input2),
                    )
                    if match.start_time is None or team_id not in (team1_id, team2_id):
                        continue
                    details = [category.name if category else None, stage_item.name]
                    if match.played and results_public:
                        details.append(
                            f"{match.stage_item_input1_score}–{match.stage_item_input2_score}"
                        )
                    events.append(
                        CalendarEvent(
                            uid=f"match-{match.id}-tournament-{tournament_id}@bracket",
                            start=match.start_time,
                            end=match.start_time + timedelta(minutes=match.duration_minutes),
                            summary=f"{team1 or '?'} – {team2 or '?'}",
                            location=match.court.name if match.court is not None else None,
                            description=" · ".join(d for d in details if d),
                        )
                    )
    events.sort(key=lambda event: (event.start, event.uid))
    return build_calendar(f"{team.name} – {tournament.name}", events, now)
