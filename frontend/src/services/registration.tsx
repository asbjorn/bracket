import useSWR, { SWRResponse } from 'swr';

import {
  EntryFeeBody,
  PublicRegistrationBody,
  PublicRegistrationClassesResponse,
  PublicRegistrationResponse,
  RegistrationSettingsBody,
  RegistrationUpdateBody,
  RegistrationsResponse,
} from '@openapi';
import { awaitRequestAndHandleError, createAxios, handleRequestError } from './adapter';

const fetcher = (url: string) =>
  createAxios()
    .get(url)
    .then((res: { data: any }) => res.data);

/** Classes open for sign-up now (public). */
export function getOpenClasses(
  tournament_id: number | null,
): SWRResponse<PublicRegistrationClassesResponse> {
  return useSWR(
    tournament_id == null ? null : `tournaments/${tournament_id}/registration/classes`,
    fetcher,
  );
}

export async function registerTeam(tournament_id: number, body: PublicRegistrationBody) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post<PublicRegistrationResponse>(`tournaments/${tournament_id}/registration`, body),
  );
}

/** All teams with their registration and contact details (organiser only). */
export function getRegistrations(tournament_id: number): SWRResponse<RegistrationsResponse> {
  return useSWR(`tournaments/${tournament_id}/registrations`, fetcher);
}

export async function updateRegistration(
  tournament_id: number,
  team_id: number,
  body: RegistrationUpdateBody,
) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.put(`tournaments/${tournament_id}/registrations/${team_id}`, body),
  );
}

export async function promoteFromWaitlist(tournament_id: number, category_id: number) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post(`tournaments/${tournament_id}/categories/${category_id}/waitlist/promote`),
  );
}

export async function saveRegistrationSettings(
  tournament_id: number,
  category_id: number,
  body: RegistrationSettingsBody,
) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.put(`tournaments/${tournament_id}/categories/${category_id}/registration`, body),
  );
}

export async function saveEntryFees(tournament_id: number, body: EntryFeeBody) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.put(`tournaments/${tournament_id}/entry_fees`, body),
  );
}

/** Downloads the registrations as a CSV file for Excel. */
export async function downloadRegistrationsCsv(tournament_id: number, language: string) {
  try {
    const response = await createAxios().get(`tournaments/${tournament_id}/registrations.csv`, {
      params: { language },
      responseType: 'blob',
    });
    const url = URL.createObjectURL(response.data);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'registrations.csv';
    link.click();
    URL.revokeObjectURL(url);
  } catch (error: any) {
    handleRequestError(error);
  }
}

export async function downloadFinalResultsCsv(tournament_id: number, language: string) {
  try {
    const response = await createAxios().get(`tournaments/${tournament_id}/final_results.csv`, {
      params: { language },
      responseType: 'blob',
    });
    const url = URL.createObjectURL(response.data);
    const link = document.createElement('a');
    link.href = url;
    link.download = language === 'nb' ? 'resultater.csv' : 'results.csv';
    link.click();
    URL.revokeObjectURL(url);
  } catch (error: any) {
    handleRequestError(error);
  }
}

export async function saveCeremonySettings(tournament_id: number, ceremony_offset_minutes: number) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.put(`tournaments/${tournament_id}/ceremony_settings`, { ceremony_offset_minutes }),
  );
}
