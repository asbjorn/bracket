import {
  ActionIcon,
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
import { useTranslation } from 'react-i18next';

import { GAME_FORMATS } from '@components/scheduling/match_plan_panel';
import { buildTimeWindows } from '@components/scheduling/time_windows_editor';
import { nffPreset } from '@components/utils/nff_presets';
import { TimeField } from '@components/utils/time_fields';
import { CapacityCourts, CapacityResult, CupSetupClass, GameFormat, PlayoffPreset } from '@openapi';
import { TimeWindowValue } from '@services/planning';

// Shared by the capacity calculator and the cup setup wizard: what is calculated is what gets
// created.

const PLAYOFF_PRESETS: PlayoffPreset[] = ['NONE', 'A', 'AB', 'ABC'];
// NFF: results and tables only from the 13-year class (youth football)
const YOUTH_FOOTBALL_MIN_AGE = 13;

export function newClass(name: string, age: number): CupSetupClass {
  const preset = nffPreset(age);
  return {
    name,
    age,
    team_count: 8,
    group_size: 4,
    // NFF: no playoffs in children's football (12 and younger)
    playoffs: age >= YOUTH_FOOTBALL_MIN_AGE ? 'AB' : 'NONE',
    playoff_placings: null,
    third_place_match: false,
    duration_minutes: preset.duration_minutes,
    margin_minutes: preset.margin_minutes,
    min_rest_minutes: 0,
    game_format: preset.game_format,
    results_public: null,
  };
}

export function resultsPublic(value: CupSetupClass): boolean {
  return value.results_public ?? (value.age == null || value.age >= YOUTH_FOOTBALL_MIN_AGE);
}

/** Playoffs are placed by results, so a class with hidden results can't have them. */
export function withAllowedPlayoffs(value: CupSetupClass): CupSetupClass {
  return resultsPublic(value) ? value : { ...value, playoffs: 'NONE', playoff_placings: null };
}

function ClassRow({
  value,
  onChange,
  onRemove,
  withResultsPublic,
}: {
  value: CupSetupClass;
  onChange: (value: CupSetupClass) => void;
  onRemove: () => void;
  withResultsPublic: boolean;
}) {
  const { t } = useTranslation();
  const update = (changes: Partial<CupSetupClass>) => onChange({ ...value, ...changes });
  const number = (field: keyof CupSetupClass) => (input: number | string) =>
    update({ [field]: input === '' ? null : Number(input) } as Partial<CupSetupClass>);
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
            update({
              age,
              results_public: null,
              playoffs: age >= YOUTH_FOOTBALL_MIN_AGE ? 'AB' : 'NONE',
              playoff_placings: null,
              ...nffPreset(age),
            });
          }}
        />
      </Table.Td>
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
          max={10}
          w="5rem"
          onChange={number('group_size')}
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
}: {
  value: CupSetupClass[];
  onChange: (value: CupSetupClass[]) => void;
  withResultsPublic?: boolean;
}) {
  const { t } = useTranslation();
  return (
    <Stack>
      <Table.ScrollContainer minWidth={900}>
        <Table>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{t('name_input_label')}</Table.Th>
              <Table.Th>{t('category_age_input_label')}</Table.Th>
              {withResultsPublic ? <Table.Th>{t('results_public_short_label')}</Table.Th> : null}
              <Table.Th>{t('capacity_teams_header')}</Table.Th>
              <Table.Th>{t('capacity_group_size_header')}</Table.Th>
              <Table.Th>{t('capacity_playoffs_header')}</Table.Th>
              <Table.Th>{t('capacity_bronze_header')}</Table.Th>
              <Table.Th>{t('match_duration_label')}</Table.Th>
              <Table.Th>{t('time_between_matches_label')}</Table.Th>
              <Table.Th>{t('min_rest_label')}</Table.Th>
              <Table.Th>{t('game_format_label')}</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {value.map((item, index) => (
              <ClassRow
                key={index}
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
        <Group key={index} align="end">
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
      <Group>
        <Button
          variant="light"
          onClick={() => onChange([...value, { count: 1, game_format: null }])}
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
