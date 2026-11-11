import { GameFormat } from '@openapi';

export interface ClassPreset {
  game_format: GameFormat;
  duration_minutes: number;
  margin_minutes: number;
}

/**
 * Suggested cup settings for an age class. Game formats follow the NFF ("spilleformer"):
 * 3v3 for 6-7, 5v5 for 8-9, 7v7 for 10-11, 9v9 for 12-13 and 11v11 from 14. Cup matches are
 * much shorter than league matches; these lengths are only a starting point.
 */
export function nffPreset(age: number): ClassPreset {
  if (age <= 7) return { game_format: '3v3', duration_minutes: 8, margin_minutes: 2 };
  if (age <= 9) return { game_format: '5v5', duration_minutes: 10, margin_minutes: 2 };
  if (age <= 11) return { game_format: '7v7', duration_minutes: 12, margin_minutes: 3 };
  if (age <= 13) return { game_format: '9v9', duration_minutes: 15, margin_minutes: 3 };
  return { game_format: '11v11', duration_minutes: 20, margin_minutes: 5 };
}

/**
 * Rest between two matches of a team: at least one match plus its break, so children never
 * play back-to-back (AreaCopa).
 */
export function defaultRestMinutes(age: number): number {
  const preset = nffPreset(age);
  return preset.duration_minutes + preset.margin_minutes;
}

/** Like the backend (max_matches_per_day_for_age): the limit when a class doesn't set its own. */
export function defaultMaxMatchesPerDay(age: number | null): number | null {
  if (age == null) return null;
  if (age <= 9) return 6;
  if (age <= 13) return 5;
  if (age <= 16) return 4;
  return 3;
}
