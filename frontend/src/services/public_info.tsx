import useSWR, { SWRResponse } from 'swr';

import { Announcement, AnnouncementResponse, PublicNoticesResponse, RulesResponse } from '@openapi';
import { awaitRequestAndHandleError, createAxios, getBaseApiUrl } from './adapter';

const fetcher = (url: string) =>
  createAxios()
    .get(url)
    .then((res: { data: any }) => res.data);

/** The announcement and delays for the public pages; refreshed every 30 seconds. */
export function getPublicNotices(tournament_id: number | null): SWRResponse<PublicNoticesResponse> {
  return useSWR(
    tournament_id == null ? null : `tournaments/${tournament_id}/public_notices`,
    fetcher,
    { refreshInterval: 30_000 },
  );
}

export function getAnnouncement(tournament_id: number): SWRResponse<AnnouncementResponse> {
  return useSWR(`tournaments/${tournament_id}/announcement`, fetcher);
}

export function getRules(tournament_id: number | null): SWRResponse<RulesResponse> {
  return useSWR(tournament_id == null ? null : `tournaments/${tournament_id}/rules`, fetcher);
}

export async function saveAnnouncement(tournament_id: number, announcement: Announcement | null) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.put(`tournaments/${tournament_id}/announcement`, { announcement }),
  );
}

export async function saveRules(tournament_id: number, text: string) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.put(`tournaments/${tournament_id}/rules`, { text }),
  );
}

export function teamCalendarUrl(tournament_id: number, team_id: number) {
  return `${getBaseApiUrl()}/tournaments/${tournament_id}/teams/${team_id}/calendar.ics`;
}
