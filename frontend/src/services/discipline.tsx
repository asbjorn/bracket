import useSWR, { SWRResponse } from 'swr';

import {
  Category,
  DisciplineOverviewResponse,
  DisciplineSettingsBody,
  JuryDecisionBody,
  MatchCardBody,
  MatchCardResponse,
  StageWithStageItems,
} from '@openapi';
import { awaitRequestAndHandleError, createAxios } from './adapter';

const fetcher = (url: string) =>
  createAxios()
    .get(url)
    .then((res: { data: any }) => res.data);

// NFF: no cards or suspensions in children's football (12 and younger)
const YOUTH_FOOTBALL_MIN_AGE = 13;

/** Same rule as the backend: from 13 years (or no age) and only with public results. */
export function disciplineAllowed(category: Category | null | undefined) {
  if (category == null) return true;
  return (
    (category.age == null || category.age >= YOUTH_FOOTBALL_MIN_AGE) && category.results_public
  );
}

/** The class of the stage item a match belongs to. */
export function categoryOfStageItem(
  stages: StageWithStageItems[],
  categories: Category[],
  stageItemId: number,
): Category | null {
  const stage = stages.find((s) => s.stage_items.some((item) => item.id === stageItemId));
  return categories.find((c) => c.id === stage?.category_id) ?? null;
}

/** Cards, suspensions, settings and the jury's log (organiser only). */
export function getDiscipline(
  tournament_id: number | null,
): SWRResponse<DisciplineOverviewResponse> {
  return useSWR(tournament_id == null ? null : `tournaments/${tournament_id}/discipline`, fetcher);
}

export async function saveDisciplineSettings(tournament_id: number, body: DisciplineSettingsBody) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.put(`tournaments/${tournament_id}/discipline_settings`, body),
  );
}

export async function createCard(tournament_id: number, match_id: number, body: MatchCardBody) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post<MatchCardResponse>(`tournaments/${tournament_id}/matches/${match_id}/cards`, body),
  );
}

export async function deleteCard(tournament_id: number, card_id: number) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.delete(`tournaments/${tournament_id}/cards/${card_id}`),
  );
}

export async function createJuryDecision(tournament_id: number, body: JuryDecisionBody) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post(`tournaments/${tournament_id}/jury_decisions`, body),
  );
}

export async function deleteJuryDecision(tournament_id: number, decision_id: number) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.delete(`tournaments/${tournament_id}/jury_decisions/${decision_id}`),
  );
}

export async function createCardAtPitch(token: string, match_id: number, body: MatchCardBody) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post<MatchCardResponse>(`score/${token}/matches/${match_id}/cards`, body),
  );
}

export async function deleteCardAtPitch(token: string, card_id: number) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.delete(`score/${token}/cards/${card_id}`),
  );
}
