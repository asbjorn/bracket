import { Grid, Select, Title } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import TeamCreateModal from '@components/modals/team_create_modal';
import { getTableState, tableStateToPagination } from '@components/tables/table';
import TeamsTable from '@components/tables/teams';
import { CategoryFilterSelect, useCategoryFilter } from '@components/utils/category';
import { capitalize, getTournamentIdFromRouter, responseIsValid } from '@components/utils/util';
import { FullTeamWithPlayers, StageItemWithRounds } from '@openapi';
import TournamentLayout from '@pages/tournaments/_tournament_layout';
import { getCategories, getStages, getTeamsPaginated } from '@services/adapter';
import { getStageItemList, getStageItemTeamIdsLookup } from '@services/lookups';

function StageItemSelect({
  groupStageItems,
  setFilteredStageItemId,
}: {
  groupStageItems: any;
  setFilteredStageItemId: any;
}) {
  const { t } = useTranslation();
  if (groupStageItems == null) return null;
  const data = groupStageItems.map(([stage_item]: [StageItemWithRounds]) => ({
    value: `${stage_item.id}`,
    label: `${stage_item.name}`,
  }));
  return (
    <Select
      data={data}
      label={t('filter_stage_item_label')}
      placeholder={t('filter_stage_item_placeholder')}
      searchable
      limit={25}
      onChange={setFilteredStageItemId}
    />
  );
}

export default function TeamsPage() {
  const tableState = getTableState('name');
  const { t } = useTranslation();
  const [filteredStageItemId, setFilteredStageItemId] = useState(null);
  const { tournamentData } = getTournamentIdFromRouter();
  const categories = getCategories(tournamentData.id).data?.data ?? [];
  const { filterValue, setFilterValue, filterCategoryId } = useCategoryFilter(categories);
  // The API can only filter on a class, not on "no class"
  const filteredCategoryId = filterCategoryId ?? null;
  const swrTeamsResponse = getTeamsPaginated(
    tournamentData.id,
    tableStateToPagination(tableState),
    filteredCategoryId,
  );
  const swrStagesResponse = getStages(tournamentData.id);
  const stageItemInputLookup = responseIsValid(swrStagesResponse)
    ? getStageItemList(swrStagesResponse)
    : [];
  const stageItemTeamLookup = responseIsValid(swrStagesResponse)
    ? getStageItemTeamIdsLookup(swrStagesResponse)
    : {};

  let teams: FullTeamWithPlayers[] =
    swrTeamsResponse.data != null ? swrTeamsResponse.data.data.teams : [];
  const teamCount = swrTeamsResponse.data != null ? swrTeamsResponse.data.data.count : 1;

  if (filteredStageItemId != null) {
    teams = (swrTeamsResponse.data?.data.teams || []).filter(
      (team: FullTeamWithPlayers) =>
        stageItemTeamLookup[filteredStageItemId].indexOf(team.id) !== -1,
    );
  }

  return (
    <TournamentLayout tournament_id={tournamentData.id}>
      <Grid justify="space-between" mb="1rem">
        <Grid.Col span="auto">
          <Title>{capitalize(t('teams_title'))}</Title>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 'content' }}>
          <Grid align="flex-end">
            <Grid.Col span={{ base: 12, xs: 'auto' }}>
              <CategoryFilterSelect
                categories={categories}
                value={filterValue}
                setValue={setFilterValue}
              />
            </Grid.Col>
            <Grid.Col span={{ base: 12, xs: 'auto' }}>
              <StageItemSelect
                groupStageItems={Object.values(stageItemInputLookup)}
                setFilteredStageItemId={setFilteredStageItemId}
              />
            </Grid.Col>
            <Grid.Col span={{ base: 12, xs: 'auto' }}>
              <TeamCreateModal
                swrTeamsResponse={swrTeamsResponse}
                tournament_id={tournamentData.id}
                defaultCategoryId={filteredCategoryId}
              />
            </Grid.Col>
          </Grid>
        </Grid.Col>
      </Grid>
      <TeamsTable
        swrTeamsResponse={swrTeamsResponse}
        tournamentData={tournamentData}
        teams={teams}
        categories={categories}
        tableState={tableState}
        teamCount={teamCount}
      />
    </TournamentLayout>
  );
}
