from bracket.database import database
from bracket.models.db.discipline import (
    DisciplineSettingsBody,
    JuryDecision,
    JuryDecisionBody,
    MatchCard,
    MatchCardBody,
)
from bracket.utils.id_types import (
    JuryDecisionId,
    MatchCardId,
    MatchId,
    TournamentId,
    UserId,
)


async def get_cards(tournament_id: TournamentId) -> list[MatchCard]:
    rows = await database.fetch_all(
        "SELECT * FROM match_cards WHERE tournament_id = :tournament_id ORDER BY id",
        values={"tournament_id": tournament_id},
    )
    return [MatchCard.model_validate(dict(row._mapping)) for row in rows]


async def sql_create_card(
    tournament_id: TournamentId, match_id: MatchId, body: MatchCardBody
) -> MatchCard:
    row = await database.fetch_one(
        """
        INSERT INTO match_cards (
            tournament_id, match_id, team_id, player_name, player_id, card_type, minute, note,
            created
        )
        VALUES (
            :tournament_id, :match_id, :team_id, :player_name, :player_id, :card_type, :minute,
            :note, NOW()
        )
        RETURNING *
        """,
        values={
            "tournament_id": tournament_id,
            "match_id": match_id,
            "team_id": body.team_id,
            "player_name": body.player_name,
            "player_id": body.player_id,
            "card_type": body.card_type.value,
            "minute": body.minute,
            "note": body.note or None,
        },
    )
    assert row is not None
    return MatchCard.model_validate(dict(row._mapping))


async def sql_delete_card(tournament_id: TournamentId, card_id: MatchCardId) -> bool:
    row = await database.fetch_one(
        "DELETE FROM match_cards WHERE id = :id AND tournament_id = :tournament_id RETURNING id",
        values={"id": card_id, "tournament_id": tournament_id},
    )
    return row is not None


async def get_jury_decisions(tournament_id: TournamentId) -> list[JuryDecision]:
    rows = await database.fetch_all(
        """
        SELECT * FROM jury_decisions WHERE tournament_id = :tournament_id
        ORDER BY decided_at DESC, id DESC
        """,
        values={"tournament_id": tournament_id},
    )
    return [JuryDecision.model_validate(dict(row._mapping)) for row in rows]


async def sql_create_jury_decision(
    tournament_id: TournamentId, body: JuryDecisionBody, user_id: UserId
) -> None:
    await database.execute(
        """
        INSERT INTO jury_decisions (
            tournament_id, match_id, team_id, card_id, text, suspension_change, decided_at,
            decided_by
        )
        VALUES (
            :tournament_id, :match_id, :team_id, :card_id, :text, :suspension_change, NOW(),
            :decided_by
        )
        """,
        values={
            "tournament_id": tournament_id,
            "match_id": body.match_id,
            "team_id": body.team_id,
            "card_id": body.card_id,
            "text": body.text,
            "suspension_change": body.suspension_change,
            "decided_by": user_id,
        },
    )


async def sql_delete_jury_decision(
    tournament_id: TournamentId, decision_id: JuryDecisionId
) -> bool:
    row = await database.fetch_one(
        """
        DELETE FROM jury_decisions WHERE id = :id AND tournament_id = :tournament_id RETURNING id
        """,
        values={"id": decision_id, "tournament_id": tournament_id},
    )
    return row is not None


async def get_discipline_settings(tournament_id: TournamentId) -> DisciplineSettingsBody:
    row = await database.fetch_one(
        """
        SELECT suspension_matches_per_red, yellow_cards_for_suspension
        FROM tournaments WHERE id = :tournament_id
        """,
        values={"tournament_id": tournament_id},
    )
    assert row is not None
    return DisciplineSettingsBody.model_validate(dict(row._mapping))


async def sql_set_discipline_settings(
    tournament_id: TournamentId, body: DisciplineSettingsBody
) -> None:
    await database.execute(
        """
        UPDATE tournaments
        SET suspension_matches_per_red = :suspension_matches_per_red,
            yellow_cards_for_suspension = :yellow_cards_for_suspension
        WHERE id = :tournament_id
        """,
        values={
            "tournament_id": tournament_id,
            "suspension_matches_per_red": body.suspension_matches_per_red,
            "yellow_cards_for_suspension": body.yellow_cards_for_suspension,
        },
    )
