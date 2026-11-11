import {
  StageItemInputBestOf,
  StageItemInputEmpty,
  StageItemInputFinal,
  StageItemInputOptionFinal,
  StageItemInputOptionTentative,
  StageItemInputTentative,
} from '@openapi';
import i18n from '../../../i18n';
import { assert_not_none } from './assert';

export type StageItemInput =
  | StageItemInputTentative
  | StageItemInputBestOf
  | StageItemInputFinal
  | StageItemInputEmpty;
export type StageItemInputOption = StageItemInputOptionTentative | StageItemInputOptionFinal;

export interface StageItemInputChoice {
  value: string;
  label: string;
  team_id: number | null;
  winner_from_stage_item_id: number | null;
  winner_position: number | null;
  already_taken: boolean;
}

/**
 * E.g. "#2 of Group A" or "Nr. 2 i Pulje A".
 */
export function formatStageItemInputTentative(
  stage_item_input: StageItemInputTentative | StageItemInputOptionTentative,
  stageItemsLookup: any,
) {
  return i18n.t('placing_of_group', {
    placing: assert_not_none(stage_item_input.winner_position),
    group: stageItemsLookup[assert_not_none(stage_item_input.winner_from_stage_item_id)].name,
  });
}

/**
 * E.g. "Best #3 (1)" for the best third placed team across all groups.
 */
export function formatStageItemInputBestOf(stage_item_input: StageItemInputBestOf) {
  return i18n.t('best_of_placing', {
    rank: stage_item_input.best_rank,
    placing: stage_item_input.winner_position,
  });
}

export function formatStageItemInput(
  stage_item_input: StageItemInput | null,
  stageItemsLookup: any,
) {
  if (stage_item_input == null) return null;
  if ('team' in stage_item_input) return stage_item_input.team.name;
  if (stage_item_input.best_from_stage_id != null) {
    return formatStageItemInputBestOf(stage_item_input as StageItemInputBestOf);
  }
  if (stage_item_input.winner_from_stage_item_id != null) {
    return formatStageItemInputTentative(
      stage_item_input as StageItemInputTentative,
      stageItemsLookup,
    );
  }
  return null;
}
