import { MatchWithDetails } from '@openapi';
import dayjs from 'dayjs';
import { formatStageItemInput } from './stage_item_input';
import { Translator } from './types';

export interface SchedulerSettings {
  eloThreshold: number;
  setEloThreshold: any;
  limit: number;
  setLimit: any;
  iterations: number;
  setIterations: any;
  onlyRecommended: string;
  setOnlyRecommended: any;
}

export function getMatchStartTime(match: MatchWithDetails) {
  return dayjs(match.start_time || '');
}

export function getMatchEndTime(match: MatchWithDetails) {
  return getMatchStartTime(match).add(match.duration_minutes + match.margin_minutes, 'minutes');
}

export function isMatchHappening(match: MatchWithDetails) {
  return getMatchStartTime(match) < dayjs() && getMatchEndTime(match) > dayjs();
}

export function isMatchInTheFutureOrPresent(match: MatchWithDetails) {
  return getMatchEndTime(match) > dayjs();
}

export function isMatchInTheFuture(match: MatchWithDetails) {
  return getMatchStartTime(match) > dayjs();
}

/**
 * A short name for a knockout match, e.g. "semifinale 1" or "kvartfinale 3": readable on
 * schedules instead of "Vinner av kamp Nr. 1 i Pulje A - Nr. 2 i Pulje B".
 */
export function knockoutMatchName(t: Translator, matchesLookup: any, matchId: number): string {
  const entry = matchesLookup[matchId];
  if (entry == null) return `#${matchId}`;
  const rounds = [...entry.stageItem.rounds].sort((a: any, b: any) => a.id - b.id);
  const roundIndex = rounds.findIndex((round: any) =>
    round.matches.some((m: MatchWithDetails) => m.id === matchId),
  );
  if (roundIndex < 0) return `#${matchId}`;
  const matches = [...rounds[roundIndex].matches].sort((a: any, b: any) => a.id - b.id);
  const number = matches.findIndex((m: MatchWithDetails) => m.id === matchId) + 1;
  const fromEnd = rounds.length - 1 - roundIndex;
  if (fromEnd === 0) return t('round_name_final');
  const name =
    fromEnd === 1
      ? t('round_name_semifinal')
      : fromEnd === 2
        ? t('round_name_quarterfinal')
        : t('round_name_round', { number: roundIndex + 1 });
  return matches.length > 1 ? `${name} ${number}` : name;
}

export function formatMatchInput1(
  t: Translator,
  stageItemsLookup: any,
  matchesLookup: any,
  match: MatchWithDetails,
): string {
  const formatted = formatStageItemInput(match.stage_item_input1, stageItemsLookup);
  if (formatted != null) return formatted;

  if (match.stage_item_input1_loser_from_match_id != null) {
    return t('loser_of_match', {
      match: knockoutMatchName(t, matchesLookup, match.stage_item_input1_loser_from_match_id),
    });
  }
  if (match.stage_item_input1_winner_from_match_id == null) {
    return t('empty_slot');
  }
  return t('winner_of_match', {
    match: knockoutMatchName(t, matchesLookup, match.stage_item_input1_winner_from_match_id),
  });
}

export function formatMatchInput2(
  t: Translator,
  stageItemsLookup: any,
  matchesLookup: any,
  match: MatchWithDetails,
): string {
  const formatted = formatStageItemInput(match.stage_item_input2, stageItemsLookup);
  if (formatted != null) return formatted;

  if (match.stage_item_input2_loser_from_match_id != null) {
    return t('loser_of_match', {
      match: knockoutMatchName(t, matchesLookup, match.stage_item_input2_loser_from_match_id),
    });
  }
  if (match.stage_item_input2_winner_from_match_id == null) {
    return t('empty_slot');
  }
  return t('winner_of_match', {
    match: knockoutMatchName(t, matchesLookup, match.stage_item_input2_winner_from_match_id),
  });
}

/**
 * The outcome of a played match: 1 or 2 when that team won (also by penalty shootout),
 * 0 for a draw, `null` when the match has not been played yet.
 */
export function getMatchOutcome(match: MatchWithDetails): 0 | 1 | 2 | null {
  if (!match.played) return null;
  if (match.stage_item_input1_score > match.stage_item_input2_score) return 1;
  if (match.stage_item_input1_score < match.stage_item_input2_score) return 2;

  const penalties1 = match.stage_item_input1_penalties;
  const penalties2 = match.stage_item_input2_penalties;
  if (
    match.result_type === 'PENALTIES' &&
    penalties1 != null &&
    penalties2 != null &&
    penalties1 !== penalties2
  ) {
    return penalties1 > penalties2 ? 1 : 2;
  }
  return 0;
}

/**
 * A short note about how the match was decided, e.g. "after extra time" or "4–3 on penalties".
 */
export function formatResultNote(t: Translator, match: MatchWithDetails): string | null {
  switch (match.result_type) {
    case 'EXTRA_TIME':
      return t('result_after_extra_time');
    case 'PENALTIES':
      return t('result_after_penalties', {
        score: `${match.stage_item_input1_penalties}–${match.stage_item_input2_penalties}`,
      });
    case 'WALKOVER':
      return t('result_walkover');
    default:
      return null;
  }
}

/**
 * A score was entered, but the match isn't marked as finished yet: it doesn't count in tables and
 * nobody advances until the final result is saved.
 */
export function isLiveScore(match: MatchWithDetails): boolean {
  return !match.played && (match.stage_item_input1_score > 0 || match.stage_item_input2_score > 0);
}
