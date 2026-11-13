import { Alert, Button, Group, SegmentedControl, Stack, Text } from '@mantine/core';
import { IconInfoCircle, IconWand } from '@tabler/icons-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { PageTitle } from '@components/help/help_button';
import Builder from '@components/builder/builder';
import { getClassStatus } from '@components/builder/class_status';
import PhaseBar from '@components/builder/phase_bar';
import SimpleStages from '@components/builder/simple_stages';
import { CreateStageButtonLarge } from '@components/buttons/create_stage';
import { CategoryWarnings } from '@components/info/category_warnings';
import CreatePlayoffsModal from '@components/modals/create_playoffs_modal';
import FitGroupsModal, { CurrentPlayoffs } from '@components/modals/fit_groups_modal';
import LevelRoundButton from '@components/modals/level_round_modal';
import { withViewTransition } from '@components/motion/view_transition';
import { NoContent } from '@components/no_content/empty_table_info';
import { CategorySelector, useSelectedCategory } from '@components/utils/category';
import { teamsToPlace } from '@components/utils/group_stage';
import PreloadLink from '@components/utils/link';
import { TableSkeletonTwoColumnsSmall } from '@components/utils/skeletons';
import { capitalize, getTournamentIdFromRouter } from '@components/utils/util';
import { StageWithStageItems } from '@openapi';
import TournamentLayout from '@pages/tournaments/_tournament_layout';
import {
  getAllTeams,
  getAvailableStageItemInputs,
  getCategories,
  getCategoryWarnings,
  getRankings,
  getRankingsPerStageItem,
  getStages,
  getTournamentById,
} from '@services/adapter';

type Mode = 'simple' | 'advanced';
const MODE_KEY = 'bracket.stages.mode';

function storedMode(): Mode {
  try {
    return localStorage.getItem(MODE_KEY) === 'advanced' ? 'advanced' : 'simple';
  } catch {
    return 'simple';
  }
}

/** The playoffs of a class as the format dialog shows them. */
function currentPlayoffs(
  playoffStage: StageWithStageItems | null,
  resultsHidden: boolean,
): CurrentPlayoffs {
  const items = playoffStage?.stage_items ?? [];
  return {
    count: items.length,
    // The last round of a knockout holds the final and, if any, the match for third place
    thirdPlaceMatch: items.some((item) => {
      const rounds = [...item.rounds].sort((a, b) => a.id - b.id);
      return rounds.length > 0 && rounds[rounds.length - 1].matches.length > 1;
    }),
    allowed: !resultsHidden,
  };
}

export default function StagesPage() {
  const { t } = useTranslation();
  const { tournamentData } = getTournamentIdFromRouter();
  const swrStagesResponse = getStages(tournamentData.id);
  const swrRankingsResponse = getRankings(tournamentData.id);
  const swrTournamentResponse = getTournamentById(tournamentData.id);
  const swrAvailableInputsResponse = getAvailableStageItemInputs(tournamentData.id);
  const swrCategoriesResponse = getCategories(tournamentData.id);
  const swrWarningsResponse = getCategoryWarnings(tournamentData.id);
  const swrTeams = getAllTeams(tournamentData.id);
  const tournamentDataFull =
    swrTournamentResponse.data != null ? swrTournamentResponse.data.data : null;
  const rankings = swrRankingsResponse.data != null ? swrRankingsResponse.data.data : [];
  const categories = swrCategoriesResponse.data?.data ?? [];
  const [mode, setMode] = useState<Mode>(storedMode);
  const [dialog, setDialog] = useState<'fit' | 'format' | null>(null);

  const allStages: StageWithStageItems[] =
    swrStagesResponse.data != null ? swrStagesResponse.data.data : [];

  // Every age class has its own stages, the user works on one class at a time
  const { categoryId, selectedValue, setSelectedValue, options } = useSelectedCategory(
    categories,
    allStages.some((stage) => stage.category_id == null),
  );
  const stages = allStages.filter((stage) => (stage.category_id ?? null) === categoryId);
  const swrRankingsPerStageItemResponse = getRankingsPerStageItem(tournamentData.id, categoryId);
  const category = categories.find((c) => c.id === categoryId) ?? null;
  const resultsHidden = category != null && !category.results_public;
  const status = getClassStatus(stages, teamsToPlace(swrTeams.data ?? [], categoryId).length);

  // Playoffs can follow the last stage with groups, unless the class hides results
  const groupStage = [...stages]
    .sort((s1, s2) => s2.id - s1.id)
    .find(
      (stage) =>
        stage.stage_items.length > 0 &&
        stage.stage_items.every((item) => item.type === 'ROUND_ROBIN' || item.type === 'SWISS'),
    );
  // The format dialog handles a class of groups plus at most one playoff stage, before it starts
  const canChangeFormat =
    status.groupStage != null &&
    status.groupStage.stage_items.every((item) => item.type === 'ROUND_ROBIN') &&
    stages.length <= (status.playoffStage != null ? 2 : 1) &&
    !(status.playoffStage?.is_active ?? false) &&
    status.phase !== 'done';

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
        setSelectedValue={(value) => withViewTransition(() => setSelectedValue(value))}
      />
      <CategoryWarnings warnings={warnings} />
    </Stack>
  );
  const modeSwitch = (
    <SegmentedControl
      size="xs"
      value={mode}
      onChange={(value) => {
        withViewTransition(() => setMode(value as Mode));
        try {
          localStorage.setItem(MODE_KEY, value);
        } catch {
          // Not remembered, e.g. in a private window
        }
      }}
      data={[
        { value: 'simple', label: t('stages_mode_simple') },
        { value: 'advanced', label: t('stages_mode_advanced') },
      ]}
      aria-label={t('stages_mode_label')}
    />
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
          {(swrStagesResponse.data?.data ?? []).length < 1 ? (
            // A new cup: the wizard sets up classes, groups, playoffs and courts at once
            <Button
              component={PreloadLink}
              href={`/tournaments/${tournamentData.id}/setup`}
              size="lg"
              color="indigo"
              leftSection={<IconWand size={22} />}
            >
              {t('setup_start_button')}
            </Button>
          ) : null}
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
      <Stack gap="lg">
        {categorySelector}
        <PhaseBar
          tournamentId={tournamentData.id}
          categoryId={categoryId}
          className={category?.name ?? t('no_category_label')}
          status={status}
          canChangeFormat={canChangeFormat}
          swrStagesResponse={swrStagesResponse}
          swrRankingsPerStageItemResponse={swrRankingsPerStageItemResponse}
          onFit={() => setDialog('fit')}
          onFormat={() => setDialog('format')}
          modeSwitch={modeSwitch}
        />
        {mode === 'advanced' ? (
          <>
            <Alert color="gray" icon={<IconInfoCircle />} p="xs">
              <Text size="sm">{t('stages_advanced_hint')}</Text>
            </Alert>
            <Group gap="sm">
              {groupStage != null && !resultsHidden ? (
                <CreatePlayoffsModal
                  // Remount when the group stage changes, so the presets fit its groups
                  key={groupStage.id}
                  tournamentId={tournamentData.id}
                  groupStage={groupStage}
                  swrStagesResponse={swrStagesResponse}
                />
              ) : null}
              {categoryId != null ? (
                <LevelRoundButton
                  tournamentId={tournamentData.id}
                  categoryId={categoryId}
                  onCreated={async () => {
                    await swrStagesResponse.mutate();
                  }}
                />
              ) : null}
            </Group>
            <Group align="top" wrap="wrap">
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
        ) : (
          <SimpleStages
            tournamentId={tournamentData.id}
            stages={stages}
            swrStagesResponse={swrStagesResponse}
          />
        )}
        {dialog != null && status.groupStage != null ? (
          <FitGroupsModal
            tournamentId={tournamentData.id}
            stage={status.groupStage}
            className={category?.name ?? ''}
            playoffs={
              dialog === 'format' ? currentPlayoffs(status.playoffStage, resultsHidden) : undefined
            }
            onClose={() => setDialog(null)}
            onFitted={async () => {
              await swrStagesResponse.mutate();
              await swrAvailableInputsResponse.mutate();
            }}
          />
        ) : null}
      </Stack>
    );
  }

  return (
    <TournamentLayout tournament_id={tournamentData.id}>
      <PageTitle help="stages" mb="sm">
        {capitalize(t('stage_title'))}
      </PageTitle>
      {content}
    </TournamentLayout>
  );
}
