import {
  CourtsResponse,
  GameFormat,
  ReplanBody,
  ReplanPreviewResponse,
  ScheduleProposalResponse,
} from '@openapi';
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
  split_into: number | null = null,
  part_format: GameFormat | null = null,
) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post(`tournaments/${tournament_id}/courts_multi`, {
      count,
      name_prefix,
      game_format,
      split_into,
      part_format,
    }),
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

export async function previewReplan(tournament_id: number, body: ReplanBody) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post<ReplanPreviewResponse>(`tournaments/${tournament_id}/schedule/replan/preview`, body),
  );
}

export async function applyReplan(tournament_id: number, body: ReplanBody) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post<ReplanPreviewResponse>(`tournaments/${tournament_id}/schedule/replan/apply`, body),
  );
}

export async function splitCourt(
  tournament_id: number,
  court_id: number,
  parts: number,
  game_format: GameFormat | null,
) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post<CourtsResponse>(`tournaments/${tournament_id}/courts/${court_id}/split`, {
      parts,
      game_format,
    }),
  );
}

/** Opening hours of a pitch; empty: the cup's playing hours. */
export async function saveCourtHours(
  tournament_id: number,
  court_id: number,
  time_windows: TimeWindowValue[],
) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.put(`tournaments/${tournament_id}/courts/${court_id}/time_windows`, { time_windows }),
  );
}

/** Days/hours of a class; empty: whenever the cup plays. */
export async function saveCategoryHours(
  tournament_id: number,
  category_id: number,
  time_windows: TimeWindowValue[],
) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.put(`tournaments/${tournament_id}/categories/${category_id}/time_windows`, {
      time_windows,
    }),
  );
}

/** Kick-off: a started match keeps its pitch and time when the schedule changes. */
export async function setMatchStarted(tournament_id: number, match_id: number, started: boolean) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.put(`tournaments/${tournament_id}/matches/${match_id}/started`, { started }),
  );
}
