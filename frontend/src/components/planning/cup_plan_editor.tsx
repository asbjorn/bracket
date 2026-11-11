import {
  ActionIcon,
  Badge,
  Button,
  Checkbox,
  Group,
  List,
  NumberInput,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
} from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { IconTrash } from '@tabler/icons-react';
import dayjs from 'dayjs';
import { useTranslation } from 'react-i18next';

import { GAME_FORMATS } from '@components/scheduling/match_plan_panel';
import { buildTimeWindows } from '@components/scheduling/time_windows_editor';
import {
  ALL_DAYS,
  DaysHours,
  DaysHoursButton,
  toWindows,
  useDayLabel,
} from '@components/scheduling/days_hours_editor';
import {
  defaultMaxMatchesPerDay,
  defaultRestMinutes,
  nffPreset,
} from '@components/utils/nff_presets';
import { TimeField } from '@components/utils/time_fields';
import {
  CapacityCourts,
  CapacityResult,
  CategoryKind,
  CupSetupClass,
  GameFormat,
  PlayoffPreset,
} from '@openapi';
import { TimeWindowValue } from '@services/planning';

// Shared by the capacity calculator and the cup setup wizard: what is calculated is what gets
// created.

const PLAYOFF_PRESETS: PlayoffPreset[] = ['NONE', 'A', 'AB', 'ABC'];
// NFF: results and tables only from the 13-year class (youth football)
const YOUTH_FOOTBALL_MIN_AGE = 13;

/** A class as edited: its days/hours are kept as days + times and turned into windows at the end. */
export type PlanClass = CupSetupClass & { hours: DaysHours };

const KIND_LETTER: Record<CategoryKind, string> = { BOYS: 'G', GIRLS: 'J', MIXED: 'M' };
const LETTER_KIND: Record<string, CategoryKind> = { G: 'BOYS', J: 'GIRLS', M: 'MIXED' };

/** A name like "G10": the letter of the kind (G boys, J girls, M mixed) and the age. */
const AUTO_NAME = /^([GJKMgjkm])(\d+)$/;

export function kindOfName(name: string): CategoryKind | null {
  const match = name.match(AUTO_NAME);
  return match != null ? (LETTER_KIND[match[1].toUpperCase()] ?? null) : null;
}

export function newClass(name: string, age: number): PlanClass {
  const preset = nffPreset(age);
  return {
    name,
    kind: kindOfName(name),
    age,
    team_count: 8,
    group_size: 4,
    // NFF: no playoffs in children's football (12 and younger)
    playoffs: age >= YOUTH_FOOTBALL_MIN_AGE ? 'AB' : 'NONE',
    playoff_placings: null,
    third_place_match: false,
    duration_minutes: preset.duration_minutes,
    margin_minutes: preset.margin_minutes,
    min_rest_minutes: defaultRestMinutes(age),
    game_format: preset.game_format,
    results_public: null,
    max_matches_per_day: null,
    time_windows: [],
    hours: ALL_DAYS,
  };
}

export function resultsPublic(value: CupSetupClass): boolean {
  return value.results_public ?? (value.age == null || value.age >= YOUTH_FOOTBALL_MIN_AGE);
}

/** Playoffs are placed by results, so a class with hidden results can't have them. */
export function withAllowedPlayoffs(value: CupSetupClass): CupSetupClass {
  return resultsPublic(value) ? value : { ...value, playoffs: 'NONE', playoff_placings: null };
}

/** The class for the API: days/hours as time windows within the cup's playing hours. */
export function toApiClass(value: PlanClass, cupWindows: TimeWindowValue[]): CupSetupClass {
  const { hours, ...rest } = value;
  return withAllowedPlayoffs({ ...rest, time_windows: toWindows(cupWindows, hours) });
}

export function groupSizeError(value: CupSetupClass): boolean {
  return value.group_size > value.team_count;
}

function groupSizes(teams: number, groupSize: number): number[] {
  const groups = Math.max(1, Math.ceil(teams / groupSize));
  const base = Math.floor(teams / groups);
  const extra = teams % groups;
  return Array.from({ length: groups }, (_, index) => (index < extra ? base + 1 : base));
}

/** Roughly how many matches a class plays (groups plus playoffs), for default courts. */
export function estimateMatches(value: CupSetupClass): number {
  const sizes = groupSizes(value.team_count, Math.min(value.group_size, value.team_count));
  const groupMatches = sizes.reduce((sum, size) => sum + (size * (size - 1)) / 2, 0);
  const playoffs = { NONE: 0, A: 1, AB: 2, ABC: 3 }[value.playoffs] ?? 0;
  // Every playoff of n teams has n - 1 matches; together the playoffs hold all teams
  const playoffMatches = playoffs > 0 ? Math.max(0, value.team_count - playoffs) : 0;
  return groupMatches + playoffMatches;
}

/**
 * Courts for the classes: one group per game format, enough for the playing hours with some
 * room to spare. The overview then shows whether everything fits.
 */
export function defaultCourts(
  classes: PlanClass[],
  cupWindows: TimeWindowValue[],
): CapacityCourts[] {
  const cupMinutes = cupWindows.reduce(
    (sum, w) => sum + dayjs(w.end_time).diff(dayjs(w.start_time), 'minute'),
    0,
  );
  const minutesPerFormat = new Map<GameFormat | null, number>();
  for (const value of classes) {
    const windows = toWindows(cupWindows, value.hours);
    const available =
      windows.length > 0
        ? windows.reduce((sum, w) => sum + dayjs(w.end_time).diff(dayjs(w.start_time), 'minute'), 0)
        : cupMinutes;
    const needed = estimateMatches(value) * (value.duration_minutes + value.margin_minutes);
    // Courts needed if the class had the courts to itself, in its own hours
    const share = available > 0 ? needed / available : needed;
    minutesPerFormat.set(value.game_format, (minutesPerFormat.get(value.game_format) ?? 0) + share);
  }
  return [...minutesPerFormat.entries()].map(([game_format, courts]) => ({
    count: Math.min(32, Math.max(1, Math.ceil(courts * 1.2))),
    game_format,
    split_into: null,
    part_format: null,
  }));
}

function ClassRow({
  value,
  onChange,
  onRemove,
  withResultsPublic,
  cupWindows,
}: {
  value: PlanClass;
  onChange: (value: PlanClass) => void;
  onRemove: () => void;
  withResultsPublic: boolean;
  cupWindows: TimeWindowValue[] | null;
}) {
  const { t } = useTranslation();
  const update = (changes: Partial<PlanClass>) => onChange({ ...value, ...changes });
  const number = (field: keyof PlanClass) => (input: number | string) =>
    update({ [field]: input === '' ? null : Number(input) } as Partial<PlanClass>);
  const playoffsAllowed = !withResultsPublic || resultsPublic(value);

  return (
    <Table.Tr>
      <Table.Td>
        <TextInput
          value={value.name}
          onChange={(event) => update({ name: event.currentTarget.value })}
          w="6rem"
        />
      </Table.Td>
      <Table.Td>
        <NumberInput
          value={value.age ?? ''}
          min={4}
          max={99}
          w="5rem"
          onChange={(input) => {
            if (input === '') {
              update({ age: null, results_public: null });
              return;
            }
            // Follow the NFF suggestions for the new age, playoffs included
            const age = Number(input);
            // A name like "G10" follows the age ("G9"); a name of its own is kept
            const autoName = value.name.match(AUTO_NAME);
            const followsAge = autoName != null && Number(autoName[2]) === value.age;
            update({
              name: followsAge ? `${autoName[1]}${age}` : value.name,
              age,
              results_public: null,
              playoffs: age >= YOUTH_FOOTBALL_MIN_AGE ? 'AB' : 'NONE',
              playoff_placings: null,
              min_rest_minutes: defaultRestMinutes(age),
              ...nffPreset(age),
            });
          }}
        />
      </Table.Td>
      {withResultsPublic ? (
        <Table.Td>
          <Select
            data={(['BOYS', 'GIRLS', 'MIXED'] as CategoryKind[]).map((kind) => ({
              value: kind,
              label: t(`category_kind_${kind.toLowerCase()}`),
            }))}
            value={value.kind}
            placeholder="–"
            clearable
            w="7rem"
            onChange={(selected) => {
              const kind = selected as CategoryKind | null;
              // An automatic name follows the kind: "G10" becomes "J10" for girls
              const autoName = value.name.match(AUTO_NAME);
              update({
                kind,
                name:
                  autoName != null && kind != null
                    ? `${KIND_LETTER[kind]}${autoName[2]}`
                    : value.name,
              });
            }}
          />
        </Table.Td>
      ) : null}
      {withResultsPublic ? (
        <Table.Td>
          <Checkbox
            checked={resultsPublic(value)}
            onChange={(event) => update({ results_public: event.currentTarget.checked })}
          />
        </Table.Td>
      ) : null}
      <Table.Td>
        <NumberInput
          value={value.team_count}
          min={2}
          max={128}
          w="5rem"
          onChange={number('team_count')}
        />
      </Table.Td>
      <Table.Td>
        <NumberInput
          value={value.group_size}
          min={2}
          max={Math.min(10, Math.max(2, value.team_count))}
          w="5rem"
          onChange={number('group_size')}
          error={groupSizeError(value) ? t('group_size_too_large_error') : undefined}
        />
      </Table.Td>
      <Table.Td>
        <Select
          data={PLAYOFF_PRESETS.map((preset) => ({
            value: preset,
            label: t(`playoff_preset_${preset.toLowerCase()}`),
          }))}
          value={playoffsAllowed ? value.playoffs : 'NONE'}
          disabled={!playoffsAllowed}
          onChange={(preset) => update({ playoffs: (preset ?? 'NONE') as PlayoffPreset })}
          allowDeselect={false}
          w="9rem"
        />
      </Table.Td>
      <Table.Td>
        <Checkbox
          checked={playoffsAllowed && value.third_place_match}
          disabled={!playoffsAllowed}
          onChange={(event) => update({ third_place_match: event.currentTarget.checked })}
        />
      </Table.Td>
      <Table.Td>
        <NumberInput
          value={value.duration_minutes}
          min={1}
          w="5rem"
          onChange={number('duration_minutes')}
        />
      </Table.Td>
      <Table.Td>
        <NumberInput
          value={value.margin_minutes}
          min={0}
          w="5rem"
          onChange={number('margin_minutes')}
        />
      </Table.Td>
      <Table.Td>
        <NumberInput
          value={value.min_rest_minutes}
          min={0}
          w="5rem"
          onChange={number('min_rest_minutes')}
        />
      </Table.Td>
      <Table.Td>
        <Select
          data={GAME_FORMATS}
          value={value.game_format}
          onChange={(format) => update({ game_format: format as GameFormat | null })}
          placeholder={t('game_format_any')}
          clearable
          w="7rem"
        />
      </Table.Td>
      <Table.Td>
        <NumberInput
          value={value.max_matches_per_day ?? ''}
          min={1}
          max={20}
          w="5rem"
          placeholder={`${defaultMaxMatchesPerDay(value.age) ?? '–'}`}
          onChange={number('max_matches_per_day')}
        />
      </Table.Td>
      {cupWindows != null ? (
        <Table.Td>
          <DaysHoursButton
            cupWindows={cupWindows}
            value={value.hours}
            onChange={(hours) => update({ hours })}
          />
        </Table.Td>
      ) : null}
      <Table.Td>
        <ActionIcon variant="subtle" color="red" onClick={onRemove}>
          <IconTrash size={18} />
        </ActionIcon>
      </Table.Td>
    </Table.Tr>
  );
}

export function ClassesEditor({
  value,
  onChange,
  withResultsPublic = false,
  cupWindows = null,
}: {
  value: PlanClass[];
  onChange: (value: PlanClass[]) => void;
  withResultsPublic?: boolean;
  // The cup's playing hours, for choosing days/hours per class (`null`: not shown)
  cupWindows?: TimeWindowValue[] | null;
}) {
  const { t } = useTranslation();
  return (
    <Stack>
      <Table.ScrollContainer minWidth={1150}>
        <Table>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{t('name_input_label')}</Table.Th>
              <Table.Th>{t('category_age_input_label')}</Table.Th>
              {withResultsPublic ? <Table.Th>{t('category_kind_label')}</Table.Th> : null}
              {withResultsPublic ? <Table.Th>{t('results_public_short_label')}</Table.Th> : null}
              <Table.Th>{t('capacity_teams_header')}</Table.Th>
              <Table.Th>{t('capacity_group_size_header')}</Table.Th>
              <Table.Th>{t('capacity_playoffs_header')}</Table.Th>
              <Table.Th>{t('capacity_bronze_header')}</Table.Th>
              <Table.Th>{t('match_duration_label')}</Table.Th>
              <Table.Th>{t('time_between_matches_label')}</Table.Th>
              <Table.Th>{t('min_rest_label')}</Table.Th>
              <Table.Th>{t('game_format_label')}</Table.Th>
              <Table.Th>{t('max_matches_per_day_short_label')}</Table.Th>
              {cupWindows != null ? <Table.Th>{t('class_hours_label')}</Table.Th> : null}
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {value.map((item, index) => (
              <ClassRow
                key={index}
                cupWindows={cupWindows}
                value={item}
                withResultsPublic={withResultsPublic}
                onChange={(changed) => onChange(value.map((c, i) => (i === index ? changed : c)))}
                onRemove={() => onChange(value.filter((_, i) => i !== index))}
              />
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
      {withResultsPublic && value.some((item) => !resultsPublic(item)) ? (
        <Text size="sm" c="dimmed">
          {t('setup_hidden_results_note')}
        </Text>
      ) : null}
      <Group>
        <Button
          variant="light"
          onClick={() => onChange([...value, newClass(`K${value.length + 1}`, 12)])}
        >
          {t('add_category_title')}
        </Button>
      </Group>
    </Stack>
  );
}

export function CourtsEditor({
  value,
  onChange,
}: {
  value: CapacityCourts[];
  onChange: (value: CapacityCourts[]) => void;
}) {
  const { t } = useTranslation();
  return (
    <Stack>
      {value.map((group, index) => (
        <Group key={index} align="end" wrap="wrap">
          <NumberInput
            label={t('court_count_label')}
            value={group.count}
            min={1}
            max={32}
            w="8rem"
            onChange={(input) =>
              onChange(value.map((c, i) => (i === index ? { ...c, count: Number(input) } : c)))
            }
          />
          <Select
            label={t('game_format_label')}
            data={GAME_FORMATS}
            value={group.game_format}
            placeholder={t('game_format_any')}
            clearable
            w="10rem"
            onChange={(format) =>
              onChange(
                value.map((c, i) =>
                  i === index ? { ...c, game_format: format as GameFormat | null } : c,
                ),
              )
            }
          />
          <Select
            label={t('court_split_label')}
            data={[
              { value: '', label: t('court_split_none') },
              ...[2, 3, 4].map((parts) => ({
                value: `${parts}`,
                label: t('court_split_parts', { count: parts }),
              })),
            ]}
            value={group.split_into != null ? `${group.split_into}` : ''}
            allowDeselect={false}
            w="9rem"
            onChange={(parts) =>
              onChange(
                value.map((c, i) =>
                  i === index
                    ? {
                        ...c,
                        split_into: parts ? Number(parts) : null,
                        part_format: parts ? (c.part_format ?? '7v7') : null,
                      }
                    : c,
                ),
              )
            }
          />
          {group.split_into != null ? (
            <Select
              label={t('court_part_format_label')}
              data={GAME_FORMATS}
              value={group.part_format}
              allowDeselect={false}
              w="9rem"
              onChange={(format) =>
                onChange(
                  value.map((c, i) =>
                    i === index ? { ...c, part_format: format as GameFormat | null } : c,
                  ),
                )
              }
            />
          ) : null}
          <ActionIcon
            variant="subtle"
            color="red"
            size="lg"
            disabled={value.length < 2}
            onClick={() => onChange(value.filter((_, i) => i !== index))}
          >
            <IconTrash size={18} />
          </ActionIcon>
        </Group>
      ))}
      <Text size="xs" c="dimmed">
        {t('court_split_description')}
      </Text>
      <Group>
        <Button
          variant="light"
          onClick={() =>
            onChange([
              ...value,
              { count: 1, game_format: null, split_into: null, part_format: null },
            ])
          }
        >
          {t('add_courts_button')}
        </Button>
      </Group>
    </Stack>
  );
}

export interface PlayingDays {
  days: [string | null, string | null];
  dayStart: string;
  dayEnd: string;
  lunchStart: string;
  lunchEnd: string;
}

export const DEFAULT_PLAYING_DAYS: PlayingDays = {
  days: [null, null],
  dayStart: '09:00',
  dayEnd: '17:00',
  lunchStart: '12:00',
  lunchEnd: '12:45',
};

export function toTimeWindows(value: PlayingDays): TimeWindowValue[] {
  const [firstDay, lastDay] = value.days;
  if (firstDay == null) return [];
  return buildTimeWindows(
    firstDay,
    lastDay ?? firstDay,
    value.dayStart,
    value.dayEnd,
    value.lunchStart,
    value.lunchEnd,
  );
}

export function PlayingDaysEditor({
  value,
  onChange,
}: {
  value: PlayingDays;
  onChange: (value: PlayingDays) => void;
}) {
  const { t } = useTranslation();
  const time = (field: keyof PlayingDays) => (input: string) =>
    onChange({ ...value, [field]: input });
  return (
    <Stack>
      <DatePickerInput
        type="range"
        allowSingleDateInRange
        valueFormat="DD.MM.YYYY"
        label={t('time_windows_days_label')}
        value={value.days}
        onChange={(days) => onChange({ ...value, days: days as [string | null, string | null] })}
        maw="24rem"
      />
      <Group>
        <TimeField
          label={t('time_windows_start_label')}
          value={value.dayStart}
          onChange={time('dayStart')}
        />
        <TimeField
          label={t('time_windows_end_label')}
          value={value.dayEnd}
          onChange={time('dayEnd')}
        />
        <TimeField
          label={t('time_windows_lunch_start_label')}
          value={value.lunchStart}
          onChange={time('lunchStart')}
          clearable
        />
        <TimeField
          label={t('time_windows_lunch_end_label')}
          value={value.lunchEnd}
          onChange={time('lunchEnd')}
          clearable
        />
      </Group>
    </Stack>
  );
}

/** How the planned matches are spread over the days, e.g. "fre. 20.11: 24 kamper". */
export function MatchesPerDay({ result }: { result: CapacityResult }) {
  const { t } = useTranslation();
  const dayLabel = useDayLabel();
  if (result.matches_per_day.length < 1) return null;
  return (
    <Group gap="xs">
      <Text size="sm" fw={500}>
        {t('matches_per_day_label')}
      </Text>
      {result.matches_per_day.map((day) => (
        <Badge key={day.day} variant="light" size="lg">
          {dayLabel(day.day)}: {t('matches_count', { count: day.matches })}
        </Badge>
      ))}
    </Group>
  );
}

export function ClassResults({ result }: { result: CapacityResult }) {
  const { t } = useTranslation();
  return (
    <Table>
      <Table.Thead>
        <Table.Tr>
          <Table.Th>{t('category_select_label')}</Table.Th>
          <Table.Th>{t('capacity_groups_header')}</Table.Th>
          <Table.Th>{t('capacity_matches_header')}</Table.Th>
          <Table.Th>{t('capacity_matches_per_team_header')}</Table.Th>
          <Table.Th>{t('nff_rules_table_header')}</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {result.classes.map((item) => (
          <Table.Tr key={item.name}>
            <Table.Td>{item.name}</Table.Td>
            <Table.Td>{item.group_sizes.join(' + ')}</Table.Td>
            <Table.Td>
              {item.group_matches}
              {item.playoff_matches > 0
                ? ` + ${item.playoff_matches} (${item.playoff_team_counts.join(', ')})`
                : ''}
            </Table.Td>
            <Table.Td>
              {item.min_matches_per_team === item.max_matches_per_team
                ? item.min_matches_per_team
                : `${item.min_matches_per_team}–${item.max_matches_per_team}`}
              {item.max_matches_per_team_per_day > 0 ? (
                <Text size="xs" c="dimmed">
                  {t('max_per_day_in_plan', { count: item.max_matches_per_team_per_day })}
                </Text>
              ) : null}
            </Table.Td>
            <Table.Td>
              {item.warnings.length < 1 ? (
                t('no_warnings_badge')
              ) : (
                <List size="sm">
                  {item.warnings.map((warning) => (
                    <List.Item key={warning}>
                      {t(`capacity_warning_${warning.toLowerCase()}`)}
                    </List.Item>
                  ))}
                </List>
              )}
            </Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}
