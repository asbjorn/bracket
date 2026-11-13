import { Alert, Container, Group, Stack, Text } from '@mantine/core';
import { AiOutlineHourglass } from '@react-icons/all-files/ai/AiOutlineHourglass';
import { IconInfoCircle } from '@tabler/icons-react';
import React from 'react';
import { useTranslation } from 'react-i18next';
import { SWRResponse } from 'swr';

import KnockoutBracket from '@components/brackets/knockout_bracket';
import { DashboardFooter } from '@components/dashboard/footer';
import { FollowedTeamCard, useFollowedTeam } from '@components/dashboard/follow_team';
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
import { TableSkeletonTwoColumns } from '@components/utils/skeletons';
import { responseIsValid, setTitle } from '@components/utils/util';
import { Category, StagesWithStageItemsResponse } from '@openapi';
import { getCategories, getStagesLive } from '@services/adapter';
import { getTournamentResponseByEndpointName } from '@services/dashboard';
import { getMatchLookup, getStageItemLookup, getStageItemTeamsLookup } from '@services/lookups';

export function StandingsContent({
  swrStagesResponse,
  categories,
  filterCategoryId,
  fontSizeInPixels,
  maxTeamsToDisplay,
  followedTeamId = null,
}: {
  swrStagesResponse: SWRResponse<StagesWithStageItemsResponse>;
  categories: Category[];
  // `undefined`: all classes
  filterCategoryId: number | null | undefined;
  fontSizeInPixels: number;
  maxTeamsToDisplay: number;
  // The team a visitor follows, highlighted in tables and brackets
  followedTeamId?: number | null;
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
          <KnockoutBracket
            stageItem={stageItemsLookup[stageItemId]}
            stageItemsLookup={stageItemsLookup}
            matchesLookup={matchesLookup}
            highlightTeamId={followedTeamId}
          />
        ) : (
          <StandingsTableForStageItem
            teams_with_inputs={stageItemTeamLookup[stageItemId]}
            stageItem={stageItemsLookup[stageItemId]}
            stageItemsLookup={stageItemsLookup}
            fontSizeInPixels={fontSizeInPixels}
            maxTeamsToDisplay={maxTeamsToDisplay}
            highlightTeamId={followedTeamId}
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
  const [followedTeamId] = useFollowedTeam(tournamentValid ? tournamentDataFull.id : null);

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
            <FollowedTeamCard
              tournamentId={tournamentDataFull.id}
              endpoint={tournamentDataFull.dashboard_endpoint}
              stages={swrStagesResponse.data?.data ?? []}
              categories={categories}
              matchesLookup={
                responseIsValid(swrStagesResponse) ? getMatchLookup(swrStagesResponse) : {}
              }
              stageItemsLookup={getStageItemLookup(swrStagesResponse)}
            />
            <Group align="end" className="no-print" mt="sm">
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
              followedTeamId={followedTeamId}
            />
          </Stack>
        </Container>
      </Container>
      <DashboardFooter />
    </>
  );
}
