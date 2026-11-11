import { createAxios, handleRequestError } from './adapter';

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
