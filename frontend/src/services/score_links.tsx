import useSWR, { SWRResponse } from 'swr';

import {
  MatchDayNoticeBody,
  MatchDayNoticesResponse,
  ScoreEntryBody,
  ScoreEntryViewResponse,
  ScoreLinkBody,
  ScoreLinkCreatedResponse,
  ScoreLinksResponse,
} from '@openapi';
import { awaitRequestAndHandleError, createAxios } from './adapter';

const fetcher = (url: string) =>
  createAxios()
    .get(url)
    .then((res: { data: any }) => res.data);

export function scoreLinkUrl(token: string) {
  return `${window.location.origin}/score/${token}`;
}

export function getScoreLinks(tournament_id: number): SWRResponse<ScoreLinksResponse> {
  return useSWR(`tournaments/${tournament_id}/score_links`, fetcher);
}

export async function createScoreLink(tournament_id: number, body: ScoreLinkBody) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post<ScoreLinkCreatedResponse>(`tournaments/${tournament_id}/score_links`, body),
  );
}

export async function revokeScoreLink(tournament_id: number, score_link_id: number) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post(`tournaments/${tournament_id}/score_links/${score_link_id}/revoke`),
  );
}

/** Reports from the pitches; refreshed often, they matter on match day. */
export function getNotices(tournament_id: number): SWRResponse<MatchDayNoticesResponse> {
  return useSWR(`tournaments/${tournament_id}/notices`, fetcher, { refreshInterval: 20_000 });
}

export async function resolveNotice(tournament_id: number, notice_id: number) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post(`tournaments/${tournament_id}/notices/${notice_id}/resolve`),
  );
}

// Without an account: the token in the link is the key

export function getScoreEntry(token: string): SWRResponse<ScoreEntryViewResponse> {
  return useSWR(`score/${token}`, fetcher, {
    refreshInterval: 30_000,
    shouldRetryOnError: false,
  });
}

export async function enterResult(token: string, match_id: number, body: ScoreEntryBody) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.put(`score/${token}/matches/${match_id}`, body),
  );
}

export async function reportFromPitch(token: string, body: MatchDayNoticeBody) {
  return awaitRequestAndHandleError(async (axios) => axios.post(`score/${token}/notices`, body));
}
