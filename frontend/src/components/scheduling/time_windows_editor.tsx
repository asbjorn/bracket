import { Button, Group, Stack, Table, Text } from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import dayjs from 'dayjs';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { DayAndTime } from '@components/utils/datetime';
import { TimeField } from '@components/utils/time_fields';
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
  // A field that is empty or still being typed gives no windows instead of an invalid date
  const isTime = (time: string) => /^\d{2}:\d{2}(:\d{2})?$/.test(time);
  if (!isTime(dayStart) || !isTime(dayEnd) || dayStart >= dayEnd) return windows;
  const hasLunch = isTime(lunchStart) && isTime(lunchEnd) && lunchStart < lunchEnd;
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

/**
 * Back from saved windows to the form: first/last day, the hours of the first day and its
 * lunch break (the gap between its two windows, if any).
 */
export function fromSavedWindows(windows: TimeWindowValue[]) {
  const sorted = [...windows].sort((a, b) => a.start_time.localeCompare(b.start_time));
  const dayOf = (moment: string) => dayjs(moment).format('YYYY-MM-DD');
  const timeOf = (moment: string) => dayjs(moment).format('HH:mm');
  const firstDay = dayOf(sorted[0].start_time);
  const firstDayWindows = sorted.filter((w) => dayOf(w.start_time) === firstDay);
  const hasLunch = firstDayWindows.length === 2;
  return {
    firstDay,
    lastDay: dayOf(sorted[sorted.length - 1].start_time),
    dayStart: timeOf(firstDayWindows[0].start_time),
    dayEnd: timeOf(firstDayWindows[firstDayWindows.length - 1].end_time),
    lunchStart: hasLunch ? timeOf(firstDayWindows[0].end_time) : '',
    lunchEnd: hasLunch ? timeOf(firstDayWindows[1].start_time) : '',
  };
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
  const [prefilled, setPrefilled] = useState(false);

  // Start from the saved playing hours (once they are loaded), so changing them is easy
  useEffect(() => {
    if (prefilled || timeWindows.length < 1) return;
    const saved = fromSavedWindows(timeWindows);
    setDays([saved.firstDay, saved.lastDay]);
    setDayStart(saved.dayStart);
    setDayEnd(saved.dayEnd);
    setLunchStart(saved.lunchStart);
    setLunchEnd(saved.lunchEnd);
    setPrefilled(true);
  }, [timeWindows, prefilled]);

  const canSave = days[0] != null && dayStart < dayEnd;

  return (
    <Stack>
      <Text size="sm" c="dimmed">
        {t('time_windows_description')}
      </Text>
      <DatePickerInput
        type="range"
        allowSingleDateInRange
        valueFormat="DD.MM.YYYY"
        label={t('time_windows_days_label')}
        value={days}
        onChange={(value) => setDays(value as [string | null, string | null])}
        maw="24rem"
      />
      <Group>
        <TimeField label={t('time_windows_start_label')} value={dayStart} onChange={setDayStart} />
        <TimeField label={t('time_windows_end_label')} value={dayEnd} onChange={setDayEnd} />
        <TimeField
          label={t('time_windows_lunch_start_label')}
          value={lunchStart}
          onChange={setLunchStart}
          clearable
        />
        <TimeField
          label={t('time_windows_lunch_end_label')}
          value={lunchEnd}
          onChange={setLunchEnd}
          clearable
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
