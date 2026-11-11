import { Alert, Container, Group, Stack, Text } from '@mantine/core';
import { AiOutlineHourglass } from '@react-icons/all-files/ai/AiOutlineHourglass';
import { IconInfoCircle } from '@tabler/icons-react';
import React from 'react';
import { useTranslation } from 'react-i18next';
import { SWRResponse } from 'swr';

import { DashboardFooter } from '@components/dashboard/footer';
import { DoubleHeader, getTournamentHeadTitle } from '@components/dashboard/layout';
import { NoContent } from '@components/no_content/empty_table_info';
import { PrintButton } from '@components/print/print_button';
import { StandingsTableForStageItem } from '@components/tables/standings';
import {
  CategoryFilterSelect,
  getStageItemCategoryLookup,
  getStageItemIdsWithHiddenResults,
  stageItemClassNames,
  useCategoryFilter,
} from '@components/utils/category';
import { formatMatchInput1, formatMatchInput2, knockoutMatchName } from '@components/utils/match';
import { TableSkeletonTwoColumns } from '@components/utils/skeletons';
import { capitalize, responseIsValid, setTitle } from '@components/utils/util';
import { Category, StageItemWithRounds, StagesWithStageItemsResponse } from '@openapi';
import { getCategories, getStagesLive } from '@services/adapter';
import { getTournamentResponseByEndpointName } from '@services/dashboard';
import { getMatchLookup, getStageItemLookup, getStageItemTeamsLookup } from '@services/lookups';

/** A knockout playoff as its matches, round by round ("Semifinale 1: A – B 2–1"). */
function KnockoutMatches({
  stageItem,
  stageItemsLookup,
  matchesLookup,
}: {
  stageItem: StageItemWithRounds;
  stageItemsLookup: any;
  matchesLookup: any;
}) {
  const { t } = useTranslation();
  const matches = [...stageItem.rounds]
    .sort((a, b) => a.id - b.id)
    .flatMap((round) => [...round.matches].sort((a, b) => a.id - b.id));
  return (
    <Stack gap={4}>
      {matches.map((match) => (
        <Group key={match.id} justify="space-between" wrap="nowrap" gap="xs">
          <Text inherit size="sm" c="dimmed" w="9rem" style={{ flexShrink: 0 }}>
            {capitalize(knockoutMatchName(t, matchesLookup, match.id))}
          </Text>
          <Text inherit style={{ flex: 1, minWidth: 0 }} truncate>
            {formatMatchInput1(t, stageItemsLookup, matchesLookup, match)} –{' '}
            {formatMatchInput2(t, stageItemsLookup, matchesLookup, match)}
          </Text>
          <Text inherit fw={700} style={{ flexShrink: 0 }}>
            {match.played
              ? `${match.stage_item_input1_score}–${match.stage_item_input2_score}`
              : ''}
          </Text>
        </Group>
      ))}
    </Stack>
  );
}

export function StandingsContent({
  swrStagesResponse,
  categories,
  filterCategoryId,
  fontSizeInPixels,
  maxTeamsToDisplay,
}: {
  swrStagesResponse: SWRResponse<StagesWithStageItemsResponse>;
  categories: Category[];
  // `undefined`: all classes
  filterCategoryId: number | null | undefined;
  fontSizeInPixels: number;
  maxTeamsToDisplay: number;
}) {
  const { t } = useTranslation();

  const stageItemsLookup = getStageItemLookup(swrStagesResponse);
  const stageItemTeamLookup = responseIsValid(swrStagesResponse)
    ? getStageItemTeamsLookup(swrStagesResponse)
    : {};
  const stages = swrStagesResponse.data?.data ?? [];
  const stageItemCategories = getStageItemCategoryLookup(stages);
  const classNames = stageItemClassNames(stages, categories);
  const matchesLookup = responseIsValid(swrStagesResponse) ? getMatchLookup(swrStagesResponse) : {};
  const hiddenStageItemIds = getStageItemIdsWithHiddenResults(stages, categories);

  const stageItemIds = Object.keys(stageItemTeamLookup)
    .filter((stageItemId) => stageItemsLookup[stageItemId] != null)
    .filter(
      (stageItemId) =>
        filterCategoryId === undefined ||
        stageItemCategories[Number(stageItemId)] === filterCategoryId,
    );
  // NFF children's football: no tables for classes with hidden results
  const someTablesHidden = stageItemIds.some((id) => hiddenStageItemIds.has(Number(id)));
  const hiddenTablesAlert = someTablesHidden ? (
    <Alert color="gray" icon={<IconInfoCircle />} mt="md">
      {t('standings_hidden_alert')}
    </Alert>
  ) : null;

  // Grouped per class, groups before playoffs; titles like "J13 · Pulje A"
  const title = (stageItemId: string) =>
    [classNames[Number(stageItemId)], stageItemsLookup[stageItemId].name]
      .filter(Boolean)
      .join(' · ');
  const isKnockout = (stageItemId: string) =>
    stageItemsLookup[stageItemId].type === 'SINGLE_ELIMINATION';
  const rows = stageItemIds
    .filter((stageItemId) => !hiddenStageItemIds.has(Number(stageItemId)))
    .sort((si1: any, si2: any) =>
      `${classNames[si1] ?? ''}${isKnockout(si1) ? 1 : 0}${stageItemsLookup[si1].name}`.localeCompare(
        `${classNames[si2] ?? ''}${isKnockout(si2) ? 1 : 0}${stageItemsLookup[si2].name}`,
      ),
    )
    .map((stageItemId) => (
      <div key={stageItemId}>
        <Text size="xl" mt="md" mb="xs" inherit fw={600}>
          {title(stageItemId)}
        </Text>
        {isKnockout(stageItemId) ? (
          <KnockoutMatches
            stageItem={stageItemsLookup[stageItemId]}
            stageItemsLookup={stageItemsLookup}
            matchesLookup={matchesLookup}
          />
        ) : (
          <StandingsTableForStageItem
            teams_with_inputs={stageItemTeamLookup[stageItemId]}
            stageItem={stageItemsLookup[stageItemId]}
            stageItemsLookup={stageItemsLookup}
            fontSizeInPixels={fontSizeInPixels}
            maxTeamsToDisplay={maxTeamsToDisplay}
          />
        )}
      </div>
    ));

  if (rows.length < 1) {
    return (
      hiddenTablesAlert ?? (
        <NoContent
          title={`${t('could_not_find_any_alert')} ${t('teams_title')}`}
          description=""
          icon={<AiOutlineHourglass />}
        />
      )
    );
  }
  return (
    <>
      {rows}
      {hiddenTablesAlert}
    </>
  );
}

export default function DashboardStandingsPage() {
  const tournamentDataFull = getTournamentResponseByEndpointName();
  const tournamentValid = !React.isValidElement(tournamentDataFull);

  const swrStagesResponse = getStagesLive(tournamentValid ? tournamentDataFull.id : null);
  const categories = getCategories(tournamentValid ? tournamentDataFull.id : null).data?.data ?? [];
  const { filterValue, setFilterValue, filterCategoryId } = useCategoryFilter(categories);

  if (!tournamentValid) {
    return tournamentDataFull;
  }

  setTitle(getTournamentHeadTitle(tournamentDataFull));

  if (swrStagesResponse.isLoading) {
    return <TableSkeletonTwoColumns />;
  }

  return (
    <>
      <DoubleHeader tournamentData={tournamentDataFull} />
      <Container mt="1rem" px="0rem">
        <Container style={{ width: '100%' }} px="sm">
          <Stack gap={0}>
            <Group align="end" className="no-print">
              <div style={{ flex: 1 }}>
                <CategoryFilterSelect
                  categories={categories}
                  value={filterValue}
                  setValue={setFilterValue}
                />
              </div>
              <PrintButton />
            </Group>
            <StandingsContent
              swrStagesResponse={swrStagesResponse}
              categories={categories}
              filterCategoryId={filterCategoryId}
              fontSizeInPixels={16}
              maxTeamsToDisplay={100}
            />
          </Stack>
        </Container>
      </Container>
      <DashboardFooter />
    </>
  );
}
