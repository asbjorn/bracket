import { Alert, Button, Group, List, NumberInput, Select, Stack, Text } from '@mantine/core';
import { IconAlertTriangle, IconClockPlus } from '@tabler/icons-react';
import dayjs from 'dayjs';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { SWRResponse } from 'swr';

import { formatMatchInput1, formatMatchInput2 } from '@components/utils/match';
import { Court, PlanIssueOut, StagesWithStageItemsResponse } from '@openapi';
import { getPlanIssues, requestSucceeded } from '@services/adapter';
import { delaySchedule } from '@services/planning';

const MAX_ISSUES_SHOWN = 10;

/**
 * Problems in the current plan, e.g. after moving matches by hand or delaying them.
 */
export function PlanIssues({
  tournamentId,
  swrStagesResponse,
  matchesLookup,
  stageItemsLookup,
}: {
  tournamentId: number;
  swrStagesResponse: SWRResponse<StagesWithStageItemsResponse>;
  matchesLookup: any;
  stageItemsLookup: any;
}) {
  const { t } = useTranslation();
  const swrIssuesResponse = getPlanIssues(tournamentId);
  // Check again whenever the matches change
  useEffect(() => {
    swrIssuesResponse.mutate();
  }, [swrStagesResponse.data]);

  const issues: PlanIssueOut[] = swrIssuesResponse.data?.data ?? [];
  if (issues.length < 1) return null;

  const label = (matchId: number) => {
    const data = matchesLookup[matchId];
    if (data == null) return `#${matchId}`;
    return `${formatMatchInput1(t, stageItemsLookup, matchesLookup, data.match)} – ${formatMatchInput2(t, stageItemsLookup, matchesLookup, data.match)}`;
  };

  return (
    <Alert color="orange" icon={<IconAlertTriangle />} title={t('plan_issues_title')} mb="md">
      <List size="sm">
        {issues.slice(0, MAX_ISSUES_SHOWN).map((issue) => (
          <List.Item key={`${issue.match_id}-${issue.kind}-${issue.other_match_id}`}>
            {t(`plan_issue_${issue.kind.toLowerCase()}`, {
              match: label(issue.match_id),
              other: issue.other_match_id != null ? label(issue.other_match_id) : '',
            })}
          </List.Item>
        ))}
      </List>
      {issues.length > MAX_ISSUES_SHOWN ? (
        <Text size="sm" mt="xs">
          {t('and_more_label', { count: issues.length - MAX_ISSUES_SHOWN })}
        </Text>
      ) : null}
    </Alert>
  );
}

/**
 * When the cup runs late: moves all remaining matches (of one court or all courts) that start
 * from now on.
 */
export function DelayForm({
  tournamentId,
  courts,
  onDelayed,
}: {
  tournamentId: number;
  courts: Court[];
  onDelayed: () => Promise<void>;
}) {
  const { t } = useTranslation();
  const [minutes, setMinutes] = useState<number | string>(5);
  const [courtId, setCourtId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  return (
    <Stack gap="xs">
      <Text size="sm" c="dimmed">
        {t('delay_description')}
      </Text>
      <Group align="end">
        <NumberInput
          label={t('delay_minutes_label')}
          min={1}
          max={600}
          value={minutes}
          onChange={setMinutes}
          w="10rem"
        />
        <Select
          label={t('delay_court_label')}
          placeholder={t('delay_all_courts')}
          clearable
          data={courts.map((court) => ({ value: `${court.id}`, label: court.name }))}
          value={courtId}
          onChange={setCourtId}
          w="12rem"
        />
        <Button
          leftSection={<IconClockPlus size={20} />}
          onClick={async () => {
            const result = await delaySchedule(
              tournamentId,
              Number(minutes),
              dayjs().toISOString(),
              courtId == null ? null : Number(courtId),
            );
            if (requestSucceeded(result) && 'data' in result) {
              setMessage(t('delay_result', { count: result.data.data }));
              await onDelayed();
            }
          }}
        >
          {t('delay_button')}
        </Button>
      </Group>
      {message != null ? <Text size="sm">{message}</Text> : null}
    </Stack>
  );
}
