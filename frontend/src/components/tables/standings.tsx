import { Table, Text } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import { PlayerScore } from '@components/info/player_score';
import { WinDistribution } from '@components/info/player_statistics';
import { EmptyTableInfo } from '@components/no_content/empty_table_info';
import { formatStageItemInput } from '@components/utils/stage_item_input';
import { StageItemInputFinal, StageItemWithRounds } from '@openapi';
import { WinDistributionTitle } from './players';
import { ThNotSortable } from './table';
import TableLayoutLarge from './table_large';

function formatGoalDifference(difference: number) {
  return difference > 0 ? `+${difference}` : `${difference}`;
}

export function StandingsTableForStageItem({
  teams_with_inputs,
  stageItem,
  fontSizeInPixels,
  stageItemsLookup,
  maxTeamsToDisplay,
}: {
  teams_with_inputs: StageItemInputFinal[];
  stageItem: StageItemWithRounds;
  fontSizeInPixels: number;
  stageItemsLookup: any;
  maxTeamsToDisplay: number;
}) {
  const { t } = useTranslation();
  const isSwiss = stageItem.type === 'SWISS';

  const minPoints = Math.min(...teams_with_inputs.map((input) => parseFloat(input.points)));
  const maxPoints = Math.max(...teams_with_inputs.map((input) => parseFloat(input.points)));

  // The backend determines the position, including the tiebreakers of the ranking
  const rows = [...teams_with_inputs]
    .sort(
      (p1: StageItemInputFinal, p2: StageItemInputFinal) =>
        (p1.position ?? Number.MAX_SAFE_INTEGER) - (p2.position ?? Number.MAX_SAFE_INTEGER) ||
        parseFloat(p2.points) - parseFloat(p1.points),
    )
    .slice(0, maxTeamsToDisplay)
    .map((team_with_input, index) => (
      <Table.Tr key={team_with_input.id}>
        <Table.Td style={{ width: '2rem' }}>{team_with_input.position ?? index + 1}</Table.Td>
        <Table.Td style={{ width: '20rem' }}>
          <Text truncate="end" lineClamp={1} inherit>
            {formatStageItemInput(team_with_input, stageItemsLookup)}
          </Text>
        </Table.Td>
        {isSwiss ? null : (
          <>
            <Table.Td visibleFrom="sm" style={{ minWidth: '6rem' }}>
              {team_with_input.goals_for}–{team_with_input.goals_against}
            </Table.Td>
            <Table.Td visibleFrom="sm" style={{ minWidth: '4rem' }}>
              {formatGoalDifference(team_with_input.goals_for - team_with_input.goals_against)}
            </Table.Td>
          </>
        )}
        <Table.Td style={{ minWidth: '6rem' }}>
          <Text truncate="end" lineClamp={1} inherit fw={700}>
            {parseFloat(team_with_input.points)}
          </Text>
        </Table.Td>
        {stageItem.type === 'SWISS' ? (
          <Table.Td style={{ minWidth: '10rem' }}>
            <PlayerScore
              score={parseFloat(team_with_input.points)}
              min_score={minPoints}
              max_score={maxPoints}
              decimals={0}
              fontSizeInPixels={fontSizeInPixels}
            />
          </Table.Td>
        ) : (
          <Table.Td style={{ minWidth: '10rem' }}>
            <WinDistribution
              wins={team_with_input.wins}
              draws={team_with_input.draws}
              losses={team_with_input.losses}
              fontSizeInPixels={fontSizeInPixels}
            />
          </Table.Td>
        )}
      </Table.Tr>
    ));

  if (rows.length < 1) return <EmptyTableInfo entity_name={t('teams_title')} />;

  return (
    <TableLayoutLarge display_mode="presentation">
      <Table.Thead>
        <Table.Tr>
          <ThNotSortable>#</ThNotSortable>
          <ThNotSortable>{t('name_table_header')}</ThNotSortable>
          {isSwiss ? (
            <>
              <ThNotSortable>{t('elo_score')}</ThNotSortable>
              <ThNotSortable>{t('elo_score')}</ThNotSortable>
            </>
          ) : (
            <>
              <ThNotSortable visibleFrom="sm">{t('goals_table_header')}</ThNotSortable>
              <ThNotSortable visibleFrom="sm">{t('goal_difference_table_header')}</ThNotSortable>
              <ThNotSortable>{t('points_table_header')}</ThNotSortable>
              <ThNotSortable>
                <WinDistributionTitle />
              </ThNotSortable>
            </>
          )}
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>{rows}</Table.Tbody>
    </TableLayoutLarge>
  );
}
