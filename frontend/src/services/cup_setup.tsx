import { CupSetupBody } from '@openapi';
import { awaitRequestAndHandleError } from './adapter';

export async function setUpCup(tournament_id: number, body: CupSetupBody) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post(`tournaments/${tournament_id}/cup_setup`, body),
  );
}
