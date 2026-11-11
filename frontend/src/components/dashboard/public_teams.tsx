import { Category, MatchWithDetails, StageWithStageItems, Team } from '@openapi';

export interface PublicTeam {
  team: Team;
  category: Category | null;
}

/** The teams placed in a stage, with their class; from the public stages data. */
export function getPublicTeams(
  stages: StageWithStageItems[],
  categories: Category[],
): PublicTeam[] {
  const byId = new Map<number, PublicTeam>();
  stages.forEach((stage) =>
    stage.stage_items.forEach((item) =>
      item.inputs.forEach((input) => {
        if ('team' in input && input.team != null && !byId.has(input.team.id)) {
          byId.set(input.team.id, {
            team: input.team,
            category: categories.find((c) => c.id === stage.category_id) ?? null,
          });
        }
      }),
    ),
  );
  return [...byId.values()].sort((a, b) => a.team.name.localeCompare(b.team.name));
}

export function teamIdsOfMatch(match: MatchWithDetails): number[] {
  return [match.stage_item_input1, match.stage_item_input2].flatMap((input) =>
    input != null && 'team' in input && input.team != null ? [input.team.id] : [],
  );
}

/** Case and accent insensitive search, e.g. "asane" finds "Åsane". */
export function normalizeForSearch(text: string) {
  return text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[æÆ]/g, 'ae')
    .replace(/[øØ]/g, 'o')
    .toLowerCase();
}

/** The first match of a team that hasn't been played yet, in order of time. */
export function nextMatchOf(matches: MatchWithDetails[]): MatchWithDetails | null {
  return (
    matches
      .filter((match) => !match.played && match.start_time != null)
      .sort((a, b) => (a.start_time ?? '').localeCompare(b.start_time ?? ''))[0] ?? null
  );
}
