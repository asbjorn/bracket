import { CountResponse } from '@openapi';
import { awaitRequestAndHandleError, createAxios, handleRequestError } from './adapter';

export async function createTeam(
  tournament_id: number,
  name: string,
  active: boolean,
  player_ids: string[],
  category_id: number | null,
  club_id: number | null,
) {
  return createAxios()
    .post(`tournaments/${tournament_id}/teams`, {
      name,
      active,
      player_ids,
      category_id,
      club_id,
    })
    .catch((response: any) => handleRequestError(response));
}

export async function createTeams(
  tournament_id: number,
  names: string,
  active: boolean,
  category_id: number | null,
) {
  return createAxios()
    .post(`tournaments/${tournament_id}/teams_multi`, { names, active, category_id })
    .catch((response: any) => handleRequestError(response));
}

export async function deleteTeam(tournament_id: number, team_id: number) {
  await createAxios()
    .delete(`tournaments/${tournament_id}/teams/${team_id}`)
    .catch((response: any) => handleRequestError(response));
}

export async function updateTeam(
  tournament_id: number,
  team_id: number,
  name: string,
  active: boolean,
  player_ids: string[],
  category_id: number | null,
  club_id: number | null,
) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.put(`tournaments/${tournament_id}/teams/${team_id}`, {
      name,
      active,
      player_ids,
      category_id,
      club_id,
    }),
  );
}

export async function withdrawTeam(tournament_id: number, team_id: number) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post<CountResponse>(`tournaments/${tournament_id}/teams/${team_id}/withdraw`),
  );
}

export async function reinstateTeam(tournament_id: number, team_id: number) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post(`tournaments/${tournament_id}/teams/${team_id}/reinstate`),
  );
}

export async function setTeamCheckedIn(
  tournament_id: number,
  team_id: number,
  checked_in: boolean,
) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.put(`tournaments/${tournament_id}/teams/${team_id}/check_in`, { checked_in }),
  );
}
