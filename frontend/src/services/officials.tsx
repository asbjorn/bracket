import useSWR, { SWRResponse } from 'swr';

import {
  BlockAssignmentBody,
  CourtHostBody,
  MatchOfficialsBody,
  OfficialBody,
  OfficialsOverviewResponse,
  PublicMatchOfficial,
  PublicMatchOfficialsResponse,
} from '@openapi';
import { awaitRequestAndHandleError, createAxios, handleRequestError } from './adapter';

const fetcher = (url: string) =>
  createAxios()
    .get(url)
    .then((res: { data: any }) => res.data);

/** Officials with contact details, assignments, conflicts and fees (organiser only). */
export function getOfficialsOverview(
  tournament_id: number,
): SWRResponse<OfficialsOverviewResponse> {
  return useSWR(`tournaments/${tournament_id}/officials`, fetcher);
}

/** Referee names per match (no contact details): also on public pages. */
export function getMatchOfficials(
  tournament_id: number | null,
): SWRResponse<PublicMatchOfficialsResponse> {
  return useSWR(
    tournament_id == null ? null : `tournaments/${tournament_id}/match_officials`,
    fetcher,
  );
}

/** "Ola Nordmann (+ Kari)" per match id: the referee, then the assistants. */
export function refereeNamesByMatch(officials: PublicMatchOfficial[]): Record<number, string> {
  const byMatch: Record<number, PublicMatchOfficial[]> = {};
  officials.forEach((official) => {
    byMatch[official.match_id] = [...(byMatch[official.match_id] ?? []), official];
  });
  return Object.fromEntries(
    Object.entries(byMatch).map(([matchId, list]) => {
      const referee = list.find((o) => o.role === 'REFEREE');
      const assistants = list.filter((o) => o.role === 'ASSISTANT').map((o) => o.name);
      const names = [referee?.name, assistants.length > 0 ? `(+ ${assistants.join(', ')})` : null];
      return [matchId, names.filter(Boolean).join(' ')];
    }),
  );
}

export async function createOfficial(tournament_id: number, body: OfficialBody) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post(`tournaments/${tournament_id}/officials`, body),
  );
}

export async function updateOfficial(
  tournament_id: number,
  official_id: number,
  body: OfficialBody,
) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.put(`tournaments/${tournament_id}/officials/${official_id}`, body),
  );
}

export async function deleteOfficial(tournament_id: number, official_id: number) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.delete(`tournaments/${tournament_id}/officials/${official_id}`),
  );
}

export async function setMatchOfficials(
  tournament_id: number,
  match_id: number,
  body: MatchOfficialsBody,
) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.put(`tournaments/${tournament_id}/matches/${match_id}/officials`, body),
  );
}

export async function assignBlock(tournament_id: number, body: BlockAssignmentBody) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post(`tournaments/${tournament_id}/officials/assign_block`, body),
  );
}

export async function createCourtHost(tournament_id: number, body: CourtHostBody) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post(`tournaments/${tournament_id}/court_hosts`, body),
  );
}

export async function deleteCourtHost(tournament_id: number, court_host_id: number) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.delete(`tournaments/${tournament_id}/court_hosts/${court_host_id}`),
  );
}

export async function downloadFeesCsv(tournament_id: number, language: string) {
  try {
    const response = await createAxios().get(`tournaments/${tournament_id}/officials_fees.csv`, {
      params: { language },
      responseType: 'blob',
    });
    const url = URL.createObjectURL(response.data);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'officials-fees.csv';
    link.click();
    URL.revokeObjectURL(url);
  } catch (error: any) {
    handleRequestError(error);
  }
}
