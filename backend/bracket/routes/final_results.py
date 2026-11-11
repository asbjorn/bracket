from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from starlette.responses import Response

from bracket.config import config
from bracket.database import database
from bracket.logic.final_results import ClassFinalResults, class_final_results
from bracket.models.db.tournament import Tournament
from bracket.models.db.user import UserPublic
from bracket.routes.auth import user_authenticated_for_tournament
from bracket.routes.models import FinalResultsResponse, SuccessResponse
from bracket.routes.util import disallow_archived_tournament
from bracket.sql.categories import get_all_categories_in_tournament
from bracket.sql.discipline import get_cards
from bracket.sql.rankings import get_ranking_for_stage_item
from bracket.sql.stages import get_full_tournament_details
from bracket.sql.teams import get_teams_with_members
from bracket.sql.tournaments import sql_get_tournament
from bracket.utils.csv_export import to_csv
from bracket.utils.id_types import TournamentId
from bracket.utils.types import assert_some

router = APIRouter(prefix=config.api_prefix)


class CeremonySettingsBody(BaseModel):
    # Minutes from a class's last match to its prize ceremony
    ceremony_offset_minutes: int = Field(ge=0, le=240)


async def get_final_results(tournament_id: TournamentId) -> list[ClassFinalResults]:
    tournament = await sql_get_tournament(tournament_id)
    stages = await get_full_tournament_details(tournament_id)
    teams = await get_teams_with_members(tournament_id, only_participating=True)
    cards = await get_cards(tournament_id)
    rankings = {
        item.id: assert_some(await get_ranking_for_stage_item(tournament_id, item.id))
        for stage in stages
        for item in stage.stage_items
    }
    return [
        class_final_results(
            category, stages, teams, rankings, cards, tournament.ceremony_offset_minutes
        )
        for category in await get_all_categories_in_tournament(tournament_id)
    ]


@router.get("/tournaments/{tournament_id}/final_results", response_model=FinalResultsResponse)
async def get_tournament_final_results(
    tournament_id: TournamentId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
) -> FinalResultsResponse:
    """Per class: the final placings, the prize ceremony time and the medals to hand out."""
    return FinalResultsResponse(data=await get_final_results(tournament_id))


@router.get("/tournaments/{tournament_id}/final_results.csv", response_class=Response)
async def export_final_results(
    tournament_id: TournamentId,
    language: str = "nb",
    _: UserPublic = Depends(user_authenticated_for_tournament),
) -> Response:
    """The final placings of all classes as a spreadsheet."""
    norwegian = language == "nb"
    header = (
        ["Klasse", "Sluttspill/pulje", "Plass", "Lag"]
        if norwegian
        else ["Class", "Playoff/group", "Place", "Team"]
    )
    rows = [
        [result.name, podium.title, placing.place, placing.team_name]
        for result in await get_final_results(tournament_id)
        for podium in result.podiums
        for placing in podium.placings
    ]
    return Response(
        to_csv(header, rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="resultater.csv"'},
    )


@router.put("/tournaments/{tournament_id}/ceremony_settings", response_model=SuccessResponse)
async def update_ceremony_settings(
    tournament_id: TournamentId,
    body: CeremonySettingsBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    await database.execute(
        "UPDATE tournaments SET ceremony_offset_minutes = :minutes WHERE id = :id",
        values={"minutes": body.ceremony_offset_minutes, "id": tournament_id},
    )
    return SuccessResponse()
