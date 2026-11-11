import { Alert, Button, Group, NumberInput, Stack, Text, Title } from '@mantine/core';
import { IconCalculator, IconInfoCircle } from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  ClassesEditor,
  ClassResults,
  CourtsEditor,
  DEFAULT_PLAYING_DAYS,
  PlayingDays,
  PlayingDaysEditor,
  newClass,
  toTimeWindows,
} from '@components/planning/cup_plan_editor';
import { ProposalReport } from '@components/scheduling/match_plan_panel';
import { CapacityCourts, CapacityResult, CupSetupClass } from '@openapi';
import { requestSucceeded } from '@services/adapter';
import { calculateCapacity } from '@services/capacity';
import Layout from './_layout';

export default function CapacityPage() {
  const { t } = useTranslation();
  const [classes, setClasses] = useState<CupSetupClass[]>([
    newClass('G10', 10),
    newClass('J14', 14),
  ]);
  const [courts, setCourts] = useState<CapacityCourts[]>([
    { count: 2, game_format: '7v7' },
    { count: 1, game_format: '11v11' },
  ]);
  const [playingDays, setPlayingDays] = useState<PlayingDays>(DEFAULT_PLAYING_DAYS);
  const [stageBuffer, setStageBuffer] = useState<number | string>(10);
  const [result, setResult] = useState<CapacityResult | null>(null);
  const [loading, setLoading] = useState(false);

  return (
    <Layout>
      <Stack>
        <Title>{t('capacity_title')}</Title>
        <Alert color="gray" icon={<IconInfoCircle />}>
          {t('capacity_description')}
        </Alert>

        <Title order={3}>{t('categories_title')}</Title>
        <ClassesEditor value={classes} onChange={setClasses} />

        <Title order={3}>{t('add_courts_title')}</Title>
        <CourtsEditor value={courts} onChange={setCourts} />

        <Title order={3}>{t('time_windows_title')}</Title>
        <PlayingDaysEditor value={playingDays} onChange={setPlayingDays} />
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
            disabled={playingDays.days[0] == null || classes.length < 1}
            leftSection={<IconCalculator size={22} />}
            onClick={async () => {
              setLoading(true);
              const response = await calculateCapacity({
                classes,
                courts,
                time_windows: toTimeWindows(playingDays),
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
