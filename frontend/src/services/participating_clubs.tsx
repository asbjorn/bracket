import { ParticipatingClubCreateBody, ParticipatingClubCreatedResponse } from '@openapi';
import { awaitRequestAndHandleError } from './adapter';

export async function createParticipatingClub(
  tournament_id: number,
  body: ParticipatingClubCreateBody,
) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post<ParticipatingClubCreatedResponse>(
      `tournaments/${tournament_id}/participating_clubs`,
      body,
    ),
  );
}

export async function updateParticipatingClub(
  tournament_id: number,
  club_id: number,
  name: string,
  team_ids: number[],
) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.put(`tournaments/${tournament_id}/participating_clubs/${club_id}`, { name, team_ids }),
  );
}

export async function deleteParticipatingClub(tournament_id: number, club_id: number) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.delete(`tournaments/${tournament_id}/participating_clubs/${club_id}`),
  );
}
