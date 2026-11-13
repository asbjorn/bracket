import { FitGroupsResponse, LevelRoundBody } from '@openapi';
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

/** What fitting the groups of a class to its teams would create; throws on an error. */
export async function previewFitGroups(
  tournament_id: number,
  stage_id: number,
  group_size: number,
) {
  return createAxios().get<FitGroupsResponse>(
    `tournaments/${tournament_id}/stages/${stage_id}/fit_groups`,
    { params: { group_size } },
  );
}

export async function fitGroups(tournament_id: number, stage_id: number, group_size: number) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post<FitGroupsResponse>(
      `tournaments/${tournament_id}/stages/${stage_id}/fit_groups`,
      null,
      { params: { group_size } },
    ),
  );
}
