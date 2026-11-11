import { DrawBody, DrawResponse } from '@openapi';
import { awaitRequestAndHandleError } from './adapter';

export async function drawTeams(tournament_id: number, stage_id: number, body: DrawBody) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post<DrawResponse>(`tournaments/${tournament_id}/stages/${stage_id}/draw`, body),
  );
}
