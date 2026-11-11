import { Tiebreaker } from '@openapi';
import { createAxios, handleRequestError } from './adapter';

export async function createRanking(tournament_id: number) {
  return createAxios()
    .post(`tournaments/${tournament_id}/rankings`, {})
    .catch((response: any) => handleRequestError(response));
}

export async function editRanking(
  tournament_id: number,
  ranking_id: number,
  win_points: string,
  draw_points: string,
  loss_points: string,
  add_score_points: boolean,
  position: number,
  tiebreakers: Tiebreaker[],
  fair_play_yellow_points: number,
  fair_play_red_points: number,
) {
  return createAxios()
    .put(`tournaments/${tournament_id}/rankings/${ranking_id}`, {
      win_points,
      draw_points,
      loss_points,
      add_score_points,
      position,
      tiebreakers,
      fair_play_yellow_points,
      fair_play_red_points,
    })
    .catch((response: any) => handleRequestError(response));
}

export async function deleteRanking(tournament_id: number, ranking_id: number) {
  return createAxios()
    .delete(`tournaments/${tournament_id}/rankings/${ranking_id}`)
    .catch((response: any) => handleRequestError(response));
}
