import { Alert, Button, Group, NumberInput, Stack, Text, Title } from '@mantine/core';
import { IconCalculator, IconInfoCircle } from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  ClassResults,
  ClassesEditor,
  CourtsEditor,
  DEFAULT_PLAYING_DAYS,
  MatchesPerDay,
  PlanClass,
  PlayingDays,
  PlayingDaysEditor,
  groupSizeError,
  newClass,
  toApiClass,
  toTimeWindows,
} from '@components/planning/cup_plan_editor';
import { PageTitle } from '@components/help/help_button';
import { ProposalReport } from '@components/scheduling/match_plan_panel';
import { capitalize } from '@components/utils/util';
import { CapacityCourts, CapacityResult } from '@openapi';
import { requestSucceeded } from '@services/adapter';
import { calculateCapacity } from '@services/capacity';
import Layout from './_layout';

export default function CapacityPage() {
  const { t } = useTranslation();
  const [classes, setClasses] = useState<PlanClass[]>([newClass('G10', 10), newClass('J14', 14)]);
  const [courts, setCourts] = useState<CapacityCourts[]>([
    { count: 2, game_format: '7v7', split_into: null, part_format: null },
    { count: 1, game_format: '11v11', split_into: null, part_format: null },
  ]);
  const [playingDays, setPlayingDays] = useState<PlayingDays>(DEFAULT_PLAYING_DAYS);
  const [stageBuffer, setStageBuffer] = useState<number | string>(10);
  const [result, setResult] = useState<CapacityResult | null>(null);
  const [loading, setLoading] = useState(false);
  const cupWindows = toTimeWindows(playingDays);

  return (
    <Layout>
      <Stack>
        <PageTitle help="capacity">{t('capacity_title')}</PageTitle>
        <Alert color="gray" icon={<IconInfoCircle />}>
          {t('capacity_description')}
        </Alert>

        <Title order={3}>{t('time_windows_title')}</Title>
        <PlayingDaysEditor value={playingDays} onChange={setPlayingDays} />

        <Title order={3}>{capitalize(t('categories_title'))}</Title>
        <ClassesEditor value={classes} onChange={setClasses} cupWindows={cupWindows} />

        <Title order={3}>{t('add_courts_title')}</Title>
        <CourtsEditor value={courts} onChange={setCourts} />

        <NumberInput
          label={t('stage_buffer_label')}
          value={stageBuffer}
          min={0}
          onChange={setStageBuffer}
          w="14rem"
        />

        <Group>
          <Button
            size="md"
            color="indigo"
            loading={loading}
            disabled={cupWindows.length < 1 || classes.length < 1 || classes.some(groupSizeError)}
            leftSection={<IconCalculator size={22} />}
            onClick={async () => {
              setLoading(true);
              const response = await calculateCapacity({
                classes: classes.map((value) => toApiClass(value, cupWindows)),
                courts,
                time_windows: cupWindows,
                stage_buffer_minutes: Number(stageBuffer),
              });
              setLoading(false);
              if (requestSucceeded(response) && 'data' in response) setResult(response.data.data);
            }}
          >
            {t('capacity_calculate_button')}
          </Button>
        </Group>

        {result != null ? (
          <Stack>
            <ProposalReport proposal={result.schedule} />
            <MatchesPerDay result={result} />
            <ClassResults result={result} />
            <Text size="sm" c="dimmed">
              {t('capacity_estimate_note')}
            </Text>
          </Stack>
        ) : null}
      </Stack>
    </Layout>
  );
}
