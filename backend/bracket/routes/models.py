from pydantic import BaseModel

from bracket.logic.category_warnings import CategoryWarning
from bracket.logic.notifications import NotificationStatus, ScheduleNoticeResult
from bracket.logic.planning.capacity import CapacityResult
from bracket.logic.planning.propose import PlanIssueOut, ScheduleProposal
from bracket.logic.scheduling.handle_stage_activation import StageItemInputUpdate
from bracket.logic.scheduling.stage_draw import DrawPlacement
from bracket.models.db.category import Category
from bracket.models.db.club import Club
from bracket.models.db.court import Court
from bracket.models.db.discipline import DisciplineOverview, MatchCard
from bracket.models.db.district_application import DistrictApplication
from bracket.models.db.match import Match, SuggestedMatch
from bracket.models.db.official import Official, OfficialsOverview, PublicMatchOfficial
from bracket.models.db.player import Player
from bracket.models.db.public_info import Announcement, PublicNotices, Rules
from bracket.models.db.ranking import Ranking
from bracket.models.db.registration import (
    PublicRegistrationClass,
    PublicRegistrationResult,
    Registration,
)
from bracket.models.db.score_link import (
    MatchDayNotice,
    ScoreEntryView,
    ScoreLink,
    ScoreLinkCreated,
)
from bracket.models.db.stage_item_inputs import (
    StageItemInputOptionFinal,
    StageItemInputOptionTentative,
)
from bracket.models.db.team import FullTeamWithPlayers, Team
from bracket.models.db.time_window import TimeWindow
from bracket.models.db.tournament import Tournament
from bracket.models.db.user import UserPublic
from bracket.models.db.util import StageWithStageItems
from bracket.routes.auth import Token
from bracket.utils.id_types import CategoryId, StageId, StageItemId


class SuccessResponse(BaseModel):
    success: bool = True


class DataResponse[DataT](BaseModel):
    data: DataT


class ClubsResponse(DataResponse[list[Club]]):
    pass


class ClubResponse(DataResponse[Club | None]):
    pass


class TournamentResponse(DataResponse[Tournament]):
    pass


class TournamentsResponse(DataResponse[list[Tournament]]):
    pass


class PaginatedPlayers(BaseModel):
    count: int
    players: list[Player]


class PlayersResponse(DataResponse[PaginatedPlayers]):
    pass


class SinglePlayerResponse(DataResponse[Player]):
    pass


class StagesWithStageItemsResponse(DataResponse[list[StageWithStageItems]]):
    pass


class UpcomingMatchesResponse(DataResponse[list[SuggestedMatch]]):
    pass


class SingleMatchResponse(DataResponse[Match]):
    pass


class PaginatedTeams(BaseModel):
    count: int
    teams: list[FullTeamWithPlayers]


class TeamsWithPlayersResponse(DataResponse[PaginatedTeams]):
    pass


class SingleTeamResponse(DataResponse[Team]):
    pass


class UserPublicResponse(DataResponse[UserPublic]):
    pass


class TokenResponse(DataResponse[Token]):
    pass


class CourtsResponse(DataResponse[list[Court]]):
    pass


class CategoriesResponse(DataResponse[list[Category]]):
    pass


class TimeWindowsResponse(DataResponse[list[TimeWindow]]):
    pass


class ScheduleProposalResponse(DataResponse[ScheduleProposal]):
    pass


class PlanIssuesResponse(DataResponse[list[PlanIssueOut]]):
    pass


class DisciplineOverviewResponse(DataResponse[DisciplineOverview]):
    pass


class MatchCardResponse(DataResponse[MatchCard]):
    pass


class OfficialResponse(DataResponse[Official]):
    pass


class OfficialsOverviewResponse(DataResponse[OfficialsOverview]):
    pass


class PublicMatchOfficialsResponse(DataResponse[list[PublicMatchOfficial]]):
    pass


class DrawResponse(DataResponse[list[DrawPlacement]]):
    pass


class ScoreLinksResponse(DataResponse[list[ScoreLink]]):
    pass


class ScoreLinkCreatedResponse(DataResponse[ScoreLinkCreated]):
    pass


class ScoreEntryViewResponse(DataResponse[ScoreEntryView]):
    pass


class MatchDayNoticeResponse(DataResponse[MatchDayNotice]):
    pass


class MatchDayNoticesResponse(DataResponse[list[MatchDayNotice]]):
    pass


class AnnouncementResponse(DataResponse[Announcement | None]):
    pass


class PublicNoticesResponse(DataResponse[PublicNotices]):
    pass


class RulesResponse(DataResponse[Rules]):
    pass


class DistrictApplicationResponse(DataResponse[DistrictApplication]):
    pass


class NotificationStatusResponse(DataResponse[NotificationStatus]):
    pass


class NotificationsQueuedResponse(DataResponse[int]):
    pass


class ScheduleNoticeResponse(DataResponse[ScheduleNoticeResult]):
    pass


class CapacityResponse(DataResponse[CapacityResult]):
    pass


class CountResponse(DataResponse[int]):
    pass


class SingleCategoryResponse(DataResponse[Category]):
    pass


class CategoryWarningsResponse(DataResponse[dict[CategoryId, list[CategoryWarning]]]):
    pass


class SingleCourtResponse(DataResponse[Court]):
    pass


class RankingsResponse(DataResponse[list[Ranking]]):
    pass


class StageItemInputOptionsResponse(
    DataResponse[dict[StageId, list[StageItemInputOptionTentative | StageItemInputOptionFinal]]]
):
    pass


class StageRankingResponse(DataResponse[dict[StageItemId, list[StageItemInputUpdate]]]):
    pass


class PublicRegistrationClassesResponse(DataResponse[list[PublicRegistrationClass]]):
    pass


class PublicRegistrationResponse(DataResponse[PublicRegistrationResult]):
    pass


class RegistrationsResponse(DataResponse[list[Registration]]):
    pass
