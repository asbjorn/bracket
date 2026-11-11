import { Group, Stack } from '@mantine/core';
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';

import Builder from '@components/builder/builder';
import { CreateStageButtonLarge } from '@components/buttons/create_stage';
import { CategoryWarnings } from '@components/info/category_warnings';
import ActivateNextStageModal from '@components/modals/activate_next_stage_modal';
import ActivatePreviousStageModal from '@components/modals/activate_previous_stage_modal';
import CreatePlayoffsModal from '@components/modals/create_playoffs_modal';
import { NoContent } from '@components/no_content/empty_table_info';
import { CategorySelector, useSelectedCategory } from '@components/utils/category';
import { TableSkeletonTwoColumnsSmall } from '@components/utils/skeletons';
import { getTournamentIdFromRouter } from '@components/utils/util';
import { StageWithStageItems } from '@openapi';
import TournamentLayout from '@pages/tournaments/_tournament_layout';
import {
  getAvailableStageItemInputs,
  getCategories,
  getCategoryWarnings,
  getRankings,
  getRankingsPerStageItem,
  getStages,
  getTournamentById,
} from '@services/adapter';

export default function StagesPage() {
  const { t } = useTranslation();
  const { tournamentData } = getTournamentIdFromRouter();
  const swrStagesResponse = getStages(tournamentData.id);
  const swrRankingsResponse = getRankings(tournamentData.id);
  const swrTournamentResponse = getTournamentById(tournamentData.id);
  const swrAvailableInputsResponse = getAvailableStageItemInputs(tournamentData.id);
  const swrCategoriesResponse = getCategories(tournamentData.id);
  const swrWarningsResponse = getCategoryWarnings(tournamentData.id);
  const tournamentDataFull =
    swrTournamentResponse.data != null ? swrTournamentResponse.data.data : null;
  const rankings = swrRankingsResponse.data != null ? swrRankingsResponse.data.data : [];
  const categories = swrCategoriesResponse.data?.data ?? [];

  const allStages: StageWithStageItems[] =
    swrStagesResponse.data != null ? swrStagesResponse.data.data : [];

  // Every age class has its own stages, the user works on one class at a time
  const { categoryId, selectedValue, setSelectedValue, options } = useSelectedCategory(
    categories,
    allStages.some((stage) => stage.category_id == null),
  );
  const stages = allStages.filter((stage) => (stage.category_id ?? null) === categoryId);
  const swrRankingsPerStageItemResponse = getRankingsPerStageItem(tournamentData.id, categoryId);

  // Playoffs can follow the last stage with groups, unless the class hides results
  const resultsHidden = categories.some((c) => c.id === categoryId && !c.results_public);
  const groupStage = [...stages]
    .sort((s1, s2) => s2.id - s1.id)
    .find(
      (stage) =>
        stage.stage_items.length > 0 &&
        stage.stage_items.every((item) => item.type === 'ROUND_ROBIN' || item.type === 'SWISS'),
    );
  // Warnings depend on the structure of the stages, so check again after every change
  useEffect(() => {
    swrWarningsResponse.mutate();
  }, [swrStagesResponse.data]);
  const warnings =
    categoryId == null ? [] : (swrWarningsResponse.data?.data[`${categoryId}`] ?? []);
  const categorySelector = (
    <Stack gap="xs">
      <CategorySelector
        options={options}
        selectedValue={selectedValue}
        setSelectedValue={setSelectedValue}
      />
      <CategoryWarnings warnings={warnings} />
    </Stack>
  );

  let content;
  if (
    swrStagesResponse.isLoading ||
    swrTournamentResponse.isLoading ||
    swrAvailableInputsResponse.isLoading ||
    swrRankingsResponse.isLoading ||
    swrCategoriesResponse.isLoading
  ) {
    content = <TableSkeletonTwoColumnsSmall />;
  } else if (tournamentDataFull == null) {
    // TODO: show loading icon.
    return null;
  } else if (stages.length < 1) {
    content = (
      <>
        {categorySelector}
        <Stack align="center">
          <NoContent title={t('no_matches_title')} description={t('no_matches_description')} />
          <CreateStageButtonLarge
            tournament={tournamentDataFull}
            categoryId={categoryId}
            swrStagesResponse={swrStagesResponse}
          />
        </Stack>
      </>
    );
  } else {
    content = (
      <>
        {categorySelector}
        <Group grow mt="1rem" maw="30rem">
          <ActivatePreviousStageModal
            tournamentId={tournamentData.id}
            categoryId={categoryId}
            swrStagesResponse={swrStagesResponse}
            swrRankingsPerStageItemResponse={swrRankingsPerStageItemResponse}
          />
          <ActivateNextStageModal
            tournamentId={tournamentData.id}
            categoryId={categoryId}
            swrStagesResponse={swrStagesResponse}
            swrRankingsPerStageItemResponse={swrRankingsPerStageItemResponse}
          />
        </Group>
        {groupStage != null && !resultsHidden ? (
          <CreatePlayoffsModal
            // Remount when the group stage changes, so the presets fit its groups
            key={groupStage.id}
            tournamentId={tournamentData.id}
            groupStage={groupStage}
            swrStagesResponse={swrStagesResponse}
          />
        ) : null}
        <Group mt="1rem" align="top">
          <Builder
            tournament={tournamentDataFull}
            categoryId={categoryId}
            swrStagesResponse={swrStagesResponse}
            swrAvailableInputsResponse={swrAvailableInputsResponse}
            swrRankingsPerStageItemResponse={swrRankingsPerStageItemResponse}
            rankings={rankings}
          />
        </Group>
      </>
    );
  }

  return <TournamentLayout tournament_id={tournamentData.id}>{content}</TournamentLayout>;
}
