import { PlayoffsCreateBody } from '@openapi';
import { awaitRequestAndHandleError } from './adapter';

export async function createPlayoffs(tournament_id: number, body: PlayoffsCreateBody) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post(`tournaments/${tournament_id}/playoffs`, body),
  );
}
