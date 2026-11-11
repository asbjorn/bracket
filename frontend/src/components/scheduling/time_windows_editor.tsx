import { Button, Group, Stack, Table, Text } from '@mantine/core';
import { DatePickerInput, TimeInput } from '@mantine/dates';
import dayjs from 'dayjs';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { DayAndTime } from '@components/utils/datetime';
import { requestSucceeded } from '@services/adapter';
import { TimeWindowValue, saveTimeWindows } from '@services/planning';

/**
 * Time windows for every day from `firstDay` to `lastDay`: from `dayStart` to `dayEnd`, split by
 * a lunch break when both lunch times are given. Times are local times ("HH:mm").
 */
export function buildTimeWindows(
  firstDay: string,
  lastDay: string,
  dayStart: string,
  dayEnd: string,
  lunchStart: string,
  lunchEnd: string,
): TimeWindowValue[] {
  const windows: TimeWindowValue[] = [];
  const hasLunch = lunchStart !== '' && lunchEnd !== '';
  const at = (day: dayjs.Dayjs, time: string) =>
    dayjs(`${day.format('YYYY-MM-DD')}T${time}`).toISOString();

  for (let day = dayjs(firstDay); !day.isAfter(dayjs(lastDay), 'day'); day = day.add(1, 'day')) {
    if (hasLunch) {
      windows.push({ start_time: at(day, dayStart), end_time: at(day, lunchStart) });
      windows.push({ start_time: at(day, lunchEnd), end_time: at(day, dayEnd) });
    } else {
      windows.push({ start_time: at(day, dayStart), end_time: at(day, dayEnd) });
    }
  }
  return windows;
}

export default function TimeWindowsEditor({
  tournamentId,
  timeWindows,
  onSaved,
}: {
  tournamentId: number;
  timeWindows: TimeWindowValue[];
  onSaved: () => void;
}) {
  const { t } = useTranslation();
  const [days, setDays] = useState<[string | null, string | null]>([null, null]);
  const [dayStart, setDayStart] = useState('09:00');
  const [dayEnd, setDayEnd] = useState('17:00');
  const [lunchStart, setLunchStart] = useState('');
  const [lunchEnd, setLunchEnd] = useState('');

  const canSave = days[0] != null && dayStart < dayEnd;

  return (
    <Stack>
      <Text size="sm" c="dimmed">
        {t('time_windows_description')}
      </Text>
      <DatePickerInput
        type="range"
        allowSingleDateInRange
        label={t('time_windows_days_label')}
        value={days}
        onChange={(value) => setDays(value as [string | null, string | null])}
        maw="24rem"
      />
      <Group>
        <TimeInput
          label={t('time_windows_start_label')}
          value={dayStart}
          onChange={(event) => setDayStart(event.currentTarget.value)}
        />
        <TimeInput
          label={t('time_windows_end_label')}
          value={dayEnd}
          onChange={(event) => setDayEnd(event.currentTarget.value)}
        />
        <TimeInput
          label={t('time_windows_lunch_start_label')}
          value={lunchStart}
          onChange={(event) => setLunchStart(event.currentTarget.value)}
        />
        <TimeInput
          label={t('time_windows_lunch_end_label')}
          value={lunchEnd}
          onChange={(event) => setLunchEnd(event.currentTarget.value)}
        />
      </Group>
      <Group>
        <Button
          disabled={!canSave}
          onClick={async () => {
            const windows = buildTimeWindows(
              days[0] ?? '',
              days[1] ?? days[0] ?? '',
              dayStart,
              dayEnd,
              lunchStart,
              lunchEnd,
            );
            const result = await saveTimeWindows(tournamentId, windows);
            if (requestSucceeded(result)) onSaved();
          }}
        >
          {t('time_windows_save_button')}
        </Button>
      </Group>
      {timeWindows.length > 0 ? (
        <Table maw="30rem">
          <Table.Tbody>
            {timeWindows.map((window) => (
              <Table.Tr key={window.start_time}>
                <Table.Td>
                  <DayAndTime datetime={window.start_time} />
                </Table.Td>
                <Table.Td>–</Table.Td>
                <Table.Td>
                  <DayAndTime datetime={window.end_time} />
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      ) : (
        <Text size="sm" c="orange">
          {t('no_time_windows')}
        </Text>
      )}
    </Stack>
  );
}
