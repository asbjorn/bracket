import useSWR, { SWRResponse } from 'swr';

import {
  EmailLanguage,
  NotificationStatusResponse,
  NotificationsQueuedResponse,
  ScheduleNoticeResponse,
} from '@openapi';
import { awaitRequestAndHandleError, createAxios } from './adapter';

export function getNotificationStatus(
  tournament_id: number,
): SWRResponse<NotificationStatusResponse> {
  return useSWR(`tournaments/${tournament_id}/notifications`, (url: string) =>
    createAxios()
      .get(url)
      .then((res) => res.data),
  );
}

export async function saveEmailLanguage(tournament_id: number, language: EmailLanguage) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.put(`tournaments/${tournament_id}/notification_settings`, { language }),
  );
}

export async function sendAnnouncementEmail(tournament_id: number) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post<NotificationsQueuedResponse>(
      `tournaments/${tournament_id}/notifications/announcement`,
    ),
  );
}

export async function sendScheduleNotices(tournament_id: number, dry_run: boolean) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post<ScheduleNoticeResponse>(
      `tournaments/${tournament_id}/notifications/schedule?dry_run=${dry_run}`,
    ),
  );
}
