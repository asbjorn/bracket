import { TournamentDetails } from '@openapi';
import { awaitRequestAndHandleError } from './adapter';

export async function saveTournamentDetails(tournament_id: number, details: TournamentDetails) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.put(`tournaments/${tournament_id}/details`, details),
  );
}
