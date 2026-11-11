import {
  ActionIcon,
  Alert,
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
  Title,
} from '@mantine/core';
import { DatePickerInput, TimeInput } from '@mantine/dates';
import { IconCalculator, IconInfoCircle, IconTrash } from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { GAME_FORMATS, ProposalReport } from '@components/scheduling/match_plan_panel';
import { buildTimeWindows } from '@components/scheduling/time_windows_editor';
import { nffPreset } from '@components/utils/nff_presets';
import { CapacityClass, CapacityCourts, CapacityResult, GameFormat, PlayoffPreset } from '@openapi';
import { requestSucceeded } from '@services/adapter';
import { calculateCapacity } from '@services/capacity';
import Layout from './_layout';

const PLAYOFF_PRESETS: PlayoffPreset[] = ['NONE', 'A', 'AB', 'ABC'];

function newClass(name: string, age: number): CapacityClass {
  const preset = nffPreset(age);
  return {
    name,
    age,
    team_count: 8,
    group_size: 4,
    // NFF: no playoffs in children's football (12 and younger)
    playoffs: age >= 13 ? 'AB' : 'NONE',
    playoff_placings: null,
    third_place_match: false,
    duration_minutes: preset.duration_minutes,
    margin_minutes: preset.margin_minutes,
    min_rest_minutes: 0,
    game_format: preset.game_format,
  };
}

function ClassRow({
  value,
  onChange,
  onRemove,
}: {
  value: CapacityClass;
  onChange: (value: CapacityClass) => void;
  onRemove: () => void;
}) {
  const { t } = useTranslation();
  const update = (changes: Partial<CapacityClass>) => onChange({ ...value, ...changes });
  const number = (field: keyof CapacityClass) => (input: number | string) =>
    update({ [field]: input === '' ? null : Number(input) } as Partial<CapacityClass>);

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
              update({ age: null });
              return;
            }
            // Follow the NFF suggestions for the new age
            const preset = nffPreset(Number(input));
            update({ age: Number(input), ...preset });
          }}
        />
      </Table.Td>
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
          value={value.playoffs}
          onChange={(preset) => update({ playoffs: (preset ?? 'NONE') as PlayoffPreset })}
          allowDeselect={false}
          w="9rem"
        />
      </Table.Td>
      <Table.Td>
        <Checkbox
          checked={value.third_place_match}
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

function ClassResults({ result }: { result: CapacityResult }) {
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

export default function CapacityPage() {
  const { t } = useTranslation();
  const [classes, setClasses] = useState<CapacityClass[]>([
    newClass('G10', 10),
    newClass('J14', 14),
  ]);
  const [courts, setCourts] = useState<CapacityCourts[]>([
    { count: 2, game_format: '7v7' },
    { count: 1, game_format: '11v11' },
  ]);
  const [days, setDays] = useState<[string | null, string | null]>([null, null]);
  const [dayStart, setDayStart] = useState('09:00');
  const [dayEnd, setDayEnd] = useState('17:00');
  const [lunchStart, setLunchStart] = useState('12:00');
  const [lunchEnd, setLunchEnd] = useState('12:45');
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
        <Table.ScrollContainer minWidth={900}>
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('name_input_label')}</Table.Th>
                <Table.Th>{t('category_age_input_label')}</Table.Th>
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
              {classes.map((value, index) => (
                <ClassRow
                  key={index}
                  value={value}
                  onChange={(changed) =>
                    setClasses(classes.map((item, i) => (i === index ? changed : item)))
                  }
                  onRemove={() => setClasses(classes.filter((_, i) => i !== index))}
                />
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
        <Group>
          <Button
            variant="light"
            onClick={() => setClasses([...classes, newClass(`K${classes.length + 1}`, 12)])}
          >
            {t('add_category_title')}
          </Button>
        </Group>

        <Title order={3}>{t('add_courts_title')}</Title>
        {courts.map((group, index) => (
          <Group key={index} align="end">
            <NumberInput
              label={t('court_count_label')}
              value={group.count}
              min={1}
              max={64}
              w="8rem"
              onChange={(input) =>
                setCourts(courts.map((c, i) => (i === index ? { ...c, count: Number(input) } : c)))
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
                setCourts(
                  courts.map((c, i) =>
                    i === index ? { ...c, game_format: format as GameFormat | null } : c,
                  ),
                )
              }
            />
            <ActionIcon
              variant="subtle"
              color="red"
              size="lg"
              disabled={courts.length < 2}
              onClick={() => setCourts(courts.filter((_, i) => i !== index))}
            >
              <IconTrash size={18} />
            </ActionIcon>
          </Group>
        ))}
        <Group>
          <Button
            variant="light"
            onClick={() => setCourts([...courts, { count: 1, game_format: null }])}
          >
            {t('add_courts_button')}
          </Button>
        </Group>

        <Title order={3}>{t('time_windows_title')}</Title>
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
            onChange={(e) => setDayStart(e.currentTarget.value)}
          />
          <TimeInput
            label={t('time_windows_end_label')}
            value={dayEnd}
            onChange={(e) => setDayEnd(e.currentTarget.value)}
          />
          <TimeInput
            label={t('time_windows_lunch_start_label')}
            value={lunchStart}
            onChange={(e) => setLunchStart(e.currentTarget.value)}
          />
          <TimeInput
            label={t('time_windows_lunch_end_label')}
            value={lunchEnd}
            onChange={(e) => setLunchEnd(e.currentTarget.value)}
          />
          <NumberInput
            label={t('stage_buffer_label')}
            value={stageBuffer}
            min={0}
            onChange={setStageBuffer}
            w="14rem"
          />
        </Group>

        <Group>
          <Button
            size="md"
            color="indigo"
            loading={loading}
            disabled={days[0] == null || classes.length < 1}
            leftSection={<IconCalculator size={22} />}
            onClick={async () => {
              setLoading(true);
              const response = await calculateCapacity({
                classes,
                courts,
                time_windows: buildTimeWindows(
                  days[0] ?? '',
                  days[1] ?? days[0] ?? '',
                  dayStart,
                  dayEnd,
                  lunchStart,
                  lunchEnd,
                ),
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
