import {
  Alert,
  Button,
  Group,
  List,
  Modal,
  NumberInput,
  Popover,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
} from '@mantine/core';
import { IconCalendarTime, IconLayoutColumns, IconArrowsJoin } from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { SWRResponse } from 'swr';

import {
  DaysHours,
  DaysHoursFields,
  fromWindows,
  toWindows,
  useHoursSummary,
} from '@components/scheduling/days_hours_editor';
import { GAME_FORMATS } from '@components/scheduling/match_plan_panel';
import { DayAndTime } from '@components/utils/datetime';
import { Court, CourtsResponse, GameFormat, MatchOnCourt } from '@openapi';
import { getPlanningHours, getTimeWindows, requestSucceeded } from '@services/adapter';
import {
  TimeWindowValue,
  createCourts,
  getSplitMatches,
  saveCourtHours,
  splitCourt,
  undoCourtSplit,
} from '@services/planning';

/** The pitches a part belongs to, from the full pitch down: ["Bane 3", "Bane 3A"]. */
function ancestorNames(court: Court, courts: Court[]): string[] {
  const names: string[] = [];
  const seen = new Set<number>();
  let parent = courts.find((other) => other.id === court.parent_court_id);
  while (parent != null && !seen.has(parent.id)) {
    seen.add(parent.id);
    names.unshift(parent.name);
    const current: Court = parent;
    parent = courts.find((other) => other.id === current.parent_court_id);
  }
  return names;
}

/** "Bane 3A1 (del av Bane 3 › Bane 3A)" for a part of a split pitch. */
export function courtLabel(t: any, court: Court, courts: Court[]): string {
  const ancestors = ancestorNames(court, courts);
  return ancestors.length < 1
    ? court.name
    : t('court_part_of', { court: court.name, parent: ancestors.join(' › ') });
}

/** Pitches in tree order (each full pitch followed by its parts), with their depth. */
function courtTree(courts: Court[]): { court: Court; depth: number }[] {
  const byName = (a: Court, b: Court) =>
    a.name.localeCompare(b.name, undefined, { numeric: true }) || a.id - b.id;
  const ids = new Set(courts.map((court) => court.id));
  const result: { court: Court; depth: number }[] = [];
  const add = (court: Court, depth: number) => {
    result.push({ court, depth });
    courts
      .filter((other) => other.parent_court_id === court.id)
      .sort(byName)
      .forEach((child) => add(child, depth + 1));
  };
  courts
    .filter((court) => court.parent_court_id == null || !ids.has(court.parent_court_id))
    .sort(byName)
    .forEach((court) => add(court, 0));
  return result;
}

/** A sensible format for the parts of a pitch: one size smaller. */
function smallerFormat(format: GameFormat | null): GameFormat {
  const smaller: Record<string, GameFormat> = {
    '11v11': '7v7',
    '9v9': '5v5',
    '7v7': '5v5',
    '5v5': '3v3',
  };
  return (format != null ? smaller[format] : undefined) ?? '7v7';
}

function SplitSelect({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const { t } = useTranslation();
  return (
    <Select
      label={t('court_split_label')}
      data={[
        { value: '', label: t('court_split_none') },
        ...[2, 3, 4].map((parts) => ({
          value: `${parts}`,
          label: t('court_split_parts', { count: parts }),
        })),
      ]}
      value={value}
      onChange={(choice) => onChange(choice ?? '')}
      allowDeselect={false}
      w="9rem"
    />
  );
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
  const [splitInto, setSplitInto] = useState('');
  const [partFormat, setPartFormat] = useState<string | null>('7v7');

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
      <SplitSelect value={splitInto} onChange={setSplitInto} />
      {splitInto !== '' ? (
        <Select
          label={t('court_part_format_label')}
          data={GAME_FORMATS}
          value={partFormat}
          onChange={setPartFormat}
          allowDeselect={false}
          w="9rem"
        />
      ) : null}
      <Button
        onClick={async () => {
          const result = await createCourts(
            tournamentId,
            Number(count),
            prefix,
            gameFormat as GameFormat | null,
            splitInto === '' ? null : Number(splitInto),
            splitInto === '' ? null : (partFormat as GameFormat | null),
          );
          if (requestSucceeded(result)) await swrCourtsResponse.mutate();
        }}
      >
        {t('add_courts_button')}
      </Button>
    </Group>
  );
}

function CourtHoursButton({
  tournamentId,
  court,
  cupWindows,
  saved,
  onSaved,
}: {
  tournamentId: number;
  court: Court;
  cupWindows: TimeWindowValue[];
  saved: TimeWindowValue[];
  onSaved: () => Promise<void>;
}) {
  const { t } = useTranslation();
  const summary = useHoursSummary();
  const [opened, setOpened] = useState(false);
  const [hours, setHours] = useState<DaysHours>(fromWindows(cupWindows, saved));
  const current = fromWindows(cupWindows, saved);
  return (
    <Popover opened={opened} onChange={setOpened} width={330} withArrow shadow="md">
      <Popover.Target>
        <Button
          size="xs"
          variant={saved.length > 0 ? 'light' : 'default'}
          leftSection={<IconCalendarTime size={16} />}
          onClick={() => {
            setHours(current);
            setOpened((o) => !o);
          }}
          maw="16rem"
        >
          <Text size="xs" truncate>
            {summary(current)}
          </Text>
        </Button>
      </Popover.Target>
      <Popover.Dropdown>
        <Stack>
          <Text size="xs" c="dimmed">
            {t('court_hours_description')}
          </Text>
          <DaysHoursFields cupWindows={cupWindows} value={hours} onChange={setHours} />
          <Button
            size="xs"
            onClick={async () => {
              const result = await saveCourtHours(
                tournamentId,
                court.id,
                toWindows(cupWindows, hours),
              );
              if (requestSucceeded(result)) {
                setOpened(false);
                await onSaved();
              }
            }}
          >
            {t('save_button')}
          </Button>
        </Stack>
      </Popover.Dropdown>
    </Popover>
  );
}

function SplitCourtButton({
  tournamentId,
  court,
  onSplit,
}: {
  tournamentId: number;
  court: Court;
  onSplit: () => Promise<void>;
}) {
  const { t } = useTranslation();
  const [opened, setOpened] = useState(false);
  const [parts, setParts] = useState('2');
  const [format, setFormat] = useState<string | null>(smallerFormat(court.game_format));
  return (
    <Popover opened={opened} onChange={setOpened} width={300} withArrow shadow="md">
      <Popover.Target>
        <Button
          size="compact-sm"
          variant="subtle"
          leftSection={<IconLayoutColumns size={16} />}
          onClick={() => setOpened((o) => !o)}
        >
          {t('court_split_short_button')}
        </Button>
      </Popover.Target>
      <Popover.Dropdown>
        <Stack>
          <Text size="xs" c="dimmed">
            {t('court_split_description')}
          </Text>
          <Group grow>
            <Select
              label={t('court_split_label')}
              data={[2, 3, 4].map((count) => ({
                value: `${count}`,
                label: t('court_split_parts', { count }),
              }))}
              value={parts}
              onChange={(value) => setParts(value ?? '2')}
              allowDeselect={false}
            />
            <Select
              label={t('court_part_format_label')}
              data={GAME_FORMATS}
              value={format}
              onChange={setFormat}
              allowDeselect={false}
            />
          </Group>
          <Button
            size="xs"
            onClick={async () => {
              const result = await splitCourt(
                tournamentId,
                court.id,
                Number(parts),
                format as GameFormat | null,
              );
              if (requestSucceeded(result)) {
                setOpened(false);
                await onSplit();
              }
            }}
          >
            {t('court_split_button')}
          </Button>
        </Stack>
      </Popover.Dropdown>
    </Popover>
  );
}

function UndoSplitButton({
  tournamentId,
  court,
  courts,
  onUndone,
}: {
  tournamentId: number;
  court: Court;
  courts: Court[];
  onUndone: () => Promise<void>;
}) {
  const { t } = useTranslation();
  const [matches, setMatches] = useState<MatchOnCourt[] | null>(null);
  const [loading, setLoading] = useState(false);
  const parts = courtTree(courts.filter((other) => other.id !== court.id))
    .filter(({ court: part }) => ancestorNames(part, courts).includes(court.name))
    .map(({ court: part }) => part.name);
  const fixed = (matches ?? []).filter((match) => match.played || match.started);

  async function undo(unschedule: boolean) {
    setLoading(true);
    const result = await undoCourtSplit(tournamentId, court.id, unschedule);
    setLoading(false);
    if (requestSucceeded(result)) {
      setMatches(null);
      await onUndone();
    }
  }

  return (
    <>
      <Button
        size="compact-sm"
        variant="subtle"
        color="orange"
        leftSection={<IconArrowsJoin size={16} />}
        onClick={async () => {
          const result = await getSplitMatches(tournamentId, court.id);
          if (requestSucceeded(result) && 'data' in result) setMatches(result.data.data);
        }}
      >
        {t('court_undo_split_button')}
      </Button>
      <Modal
        opened={matches != null}
        onClose={() => setMatches(null)}
        title={t('court_undo_split_title', { court: court.name })}
      >
        <Stack>
          <Text size="sm">{t('court_undo_split_parts', { parts: parts.join(', ') })}</Text>
          {matches != null && matches.length > 0 ? (
            <Alert color={fixed.length > 0 ? 'red' : 'orange'}>
              <Stack gap="xs">
                <Text size="sm">
                  {fixed.length > 0
                    ? t('court_undo_split_blocked', { count: fixed.length })
                    : t('court_undo_split_matches', { count: matches.length })}
                </Text>
                <List size="sm">
                  {matches.slice(0, 12).map((match) => (
                    <List.Item key={match.id}>
                      {match.start_time != null ? <DayAndTime datetime={match.start_time} /> : '–'}
                      {' · '}
                      {match.court_name}
                      {match.played
                        ? ` · ${t('match_played_label')}`
                        : match.started
                          ? ` · ${t('match_started_short')}`
                          : ''}
                    </List.Item>
                  ))}
                </List>
                {matches.length > 12 ? (
                  <Text size="xs" c="dimmed">
                    {t('court_undo_split_more', { count: matches.length - 12 })}
                  </Text>
                ) : null}
              </Stack>
            </Alert>
          ) : null}
          <Group justify="right">
            <Button variant="default" onClick={() => setMatches(null)}>
              {t('cancel_button')}
            </Button>
            {matches != null && matches.length > 0 ? (
              <Button
                color="orange"
                loading={loading}
                disabled={fixed.length > 0}
                onClick={() => undo(true)}
              >
                {t('court_undo_split_unschedule_button')}
              </Button>
            ) : (
              <Button color="orange" loading={loading} onClick={() => undo(false)}>
                {t('court_undo_split_button')}
              </Button>
            )}
          </Group>
        </Stack>
      </Modal>
    </>
  );
}

/** Adding pitches (also split pitches), opening hours per pitch, splitting a pitch. */
export function CourtsPanel({
  tournamentId,
  swrCourtsResponse,
}: {
  tournamentId: number;
  swrCourtsResponse: SWRResponse<CourtsResponse>;
}) {
  const { t } = useTranslation();
  const courts = swrCourtsResponse.data?.data ?? [];
  const cupWindows = getTimeWindows(tournamentId).data?.data ?? [];
  const swrHours = getPlanningHours(tournamentId);
  const hasParts = (court: Court) => courts.some((other) => other.parent_court_id === court.id);
  const refresh = async () => {
    await swrCourtsResponse.mutate();
    await swrHours.mutate();
  };

  return (
    <Stack>
      <AddCourtsForm tournamentId={tournamentId} swrCourtsResponse={swrCourtsResponse} />
      {courts.length > 0 ? (
        <Table.ScrollContainer minWidth={560}>
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('court_name_header')}</Table.Th>
                <Table.Th>{t('game_format_label')}</Table.Th>
                <Table.Th>{t('court_hours_label')}</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {courtTree(courts).map(({ court, depth }) => (
                <Table.Tr key={court.id}>
                  <Table.Td>
                    <Group gap="xs" wrap="nowrap" style={{ paddingLeft: `${depth * 1.25}rem` }}>
                      {depth > 0 ? (
                        <Text c="dimmed" span>
                          ↳
                        </Text>
                      ) : null}
                      <Stack gap={0}>
                        <Text size="sm" fw={depth === 0 ? 600 : 400}>
                          {court.name}
                        </Text>
                        {depth > 0 ? (
                          <Text size="xs" c="dimmed">
                            {t('court_part_badge', {
                              parent: ancestorNames(court, courts).join(' › '),
                            })}
                          </Text>
                        ) : null}
                      </Stack>
                    </Group>
                  </Table.Td>
                  <Table.Td>{court.game_format ?? t('game_format_any')}</Table.Td>
                  <Table.Td>
                    <CourtHoursButton
                      tournamentId={tournamentId}
                      court={court}
                      cupWindows={cupWindows}
                      saved={swrHours.data?.data.courts[`${court.id}`] ?? []}
                      onSaved={refresh}
                    />
                  </Table.Td>
                  <Table.Td>
                    {hasParts(court) ? (
                      <UndoSplitButton
                        tournamentId={tournamentId}
                        court={court}
                        courts={courts}
                        onUndone={refresh}
                      />
                    ) : (
                      <SplitCourtButton
                        tournamentId={tournamentId}
                        court={court}
                        onSplit={refresh}
                      />
                    )}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      ) : null}
    </Stack>
  );
}
