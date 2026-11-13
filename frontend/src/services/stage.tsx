import { FitGroupsResponse, LevelRoundBody, PlayoffPreset } from '@openapi';
import { awaitRequestAndHandleError, createAxios, handleRequestError } from './adapter';

export async function createStage(tournament_id: number, category_id: number | null) {
  return createAxios()
    .post(`tournaments/${tournament_id}/stages`, { category_id })
    .catch((response: any) => handleRequestError(response));
}

export async function updateStage(tournament_id: number, stage_id: number, name: string) {
  return createAxios()
    .put(`tournaments/${tournament_id}/stages/${stage_id}`, { name })
    .catch((response: any) => handleRequestError(response));
}

export async function activateNextStage(
  tournament_id: number,
  direction: string,
  category_id: number | null,
) {
  return createAxios()
    .post(`tournaments/${tournament_id}/stages/activate`, { direction, category_id })
    .catch((response: any) => handleRequestError(response));
}

export async function deleteStage(tournament_id: number, stage_id: number) {
  return createAxios()
    .delete(`tournaments/${tournament_id}/stages/${stage_id}`)
    .catch((response: any) => handleRequestError(response));
}

export async function createLevelRound(
  tournament_id: number,
  category_id: number,
  body: LevelRoundBody,
) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post(`tournaments/${tournament_id}/categories/${category_id}/level_round`, body),
  );
}

/** A change of the format of a class: group size, and optionally its playoffs. */
export interface FormatParams {
  group_size: number;
  playoffs?: PlayoffPreset;
  third_place_match?: boolean;
  playoff_stage_name?: string;
  playoff_name?: string;
}

/** What changing the format of a class would create; throws on an error. */
export async function previewFitGroups(
  tournament_id: number,
  stage_id: number,
  params: FormatParams,
) {
  return createAxios().get<FitGroupsResponse>(
    `tournaments/${tournament_id}/stages/${stage_id}/fit_groups`,
    { params },
  );
}

export async function fitGroups(tournament_id: number, stage_id: number, params: FormatParams) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post<FitGroupsResponse>(
      `tournaments/${tournament_id}/stages/${stage_id}/fit_groups`,
      null,
      { params },
    ),
  );
}

/** Moves a team to another place in the groups: an empty one, or swapped with its team. */
export async function moveTeam(
  tournament_id: number,
  stage_id: number,
  team_id: number,
  target_input_id: number,
) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post(`tournaments/${tournament_id}/stages/${stage_id}/move_team`, {
      team_id,
      target_input_id,
    }),
  );
}
