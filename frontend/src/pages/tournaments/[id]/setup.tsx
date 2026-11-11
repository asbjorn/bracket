import { Alert, Button, Checkbox, Group, Stack, Stepper, Text, Title } from '@mantine/core';
import { IconInfoCircle, IconWand } from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';

import {
  ClassesEditor,
  ClassResults,
  CourtsEditor,
  DEFAULT_PLAYING_DAYS,
  PlayingDays,
  PlayingDaysEditor,
  newClass,
  toTimeWindows,
  withAllowedPlayoffs,
} from '@components/planning/cup_plan_editor';
import { ProposalReport } from '@components/scheduling/match_plan_panel';
import { getTournamentIdFromRouter } from '@components/utils/util';
import { CapacityCourts, CapacityResult, CupSetupClass } from '@openapi';
import TournamentLayout from '@pages/tournaments/_tournament_layout';
import { getCategories, getStages, getTournamentById, requestSucceeded } from '@services/adapter';
import { calculateCapacity } from '@services/capacity';
import { setUpCup } from '@services/cup_setup';
import { applySchedule } from '@services/planning';

const LAST_STEP = 3;

export default function CupSetupPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { tournamentData } = getTournamentIdFromRouter();
  const tournament = getTournamentById(tournamentData.id).data?.data;
  const swrStagesResponse = getStages(tournamentData.id);
  const swrCategoriesResponse = getCategories(tournamentData.id);

  const [step, setStep] = useState(0);
  const [classes, setClasses] = useState<CupSetupClass[]>([newClass('G10', 10)]);
  const [courts, setCourts] = useState<CapacityCourts[]>([{ count: 2, game_format: '7v7' }]);
  const [playingDays, setPlayingDays] = useState<PlayingDays>(DEFAULT_PLAYING_DAYS);
  const [preview, setPreview] = useState<CapacityResult | null>(null);
  const [planMatches, setPlanMatches] = useState(true);
  const [loading, setLoading] = useState(false);

  const isEmpty =
    (swrStagesResponse.data?.data ?? []).length < 1 &&
    (swrCategoriesResponse.data?.data ?? []).length < 1;
  const loaded = swrStagesResponse.data != null && swrCategoriesResponse.data != null;
  const allowedClasses = classes.map(withAllowedPlayoffs);
  const timeWindows = toTimeWindows(playingDays);

  async function showPreview() {
    setLoading(true);
    setPreview(null);
    const response = await calculateCapacity({
      classes: allowedClasses,
      courts,
      time_windows: timeWindows,
      stage_buffer_minutes: tournament?.stage_buffer_minutes ?? 10,
    });
    setLoading(false);
    if (requestSucceeded(response) && 'data' in response) {
      setPreview(response.data.data);
      setStep(LAST_STEP);
    }
  }

  async function createCup() {
    setLoading(true);
    const response = await setUpCup(tournamentData.id, {
      classes: allowedClasses,
      courts: courts.map((group) => ({
        ...group,
        name_prefix: t('court_name_prefix_default'),
      })),
      time_windows: timeWindows,
      names: {
        group_stage: t('setup_group_stage_name'),
        group: t('setup_group_name'),
        playoff_stage: t('setup_playoff_stage_name'),
        playoff: t('setup_playoff_name'),
      },
    });
    if (requestSucceeded(response) && planMatches) await applySchedule(tournamentData.id);
    setLoading(false);
    if (requestSucceeded(response)) navigate(`/tournaments/${tournamentData.id}/schedule`);
  }

  const next = (disabled: boolean) => (
    <Button disabled={disabled} onClick={() => setStep(step + 1)}>
      {t('setup_next_button')}
    </Button>
  );

  return (
    <TournamentLayout tournament_id={tournamentData.id}>
      <Stack>
        <Title>{t('setup_title')}</Title>
        <Alert color="gray" icon={<IconInfoCircle />}>
          {t('setup_description')}
        </Alert>
        {loaded && !isEmpty ? (
          <Alert color="orange">{t('setup_not_empty_alert')}</Alert>
        ) : (
          <Stepper active={step} onStepClick={setStep} allowNextStepsSelect={false}>
            <Stepper.Step label={t('categories_title')}>
              <Stack>
                <ClassesEditor value={classes} onChange={setClasses} withResultsPublic />
                <Group justify="right">{next(classes.length < 1)}</Group>
              </Stack>
            </Stepper.Step>
            <Stepper.Step label={t('add_courts_title')}>
              <Stack>
                <CourtsEditor value={courts} onChange={setCourts} />
                <Group justify="right">{next(courts.length < 1)}</Group>
              </Stack>
            </Stepper.Step>
            <Stepper.Step label={t('time_windows_title')}>
              <Stack>
                <PlayingDaysEditor value={playingDays} onChange={setPlayingDays} />
                <Group justify="right">
                  <Button loading={loading} disabled={timeWindows.length < 1} onClick={showPreview}>
                    {t('setup_next_button')}
                  </Button>
                </Group>
              </Stack>
            </Stepper.Step>
            <Stepper.Step label={t('setup_review_step')}>
              {preview != null ? (
                <Stack>
                  <ProposalReport proposal={preview.schedule} />
                  <ClassResults result={preview} />
                  <Text size="sm" c="dimmed">
                    {t('setup_review_description')}
                  </Text>
                  <Checkbox
                    label={t('setup_plan_matches_label')}
                    checked={planMatches}
                    onChange={(event) => setPlanMatches(event.currentTarget.checked)}
                  />
                  <Group justify="right">
                    <Button
                      size="md"
                      color="green"
                      loading={loading}
                      leftSection={<IconWand size={22} />}
                      onClick={createCup}
                    >
                      {t('setup_create_button')}
                    </Button>
                  </Group>
                </Stack>
              ) : null}
            </Stepper.Step>
          </Stepper>
        )}
      </Stack>
    </TournamentLayout>
  );
}
