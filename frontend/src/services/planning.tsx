import { GameFormat, ScheduleProposalResponse } from '@openapi';
import { awaitRequestAndHandleError } from './adapter';

export interface TimeWindowValue {
  start_time: string;
  end_time: string;
}

export async function saveTimeWindows(tournament_id: number, time_windows: TimeWindowValue[]) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.put(`tournaments/${tournament_id}/time_windows`, { time_windows }),
  );
}

export async function createCourts(
  tournament_id: number,
  count: number,
  name_prefix: string,
  game_format: GameFormat | null,
) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post(`tournaments/${tournament_id}/courts_multi`, { count, name_prefix, game_format }),
  );
}

export async function proposeSchedule(tournament_id: number) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post<ScheduleProposalResponse>(`tournaments/${tournament_id}/schedule/propose`),
  );
}

export async function applySchedule(tournament_id: number) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post<ScheduleProposalResponse>(`tournaments/${tournament_id}/schedule/apply`),
  );
}
