import {
  Alert,
  Badge,
  Button,
  Group,
  Modal,
  NumberInput,
  SegmentedControl,
  Select,
  Stack,
  Table,
  Text,
} from '@mantine/core';
import { IconClockPlus, IconEye } from '@tabler/icons-react';
import dayjs from 'dayjs';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ProposalReport } from '@components/scheduling/match_plan_panel';
import { DayAndTime } from '@components/utils/datetime';
import { DateTimeField } from '@components/utils/time_fields';
import { Court, ReplanBody, ReplanPreview } from '@openapi';
import { getCategories, requestSucceeded } from '@services/adapter';
import { applyReplan, previewReplan } from '@services/planning';

const CHANGES_SHOWN = 15;

/** Now, rounded up to the next 5 minutes. */
function nextFiveMinutes(): string {
  const now = dayjs();
  return now
    .add(5 - (now.minute() % 5), 'minute')
    .second(0)
    .millisecond(0)
    .format('YYYY-MM-DD HH:mm:ss');
}

/**
 * Changing the schedule during the cup, always with a preview first:
 * - a delay: by pitch or class, the matches keep their pitch and order and gaps (lunch) absorb it;
 * - a new schedule from a moment: everything not played or started is planned again.
 * Played and started matches never move, and nothing is planned in the past.
 */
export function ScheduleChangeForm({
  tournamentId,
  courts,
  matchLabel,
  onApplied,
}: {
  tournamentId: number;
  courts: Court[];
  matchLabel: (matchId: number) => string;
  onApplied: () => Promise<void>;
}) {
  const { t } = useTranslation();
  const categories = getCategories(tournamentId).data?.data ?? [];
  const [mode, setMode] = useState<'delay' | 'replan'>('delay');
  const [minutes, setMinutes] = useState<number | string>(10);
  const [courtId, setCourtId] = useState<string | null>(null);
  const [categoryId, setCategoryId] = useState<string | null>(null);
  const [fromTime, setFromTime] = useState<string | null>(null);
  const [preview, setPreview] = useState<ReplanPreview | null>(null);
  const [body, setBody] = useState<ReplanBody | null>(null);
  const [loading, setLoading] = useState(false);
  const courtName = (id: number | null) => courts.find((c) => c.id === id)?.name ?? '–';

  function makeBody(): ReplanBody {
    const from = dayjs(fromTime ?? nextFiveMinutes()).toISOString();
    if (mode === 'replan') {
      return {
        from_time: from,
        delay_minutes: 0,
        court_id: null,
        category_id: null,
        keep_courts: false,
      };
    }
    return {
      from_time: dayjs().toISOString(),
      delay_minutes: Number(minutes),
      court_id: courtId == null ? null : Number(courtId),
      category_id: categoryId == null ? null : Number(categoryId),
      keep_courts: true,
    };
  }

  return (
    <Stack gap="sm">
      <Modal
        opened={preview != null}
        onClose={() => setPreview(null)}
        title={t('schedule_change_preview_title')}
        size="44rem"
      >
        {preview != null && body != null ? (
          <Stack>
            {preview.moved < 1 ? (
              <Alert color="gray">{t('schedule_change_nothing')}</Alert>
            ) : (
              <Group gap="xs">
                <Badge size="lg" variant="light">
                  {t('schedule_change_moved', { count: preview.moved })}
                </Badge>
                <Badge size="lg" variant="light" color="gray">
                  {t('schedule_change_unchanged', { count: preview.unchanged })}
                </Badge>
                <Badge size="lg" variant="light" color="orange">
                  {t('schedule_change_max_shift', { count: preview.max_shift_minutes })}
                </Badge>
              </Group>
            )}
            {preview.proposal.unscheduled_match_ids.length > 0 ? (
              <ProposalReport proposal={preview.proposal} />
            ) : null}
            {preview.changes.length > 0 ? (
              <Table.ScrollContainer minWidth={500}>
                <Table striped>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>{t('match_label')}</Table.Th>
                      <Table.Th>{t('schedule_change_before')}</Table.Th>
                      <Table.Th>{t('schedule_change_after')}</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {preview.changes.slice(0, CHANGES_SHOWN).map((change) => (
                      <Table.Tr key={change.match_id}>
                        <Table.Td>{matchLabel(change.match_id)}</Table.Td>
                        <Table.Td>
                          {change.old_start != null ? (
                            <DayAndTime datetime={change.old_start} />
                          ) : (
                            '–'
                          )}
                          <Text size="xs" c="dimmed">
                            {courtName(change.old_court_id)}
                          </Text>
                        </Table.Td>
                        <Table.Td>
                          {change.new_start != null ? (
                            <DayAndTime datetime={change.new_start} />
                          ) : (
                            <Text c="red" size="sm">
                              {t('schedule_change_no_room')}
                            </Text>
                          )}
                          <Text size="xs" c="dimmed">
                            {courtName(change.new_court_id)}
                          </Text>
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Table.ScrollContainer>
            ) : null}
            {preview.changes.length > CHANGES_SHOWN ? (
              <Text size="sm" c="dimmed">
                {t('and_more_label', { count: preview.changes.length - CHANGES_SHOWN })}
              </Text>
            ) : null}
            <Group justify="right">
              <Button variant="default" onClick={() => setPreview(null)}>
                {t('cancel_button')}
              </Button>
              <Button
                color="green"
                loading={loading}
                disabled={preview.moved < 1}
                onClick={async () => {
                  setLoading(true);
                  const result = await applyReplan(tournamentId, body);
                  setLoading(false);
                  if (requestSucceeded(result)) {
                    setPreview(null);
                    await onApplied();
                  }
                }}
              >
                {t('schedule_change_apply_button', { count: preview.moved })}
              </Button>
            </Group>
          </Stack>
        ) : null}
      </Modal>

      <SegmentedControl
        value={mode}
        onChange={(value) => setMode(value as 'delay' | 'replan')}
        data={[
          { value: 'delay', label: t('schedule_change_delay_mode') },
          { value: 'replan', label: t('schedule_change_replan_mode') },
        ]}
        maw="30rem"
      />
      <Text size="sm" c="dimmed">
        {mode === 'delay'
          ? t('schedule_change_delay_description')
          : t('schedule_change_replan_description')}
      </Text>
      {mode === 'delay' ? (
        <Group align="end">
          <NumberInput
            label={t('delay_minutes_label')}
            min={1}
            max={600}
            value={minutes}
            onChange={setMinutes}
            w="8rem"
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
          <Select
            label={t('category_select_label')}
            placeholder={t('delay_all_classes')}
            clearable
            data={categories.map((c) => ({ value: `${c.id}`, label: c.name }))}
            value={categoryId}
            onChange={setCategoryId}
            w="12rem"
          />
        </Group>
      ) : (
        <DateTimeField
          label={t('schedule_change_from_label')}
          value={fromTime ?? nextFiveMinutes()}
          onChange={(value) => setFromTime(value)}
          maw="16rem"
        />
      )}
      <Group>
        <Button
          leftSection={mode === 'delay' ? <IconClockPlus size={20} /> : <IconEye size={20} />}
          loading={loading}
          disabled={mode === 'delay' && !(Number(minutes) >= 1)}
          onClick={async () => {
            const newBody = makeBody();
            setLoading(true);
            const result = await previewReplan(tournamentId, newBody);
            setLoading(false);
            if (requestSucceeded(result) && 'data' in result) {
              setBody(newBody);
              setPreview(result.data.data);
            }
          }}
        >
          {t('schedule_change_preview_button')}
        </Button>
      </Group>
    </Stack>
  );
}
