import { Text } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import classes from '@components/builder/stages.module.css';
import { formatMatchInput1, formatMatchInput2, getMatchOutcome } from '@components/utils/match';
import { Translator } from '@components/utils/types';
import { MatchWithDetails, MatchWithDetailsDefinitive, StageItemWithRounds } from '@openapi';

type Match = MatchWithDetails | MatchWithDetailsDefinitive;

function roundTitle(t: Translator, index: number, roundCount: number) {
  const fromEnd = roundCount - 1 - index;
  if (fromEnd === 0) return t('round_name_final');
  if (fromEnd === 1) return t('round_name_semifinal');
  if (fromEnd === 2) return t('round_name_quarterfinal');
  return t('round_name_round', { number: index + 1 });
}

function teamOf(input: Match['stage_item_input1']): number | null {
  return input != null && 'team' in input && input.team != null ? input.team.id : null;
}

/** The group a side of a match comes from ("1st of group A"), for linking it to that group. */
function groupOf(input: Match['stage_item_input1']): number | null {
  if (input == null || !('winner_from_stage_item_id' in input)) return null;
  return input.winner_from_stage_item_id ?? null;
}

function isBronzeFinal(match: Match) {
  return (
    match.stage_item_input1_loser_from_match_id != null ||
    match.stage_item_input2_loser_from_match_id != null
  );
}

function MatchBox({
  match,
  name,
  fed,
  stageItemsLookup,
  matchesLookup,
  hoveredGroupId,
  onHoverGroup,
  highlightTeamId,
}: {
  match: Match;
  name?: string;
  fed: boolean;
  stageItemsLookup: any;
  matchesLookup: any;
  hoveredGroupId: number | null;
  onHoverGroup: (groupId: number | null) => void;
  highlightTeamId: number | null;
}) {
  const { t } = useTranslation();
  const outcome = getMatchOutcome(match as MatchWithDetails);
  const sides = [
    {
      label: formatMatchInput1(t, stageItemsLookup, matchesLookup, match as MatchWithDetails),
      score: match.stage_item_input1_score,
      group: groupOf(match.stage_item_input1),
      team: teamOf(match.stage_item_input1),
      winner: outcome === 1,
    },
    {
      label: formatMatchInput2(t, stageItemsLookup, matchesLookup, match as MatchWithDetails),
      score: match.stage_item_input2_score,
      group: groupOf(match.stage_item_input2),
      team: teamOf(match.stage_item_input2),
      winner: outcome === 2,
    },
  ];
  return (
    <div className={classes.match} data-fed={fed}>
      {name != null ? <div className={classes.matchName}>{name}</div> : null}
      {sides.map((side, index) => (
        <div
          key={index}
          className={classes.side}
          data-winner={side.winner}
          data-linked={side.group != null && side.group === hoveredGroupId}
          data-followed={side.team != null && side.team === highlightTeamId}
          onMouseEnter={() => onHoverGroup(side.group)}
          onMouseLeave={() => onHoverGroup(null)}
        >
          <span className={classes.sideName} title={side.label}>
            {side.label}
          </span>
          {match.played ? <b>{side.score}</b> : null}
        </div>
      ))}
    </div>
  );
}

/**
 * A knockout stage item drawn as a bracket: one column per round, lines joining every two
 * matches to the match they feed, and the bronze final under the final.
 */
export default function KnockoutBracket({
  stageItem,
  stageItemsLookup,
  matchesLookup,
  hoveredGroupId = null,
  onHoverGroup = () => {},
  highlightTeamId = null,
}: {
  stageItem: StageItemWithRounds;
  stageItemsLookup: any;
  matchesLookup: any;
  hoveredGroupId?: number | null;
  onHoverGroup?: (groupId: number | null) => void;
  // The team a visitor follows
  highlightTeamId?: number | null;
}) {
  const { t } = useTranslation();
  const rounds = [...stageItem.rounds]
    .sort((a, b) => a.id - b.id)
    .map((round) => [...round.matches].sort((a, b) => a.id - b.id));
  if (rounds.length < 1 || rounds.every((matches) => matches.length < 1)) {
    return (
      <Text size="sm" c="dimmed">
        {t('bracket_no_matches')}
      </Text>
    );
  }
  const lastRound = rounds[rounds.length - 1];
  const bronze = lastRound.find(isBronzeFinal) ?? null;
  const columns = rounds.map((matches, index) =>
    index === rounds.length - 1 ? matches.filter((match) => !isBronzeFinal(match)) : matches,
  );
  // Lines only where every two matches feed one match (rounds after byes can differ)
  const connects = columns.map(
    (matches, index) =>
      index < columns.length - 1 && matches.length === 2 * columns[index + 1].length,
  );

  const box = (match: Match, index: number, name?: string) => (
    <MatchBox
      key={match.id}
      match={match}
      name={name}
      fed={index > 0 && connects[index - 1]}
      stageItemsLookup={stageItemsLookup}
      matchesLookup={matchesLookup}
      hoveredGroupId={hoveredGroupId}
      onHoverGroup={onHoverGroup}
      highlightTeamId={highlightTeamId}
    />
  );

  return (
    <div className={classes.bracketScroll}>
      <div className={classes.bracket} style={{ ['--rounds' as string]: columns.length }}>
        {columns.map((_, index) => (
          <div key={index} className={classes.roundTitle}>
            {roundTitle(t, index, columns.length)}
          </div>
        ))}
        {columns.map((matches, index) => (
          <div key={index} className={classes.round}>
            {connects[index]
              ? Array.from({ length: matches.length / 2 }, (_, pair) => (
                  <div key={pair} className={classes.pair} data-connect>
                    {box(matches[2 * pair], index)}
                    {box(matches[2 * pair + 1], index)}
                  </div>
                ))
              : matches.map((match) => (
                  <div key={match.id} className={classes.pair}>
                    {box(match, index)}
                  </div>
                ))}
            {index === columns.length - 1 && bronze != null ? (
              <div className={classes.bronze}>{box(bronze, 0, t('bracket_bronze_final'))}</div>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}
