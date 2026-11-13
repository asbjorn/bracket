import { FullTeamWithPlayers, StageWithStageItems } from '@openapi';

const GROUP_TYPES = new Set(['ROUND_ROBIN', 'SWISS']);

/** A stage of groups: teams are drawn into it (as opposed to playoffs filled by placings). */
export function isGroupStage(stage: StageWithStageItems) {
  return (
    stage.stage_items.length > 0 && stage.stage_items.every((item) => GROUP_TYPES.has(item.type))
  );
}

/** The teams that are already in a group of the stage. */
export function teamIdsInStage(stage: StageWithStageItems) {
  return new Set(
    stage.stage_items.flatMap((item) =>
      item.inputs.flatMap((input) =>
        'team' in input && input.team != null ? [input.team.id] : [],
      ),
    ),
  );
}

/** Places in the groups that have no team yet (and aren't filled from another stage). */
export function freeSlots(stage: StageWithStageItems) {
  return stage.stage_items
    .flatMap((item) => item.inputs)
    .filter(
      (input) =>
        input.team_id == null && input.winner_from_stage_item_id == null && input.best_rank == null,
    ).length;
}

/** The first group stage of a class: the one the teams are drawn into. */
export function firstGroupStageOfClass(stages: StageWithStageItems[], categoryId: number) {
  return (
    [...stages]
      .sort((a, b) => a.id - b.id)
      .find((stage) => stage.category_id === categoryId && isGroupStage(stage)) ?? null
  );
}

/** Teams that take part in the draw: withdrawn teams don't. */
export function teamsToPlace(teams: FullTeamWithPlayers[], categoryId: number | null) {
  return teams.filter((team) => team.category_id === categoryId && !team.withdrawn);
}
