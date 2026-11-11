from datetime import timedelta

from bracket.database import database
from bracket.logic.officials import MatchSlot
from bracket.logic.participating_clubs import get_club_names
from bracket.logic.scheduling.group_draw import club_name_of, club_of
from bracket.models.db.official import (
    CourtHost,
    CourtHostBody,
    MatchOfficial,
    MatchOfficialRole,
    Official,
    OfficialBody,
    PublicMatchOfficial,
)
from bracket.models.db.stage_item_inputs import StageItemInputFinal
from bracket.sql.categories import get_all_categories_in_tournament
from bracket.sql.stages import get_full_tournament_details
from bracket.utils.id_types import CourtHostId, MatchId, OfficialId, TournamentId

OFFICIAL_COLUMNS = """
    name, age, level, club_name, phone, email, role, fee_per_match, fee_per_day, active
"""


def official_values(body: OfficialBody) -> dict[str, object]:
    values: dict[str, object] = body.model_dump()
    values["email"] = str(body.email) if body.email is not None else None
    values["role"] = body.role.value
    return values


async def get_officials(tournament_id: TournamentId) -> list[Official]:
    rows = await database.fetch_all(
        "SELECT * FROM officials WHERE tournament_id = :tournament_id ORDER BY name, id",
        values={"tournament_id": tournament_id},
    )
    return [Official.model_validate(dict(row._mapping)) for row in rows]


async def sql_create_official(tournament_id: TournamentId, body: OfficialBody) -> Official:
    row = await database.fetch_one(
        f"""
        INSERT INTO officials (tournament_id, created, {OFFICIAL_COLUMNS})
        VALUES (
            :tournament_id, NOW(), :name, :age, :level, :club_name, :phone, :email, :role,
            :fee_per_match, :fee_per_day, :active
        )
        RETURNING *
        """,
        values={"tournament_id": tournament_id} | official_values(body),
    )
    assert row is not None
    return Official.model_validate(dict(row._mapping))


async def sql_update_official(
    tournament_id: TournamentId, official_id: OfficialId, body: OfficialBody
) -> bool:
    row = await database.fetch_one(
        """
        UPDATE officials
        SET name = :name, age = :age, level = :level, club_name = :club_name, phone = :phone,
            email = :email, role = :role, fee_per_match = :fee_per_match,
            fee_per_day = :fee_per_day, active = :active
        WHERE id = :official_id AND tournament_id = :tournament_id
        RETURNING id
        """,
        values={"tournament_id": tournament_id, "official_id": official_id} | official_values(body),
    )
    return row is not None


async def sql_delete_official(tournament_id: TournamentId, official_id: OfficialId) -> bool:
    row = await database.fetch_one(
        """
        DELETE FROM officials WHERE id = :official_id AND tournament_id = :tournament_id
        RETURNING id
        """,
        values={"tournament_id": tournament_id, "official_id": official_id},
    )
    return row is not None


async def get_match_officials(tournament_id: TournamentId) -> list[MatchOfficial]:
    rows = await database.fetch_all(
        """
        SELECT mo.match_id, mo.official_id, mo.role
        FROM match_officials mo
        JOIN officials o ON o.id = mo.official_id
        WHERE o.tournament_id = :tournament_id
        ORDER BY mo.match_id, mo.role DESC, mo.id
        """,
        values={"tournament_id": tournament_id},
    )
    return [MatchOfficial.model_validate(dict(row._mapping)) for row in rows]


async def get_public_match_officials(tournament_id: TournamentId) -> list[PublicMatchOfficial]:
    """Names only: for public pages, the pitch page and printed match cards."""
    rows = await database.fetch_all(
        """
        SELECT mo.match_id, o.name, mo.role
        FROM match_officials mo
        JOIN officials o ON o.id = mo.official_id
        WHERE o.tournament_id = :tournament_id
        ORDER BY mo.match_id, mo.role DESC, o.name
        """,
        values={"tournament_id": tournament_id},
    )
    return [PublicMatchOfficial.model_validate(dict(row._mapping)) for row in rows]


async def insert_match_official(
    match_id: MatchId, official_id: OfficialId, role: MatchOfficialRole
) -> None:
    await database.execute(
        """
        INSERT INTO match_officials (match_id, official_id, role)
        VALUES (:match_id, :official_id, :role)
        """,
        values={"match_id": match_id, "official_id": official_id, "role": role.value},
    )


async def sql_replace_match_officials(
    match_id: MatchId, referee_id: OfficialId | None, assistant_ids: list[OfficialId]
) -> None:
    async with database.transaction():
        await database.execute(
            "DELETE FROM match_officials WHERE match_id = :match_id", values={"match_id": match_id}
        )
        if referee_id is not None:
            await insert_match_official(match_id, referee_id, MatchOfficialRole.REFEREE)
        for assistant_id in assistant_ids:
            await insert_match_official(match_id, assistant_id, MatchOfficialRole.ASSISTANT)


async def sql_set_referee(match_ids: list[MatchId], referee_id: OfficialId) -> None:
    """The official becomes the referee of the matches; other assistants stay."""
    async with database.transaction():
        for match_id in match_ids:
            await database.execute(
                """
                DELETE FROM match_officials
                WHERE match_id = :match_id AND (role = 'REFEREE' OR official_id = :official_id)
                """,
                values={"match_id": match_id, "official_id": referee_id},
            )
            await insert_match_official(match_id, referee_id, MatchOfficialRole.REFEREE)


async def get_court_hosts(tournament_id: TournamentId) -> list[CourtHost]:
    rows = await database.fetch_all(
        """
        SELECT * FROM court_hosts WHERE tournament_id = :tournament_id
        ORDER BY start_time, court_id, id
        """,
        values={"tournament_id": tournament_id},
    )
    return [CourtHost.model_validate(dict(row._mapping)) for row in rows]


async def sql_create_court_host(tournament_id: TournamentId, body: CourtHostBody) -> None:
    await database.execute(
        """
        INSERT INTO court_hosts (tournament_id, court_id, official_id, start_time, end_time)
        VALUES (:tournament_id, :court_id, :official_id, :start_time, :end_time)
        """,
        values={"tournament_id": tournament_id} | body.model_dump(),
    )


async def sql_delete_court_host(tournament_id: TournamentId, court_host_id: CourtHostId) -> bool:
    row = await database.fetch_one(
        """
        DELETE FROM court_hosts WHERE id = :id AND tournament_id = :tournament_id RETURNING id
        """,
        values={"tournament_id": tournament_id, "id": court_host_id},
    )
    return row is not None


async def get_match_slots(tournament_id: TournamentId) -> dict[MatchId, MatchSlot]:
    """Every match of the tournament with its time, court and the clubs of its teams."""
    slots = {}
    club_names = await get_club_names(tournament_id)
    age_of_class = {c.id: c.age for c in await get_all_categories_in_tournament(tournament_id)}
    for stage in await get_full_tournament_details(tournament_id):
        for stage_item in stage.stage_items:
            for round_ in stage_item.rounds:
                for match in round_.matches:
                    end = (
                        match.start_time
                        + timedelta(minutes=match.duration_minutes + match.margin_minutes)
                        if match.start_time is not None
                        else None
                    )
                    clubs = frozenset(
                        club_of(input_.team.name, club_name_of(input_.team.club_id, club_names))
                        for input_ in (match.stage_item_input1, match.stage_item_input2)
                        if isinstance(input_, StageItemInputFinal)
                    )
                    slots[match.id] = MatchSlot(
                        match.id,
                        match.start_time,
                        end,
                        match.court_id,
                        clubs,
                        player_age=(
                            age_of_class.get(stage.category_id)
                            if stage.category_id is not None
                            else None
                        ),
                    )
    return slots
