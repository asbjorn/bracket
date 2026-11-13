import { freeSlots, isGroupStage, teamIdsInStage } from '@components/utils/group_stage';
import { StageWithStageItems } from '@openapi';

export const PHASES = ['setup', 'draw', 'groups', 'playoffs', 'done'] as const;
export type Phase = (typeof PHASES)[number];

export interface ClassStatus {
  phase: Phase;
  groupStage: StageWithStageItems | null;
  // The knockout stage right after the groups, if the class has one
  playoffStage: StageWithStageItems | null;
  activeStage: StageWithStageItems | null;
  nextStage: StageWithStageItems | null;
  // Matches of the active stage
  played: number;
  total: number;
  teams: number;
  places: number;
  drawn: number;
}

export function stageMatches(stage: StageWithStageItems) {
  return stage.stage_items.flatMap((item) => item.rounds.flatMap((round) => round.matches));
}

/**
 * Where a class is on its way from setup to the prize ceremony, from its stages (in order) and
 * the number of teams that take part.
 */
export function getClassStatus(stages: StageWithStageItems[], teamCount: number): ClassStatus {
  const ordered = [...stages].sort((a, b) => a.id - b.id);
  const groupStage = ordered.find(isGroupStage) ?? null;
  const afterGroups = groupStage != null ? ordered.filter((s) => s.id > groupStage.id) : [];
  const playoffStage =
    afterGroups.find((s) => s.stage_items.some((i) => i.type === 'SINGLE_ELIMINATION')) ?? null;
  const activeIndex = ordered.findIndex((stage) => stage.is_active);
  const activeStage = activeIndex >= 0 ? ordered[activeIndex] : null;
  const nextStage = activeIndex >= 0 ? (ordered[activeIndex + 1] ?? null) : null;
  const matches = activeStage != null ? stageMatches(activeStage) : [];
  const played = matches.filter((match) => match.played).length;
  const drawn = groupStage != null ? teamIdsInStage(groupStage).size : 0;
  const places = groupStage != null ? drawn + freeSlots(groupStage) : 0;
  const anyPlayed = ordered.some((stage) => stageMatches(stage).some((match) => match.played));

  let phase: Phase;
  if (ordered.length < 1) phase = 'setup';
  else if (!anyPlayed && (drawn < teamCount || drawn < 1)) phase = 'draw';
  else if (activeStage != null && activeStage.id !== groupStage?.id && isKnockout(activeStage)) {
    phase = played === matches.length && nextStage == null ? 'done' : 'playoffs';
  } else if (nextStage == null && matches.length > 0 && played === matches.length) {
    phase = 'done';
  } else phase = 'groups';

  return {
    phase,
    groupStage,
    playoffStage,
    activeStage,
    nextStage,
    played,
    total: matches.length,
    teams: teamCount,
    places,
    drawn,
  };
}

function isKnockout(stage: StageWithStageItems) {
  return stage.stage_items.some((item) => item.type === 'SINGLE_ELIMINATION');
}
