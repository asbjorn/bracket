import hashlib

from heliclockter import datetime_utc, timedelta

from bracket.database import database
from bracket.models.db.score_link import (
    MatchDayNotice,
    MatchDayNoticeBody,
    ScoreLink,
    ScoreLinkBody,
)
from bracket.utils.id_types import (
    CourtId,
    MatchDayNoticeId,
    ScoreLinkId,
    TournamentId,
)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def sql_create_score_link(
    tournament_id: TournamentId, body: ScoreLinkBody, token: str
) -> ScoreLink:
    query = """
        INSERT INTO score_links (tournament_id, court_id, name, token_hash, created, expires_at)
        VALUES (:tournament_id, :court_id, :name, :token_hash, NOW(), :expires_at)
        RETURNING id, tournament_id, court_id, name, created, expires_at, revoked_at
        """
    result = await database.fetch_one(
        query,
        values={
            "tournament_id": tournament_id,
            "court_id": body.court_id,
            "name": body.name,
            "token_hash": hash_token(token),
            "expires_at": datetime_utc.now() + timedelta(hours=body.valid_hours),
        },
    )
    assert result is not None
    return ScoreLink.model_validate(dict(result._mapping))


async def get_score_links(tournament_id: TournamentId) -> list[ScoreLink]:
    query = """
        SELECT id, tournament_id, court_id, name, created, expires_at, revoked_at
        FROM score_links
        WHERE tournament_id = :tournament_id
        ORDER BY created DESC, id DESC
        """
    result = await database.fetch_all(query, values={"tournament_id": tournament_id})
    return [ScoreLink.model_validate(dict(row._mapping)) for row in result]


async def sql_revoke_score_link(tournament_id: TournamentId, score_link_id: ScoreLinkId) -> bool:
    query = """
        UPDATE score_links
        SET revoked_at = COALESCE(revoked_at, NOW())
        WHERE id = :id AND tournament_id = :tournament_id
        RETURNING id
        """
    values = {"id": score_link_id, "tournament_id": tournament_id}
    return await database.fetch_one(query, values=values) is not None


async def get_valid_score_link(token: str) -> ScoreLink | None:
    """The link of a token, unless it has expired or was revoked."""
    query = """
        SELECT id, tournament_id, court_id, name, created, expires_at, revoked_at
        FROM score_links
        WHERE token_hash = :token_hash AND revoked_at IS NULL AND expires_at > NOW()
        """
    result = await database.fetch_one(query, values={"token_hash": hash_token(token)})
    return ScoreLink.model_validate(dict(result._mapping)) if result is not None else None


async def sql_create_notice(
    tournament_id: TournamentId,
    court_id: CourtId | None,
    score_link_id: ScoreLinkId | None,
    body: MatchDayNoticeBody,
) -> MatchDayNotice:
    query = """
        INSERT INTO match_day_notices
            (tournament_id, court_id, score_link_id, delay_minutes, message, created, resolved)
        VALUES (:tournament_id, :court_id, :score_link_id, :delay_minutes, :message, NOW(), false)
        RETURNING *
        """
    result = await database.fetch_one(
        query,
        values={
            "tournament_id": tournament_id,
            "court_id": court_id,
            "score_link_id": score_link_id,
            "delay_minutes": body.delay_minutes,
            "message": body.message,
        },
    )
    assert result is not None
    return MatchDayNotice.model_validate(dict(result._mapping))


async def get_notices(tournament_id: TournamentId) -> list[MatchDayNotice]:
    query = """
        SELECT *
        FROM match_day_notices
        WHERE tournament_id = :tournament_id
        ORDER BY resolved, created DESC, id DESC
        LIMIT 100
        """
    result = await database.fetch_all(query, values={"tournament_id": tournament_id})
    return [MatchDayNotice.model_validate(dict(row._mapping)) for row in result]


async def sql_resolve_notice(tournament_id: TournamentId, notice_id: MatchDayNoticeId) -> bool:
    query = """
        UPDATE match_day_notices
        SET resolved = true
        WHERE id = :id AND tournament_id = :tournament_id
        RETURNING id
        """
    values = {"id": notice_id, "tournament_id": tournament_id}
    return await database.fetch_one(query, values=values) is not None
