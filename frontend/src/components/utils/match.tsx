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

export function formatMatchInput1(
  t: Translator,
  stageItemsLookup: any,
  matchesLookup: any,
  match: MatchWithDetails,
): string {
  const formatted = formatStageItemInput(match.stage_item_input1, stageItemsLookup);
  if (formatted != null) return formatted;

  if (match.stage_item_input1_loser_from_match_id != null) {
    const loser = matchesLookup[match.stage_item_input1_loser_from_match_id].match;
    const loser_1 = formatMatchInput1(t, stageItemsLookup, matchesLookup, loser);
    const loser_2 = formatMatchInput2(t, stageItemsLookup, matchesLookup, loser);
    return t('loser_of_match', { match: `${loser_1} - ${loser_2}` });
  }
  if (match.stage_item_input1_winner_from_match_id == null) {
    return t('empty_slot');
  }
  const winner = matchesLookup[match.stage_item_input1_winner_from_match_id].match;
  const match_1 = formatMatchInput1(t, stageItemsLookup, matchesLookup, winner);
  const match_2 = formatMatchInput2(t, stageItemsLookup, matchesLookup, winner);
  return t('winner_of_match', { match: `${match_1} - ${match_2}` });
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
    const loser = matchesLookup[match.stage_item_input2_loser_from_match_id].match;
    const loser_1 = formatMatchInput1(t, stageItemsLookup, matchesLookup, loser);
    const loser_2 = formatMatchInput2(t, stageItemsLookup, matchesLookup, loser);
    return t('loser_of_match', { match: `${loser_1} - ${loser_2}` });
  }
  if (match.stage_item_input2_winner_from_match_id == null) {
    return t('empty_slot');
  }
  const winner = matchesLookup[match.stage_item_input2_winner_from_match_id].match;
  const match_1 = formatMatchInput1(t, stageItemsLookup, matchesLookup, winner);
  const match_2 = formatMatchInput2(t, stageItemsLookup, matchesLookup, winner);
  return t('winner_of_match', { match: `${match_1} - ${match_2}` });
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
