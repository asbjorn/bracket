import {
  Accordion,
  Alert,
  Button,
  Group,
  List,
  Modal,
  NumberInput,
  Select,
  Stack,
  Text,
  TextInput,
} from '@mantine/core';
import { IconAlertTriangle, IconCalendarPlus, IconCheck } from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { SWRResponse } from 'swr';

import { DelayForm } from '@components/scheduling/plan_issues';
import ScoreLinksPanel from '@components/scheduling/score_links_panel';
import TimeWindowsEditor from '@components/scheduling/time_windows_editor';
import { DayAndTime } from '@components/utils/datetime';
import { CourtsResponse, GameFormat, ScheduleProposal } from '@openapi';
import { getTimeWindows, requestSucceeded } from '@services/adapter';
import { applySchedule, createCourts, proposeSchedule } from '@services/planning';

export const GAME_FORMATS: GameFormat[] = ['3v3', '5v5', '7v7', '9v9', '11v11'];

function formatDuration(t: any, minutes: number) {
  const hours = Math.floor(minutes / 60);
  return t('duration_hours_minutes', { hours, minutes: minutes % 60 });
}

function AddCourtsForm({
  tournamentId,
  swrCourtsResponse,
}: {
  tournamentId: number;
  swrCourtsResponse: SWRResponse<CourtsResponse>;
}) {
  const { t } = useTranslation();
  const [count, setCount] = useState<number | string>(2);
  const [prefix, setPrefix] = useState(t('court_name_prefix_default'));
  const [gameFormat, setGameFormat] = useState<string | null>(null);

  return (
    <Group align="end">
      <NumberInput
        label={t('court_count_label')}
        min={1}
        max={32}
        value={count}
        onChange={setCount}
        w="8rem"
      />
      <TextInput
        label={t('court_name_prefix_label')}
        value={prefix}
        onChange={(event) => setPrefix(event.currentTarget.value)}
        w="10rem"
      />
      <Select
        label={t('game_format_label')}
        placeholder={t('game_format_any')}
        clearable
        data={GAME_FORMATS}
        value={gameFormat}
        onChange={setGameFormat}
        w="10rem"
      />
      <Button
        onClick={async () => {
          const result = await createCourts(
            tournamentId,
            Number(count),
            prefix,
            gameFormat as GameFormat | null,
          );
          if (requestSucceeded(result)) await swrCourtsResponse.mutate();
        }}
      >
        {t('add_courts_button')}
      </Button>
    </Group>
  );
}

export function ProposalReport({ proposal }: { proposal: ScheduleProposal }) {
  const { t } = useTranslation();
  const scheduled = proposal.matches_total - proposal.unscheduled_match_ids.length;
  const utilisation =
    proposal.available_court_minutes > 0
      ? Math.round((100 * proposal.required_court_minutes) / proposal.available_court_minutes)
      : 0;
  const fits = proposal.unscheduled_match_ids.length < 1;

  return (
    <Stack>
      {proposal.uses_default_window ? (
        <Alert color="orange" icon={<IconAlertTriangle />}>
          {t('schedule_default_window_alert')}
        </Alert>
      ) : null}
      {fits ? (
        <Alert color="green" icon={<IconCheck />} title={t('schedule_fits_title')}>
          {t('schedule_fits_description', { count: proposal.matches_total })}
        </Alert>
      ) : (
        <Alert color="red" icon={<IconAlertTriangle />} title={t('schedule_does_not_fit_title')}>
          <Stack gap="xs">
            <Text size="sm">
              {t('schedule_does_not_fit_description', {
                scheduled,
                total: proposal.matches_total,
              })}
            </Text>
            <List size="sm">
              {proposal.extra_courts == null ? (
                <List.Item>{t('schedule_more_courts_dont_help')}</List.Item>
              ) : (
                proposal.extra_courts.map((extra) => (
                  <List.Item key={extra.game_format ?? 'any'}>
                    {t('schedule_extra_courts', {
                      count: extra.count,
                      format: extra.game_format ?? t('game_format_any'),
                    })}
                  </List.Item>
                ))
              )}
              {proposal.extra_minutes == null ? (
                <List.Item>{t('schedule_more_time_doesnt_help')}</List.Item>
              ) : (
                <List.Item>
                  {t('schedule_extra_time', {
                    duration: formatDuration(t, proposal.extra_minutes),
                  })}
                </List.Item>
              )}
            </List>
          </Stack>
        </Alert>
      )}
      <List size="sm">
        {proposal.first_start != null && proposal.last_end != null ? (
          <List.Item>
            {t('schedule_first_and_last')} <DayAndTime datetime={proposal.first_start} /> –{' '}
            <DayAndTime datetime={proposal.last_end} />
          </List.Item>
        ) : null}
        <List.Item>
          {t('schedule_court_time', {
            required: formatDuration(t, proposal.required_court_minutes),
            available: formatDuration(t, proposal.available_court_minutes),
            utilisation,
          })}
        </List.Item>
      </List>
    </Stack>
  );
}

export default function MatchPlanPanel({
  tournamentId,
  swrCourtsResponse,
  onApplied,
}: {
  tournamentId: number;
  swrCourtsResponse: SWRResponse<CourtsResponse>;
  onApplied: () => Promise<void>;
}) {
  const { t } = useTranslation();
  const swrTimeWindowsResponse = getTimeWindows(tournamentId);
  const [proposal, setProposal] = useState<ScheduleProposal | null>(null);
  const [loading, setLoading] = useState(false);

  return (
    <>
      <Modal
        opened={proposal != null}
        onClose={() => setProposal(null)}
        title={t('schedule_proposal_title')}
        size="40rem"
      >
        {proposal != null ? (
          <Stack>
            <ProposalReport proposal={proposal} />
            <Text size="sm" c="dimmed">
              {t('schedule_apply_description')}
            </Text>
            <Group justify="right">
              <Button variant="default" onClick={() => setProposal(null)}>
                {t('cancel_button')}
              </Button>
              <Button
                color="green"
                loading={loading}
                onClick={async () => {
                  setLoading(true);
                  const result = await applySchedule(tournamentId);
                  setLoading(false);
                  if (requestSucceeded(result)) {
                    await onApplied();
                    setProposal(null);
                  }
                }}
              >
                {t('schedule_apply_button')}
              </Button>
            </Group>
          </Stack>
        ) : null}
      </Modal>
      <Accordion variant="contained" mb="md">
        <Accordion.Item value="time_windows">
          <Accordion.Control>{t('time_windows_title')}</Accordion.Control>
          <Accordion.Panel>
            <TimeWindowsEditor
              tournamentId={tournamentId}
              timeWindows={swrTimeWindowsResponse.data?.data ?? []}
              onSaved={() => swrTimeWindowsResponse.mutate()}
            />
          </Accordion.Panel>
        </Accordion.Item>
        <Accordion.Item value="delay">
          <Accordion.Control>{t('delay_title')}</Accordion.Control>
          <Accordion.Panel>
            <DelayForm
              tournamentId={tournamentId}
              courts={swrCourtsResponse.data?.data ?? []}
              onDelayed={onApplied}
            />
          </Accordion.Panel>
        </Accordion.Item>
        <Accordion.Item value="score_links">
          <Accordion.Control>{t('score_links_title')}</Accordion.Control>
          <Accordion.Panel>
            <ScoreLinksPanel
              tournamentId={tournamentId}
              courts={swrCourtsResponse.data?.data ?? []}
            />
          </Accordion.Panel>
        </Accordion.Item>
        <Accordion.Item value="courts">
          <Accordion.Control>{t('add_courts_title')}</Accordion.Control>
          <Accordion.Panel>
            <AddCourtsForm tournamentId={tournamentId} swrCourtsResponse={swrCourtsResponse} />
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>
      <Button
        color="indigo"
        size="md"
        loading={loading}
        leftSection={<IconCalendarPlus size={24} />}
        onClick={async () => {
          setLoading(true);
          const result = await proposeSchedule(tournamentId);
          setLoading(false);
          if (requestSucceeded(result) && 'data' in result) setProposal(result.data.data);
        }}
      >
        {t('schedule_propose_button')}
      </Button>
    </>
  );
}
