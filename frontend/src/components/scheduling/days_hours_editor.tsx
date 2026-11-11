import { Button, Checkbox, Group, Popover, Stack, Text } from '@mantine/core';
import { IconCalendarTime } from '@tabler/icons-react';
import dayjs from 'dayjs';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { TimeField } from '@components/utils/time_fields';
import { TimeWindowValue } from '@services/planning';

// Days and hours of a pitch or a class are built from the cup's playing hours: the chosen days,
// optionally limited to a from/to time. No days chosen: the cup's playing hours (empty list).

const TIME = /^\d{2}:\d{2}(:\d{2})?$/;

function dayOf(moment: string) {
  return dayjs(moment).format('YYYY-MM-DD');
}

function timeOf(moment: string) {
  return dayjs(moment).format('HH:mm');
}

/** The days of the cup (local dates), in order. */
export function cupDays(cupWindows: TimeWindowValue[]): string[] {
  return [...new Set(cupWindows.map((w) => dayOf(w.start_time)))].sort();
}

export interface DaysHours {
  days: string[];
  from: string;
  to: string;
}

export const ALL_DAYS: DaysHours = { days: [], from: '', to: '' };

/** The windows for the chosen days and hours, clipped to the cup's playing hours. */
export function toWindows(cupWindows: TimeWindowValue[], value: DaysHours): TimeWindowValue[] {
  if (value.days.length < 1) return [];
  const windows: TimeWindowValue[] = [];
  for (const cup of cupWindows) {
    const day = dayOf(cup.start_time);
    if (!value.days.includes(day)) continue;
    let start = dayjs(cup.start_time);
    let end = dayjs(cup.end_time);
    if (TIME.test(value.from)) {
      const from = dayjs(`${day}T${value.from}`);
      if (from.isAfter(start)) start = from;
    }
    if (TIME.test(value.to)) {
      const to = dayjs(`${day}T${value.to}`);
      if (to.isBefore(end)) end = to;
    }
    if (start.isBefore(end)) {
      windows.push({ start_time: start.toISOString(), end_time: end.toISOString() });
    }
  }
  return windows;
}

/** Back from saved windows to days and hours (from/to only when they limit the cup's hours). */
export function fromWindows(cupWindows: TimeWindowValue[], windows: TimeWindowValue[]): DaysHours {
  if (windows.length < 1) return ALL_DAYS;
  const days = [...new Set(windows.map((w) => dayOf(w.start_time)))].sort();
  const from = windows.map((w) => timeOf(w.start_time)).sort()[0];
  const to = windows
    .map((w) => timeOf(w.end_time))
    .sort()
    .reverse()[0];
  const cupFrom = cupWindows.map((w) => timeOf(w.start_time)).sort()[0];
  const cupTo = cupWindows
    .map((w) => timeOf(w.end_time))
    .sort()
    .reverse()[0];
  return { days, from: from === cupFrom ? '' : from, to: to === cupTo ? '' : to };
}

export function useDayLabel() {
  const { i18n } = useTranslation();
  return (day: string) =>
    new Intl.DateTimeFormat(i18n.resolvedLanguage ?? 'nb', {
      weekday: 'short',
      day: 'numeric',
      month: 'numeric',
    }).format(new Date(`${day}T12:00:00`));
}

/** A short text, e.g. "lør. 21.11, 10:00–14:00" or "Alle dager". */
export function useHoursSummary() {
  const { t } = useTranslation();
  const dayLabel = useDayLabel();
  return (value: DaysHours) => {
    if (value.days.length < 1) return t('hours_all_days');
    const days = value.days.map(dayLabel).join(', ');
    if (value.from === '' && value.to === '') return days;
    return `${days}, ${value.from || '…'}–${value.to || '…'}`;
  };
}

export function DaysHoursFields({
  cupWindows,
  value,
  onChange,
}: {
  cupWindows: TimeWindowValue[];
  value: DaysHours;
  onChange: (value: DaysHours) => void;
}) {
  const { t } = useTranslation();
  const dayLabel = useDayLabel();
  const days = cupDays(cupWindows);
  if (days.length < 1) {
    return (
      <Text size="sm" c="dimmed">
        {t('hours_need_cup_hours')}
      </Text>
    );
  }
  return (
    <Stack gap="xs">
      <Text size="sm" fw={500}>
        {t('hours_days_label')}
      </Text>
      <Group gap="xs">
        {days.map((day) => (
          <Checkbox
            key={day}
            label={dayLabel(day)}
            checked={value.days.includes(day)}
            onChange={(event) =>
              onChange({
                ...value,
                days: event.currentTarget.checked
                  ? [...value.days, day].sort()
                  : value.days.filter((other) => other !== day),
              })
            }
          />
        ))}
      </Group>
      <Text size="xs" c="dimmed">
        {t('hours_days_description')}
      </Text>
      <Group grow>
        <TimeField
          label={t('hours_from_label')}
          value={value.from}
          onChange={(from) => onChange({ ...value, from })}
          clearable
          disabled={value.days.length < 1}
        />
        <TimeField
          label={t('hours_to_label')}
          value={value.to}
          onChange={(to) => onChange({ ...value, to })}
          clearable
          disabled={value.days.length < 1}
        />
      </Group>
    </Stack>
  );
}

/** A button with the current days/hours that opens the editor in a popover. */
export function DaysHoursButton({
  cupWindows,
  value,
  onChange,
}: {
  cupWindows: TimeWindowValue[];
  value: DaysHours;
  onChange: (value: DaysHours) => void;
}) {
  const summary = useHoursSummary();
  const [opened, setOpened] = useState(false);
  return (
    <Popover
      opened={opened}
      onChange={setOpened}
      width={320}
      position="bottom"
      withArrow
      shadow="md"
    >
      <Popover.Target>
        <Button
          variant={value.days.length > 0 ? 'light' : 'default'}
          size="xs"
          leftSection={<IconCalendarTime size={16} />}
          onClick={() => setOpened((o) => !o)}
          maw="14rem"
        >
          <Text size="xs" truncate>
            {summary(value)}
          </Text>
        </Button>
      </Popover.Target>
      <Popover.Dropdown>
        <DaysHoursFields cupWindows={cupWindows} value={value} onChange={onChange} />
      </Popover.Dropdown>
    </Popover>
  );
}
