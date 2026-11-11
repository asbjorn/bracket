from bracket.database import database
from bracket.models.db.jury import JuryMember, JuryMemberBody
from bracket.utils.id_types import TournamentId


async def get_jury_members(tournament_id: TournamentId) -> list[JuryMember]:
    rows = await database.fetch_all(
        """
        SELECT * FROM jury_members WHERE tournament_id = :tournament_id
        ORDER BY role = 'MEMBER', name
        """,
        values={"tournament_id": tournament_id},
    )
    return [JuryMember.model_validate(dict(row._mapping)) for row in rows]


def member_values(body: JuryMemberBody) -> dict[str, str | None]:
    return {
        "name": body.name,
        "club_name": body.club_name,
        "phone": body.phone,
        "role": body.role.value,
    }


async def sql_create_jury_member(tournament_id: TournamentId, body: JuryMemberBody) -> None:
    await database.execute(
        """
        INSERT INTO jury_members (tournament_id, name, club_name, phone, role)
        VALUES (:tournament_id, :name, :club_name, :phone, :role)
        """,
        values={"tournament_id": tournament_id, **member_values(body)},
    )


async def sql_update_jury_member(
    tournament_id: TournamentId, member_id: int, body: JuryMemberBody
) -> bool:
    row = await database.fetch_one(
        """
        UPDATE jury_members
        SET name = :name, club_name = :club_name, phone = :phone, role = :role
        WHERE id = :id AND tournament_id = :tournament_id
        RETURNING id
        """,
        values={"tournament_id": tournament_id, "id": member_id, **member_values(body)},
    )
    return row is not None


async def sql_delete_jury_member(tournament_id: TournamentId, member_id: int) -> bool:
    row = await database.fetch_one(
        "DELETE FROM jury_members WHERE id = :id AND tournament_id = :tournament_id RETURNING id",
        values={"tournament_id": tournament_id, "id": member_id},
    )
    return row is not None
