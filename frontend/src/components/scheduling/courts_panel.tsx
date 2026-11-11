import {
  ActionIcon,
  Badge,
  Button,
  Group,
  NumberInput,
  Popover,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Tooltip,
} from '@mantine/core';
import { IconCalendarTime, IconLayoutColumns } from '@tabler/icons-react';
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
import { Court, CourtsResponse, GameFormat } from '@openapi';
import { getPlanningHours, getTimeWindows, requestSucceeded } from '@services/adapter';
import { TimeWindowValue, createCourts, saveCourtHours, splitCourt } from '@services/planning';

/** "Bane 1A (del av Bane 1)" for a part of a split pitch. */
export function courtLabel(t: any, court: Court, courts: Court[]): string {
  const parent = courts.find((other) => other.id === court.parent_court_id);
  return parent == null
    ? court.name
    : t('court_part_of', { court: court.name, parent: parent.name });
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
  const [format, setFormat] = useState<string | null>('7v7');
  return (
    <Popover opened={opened} onChange={setOpened} width={300} withArrow shadow="md">
      <Popover.Target>
        <Tooltip label={t('court_split_button')}>
          <ActionIcon
            variant="subtle"
            aria-label={t('court_split_button')}
            onClick={() => setOpened((o) => !o)}
          >
            <IconLayoutColumns size={18} />
          </ActionIcon>
        </Tooltip>
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
              {courts.map((court) => (
                <Table.Tr key={court.id}>
                  <Table.Td>
                    <Group gap="xs">
                      {court.name}
                      {court.parent_court_id != null ? (
                        <Badge size="sm" variant="light" color="gray">
                          {t('court_part_badge', {
                            parent: courts.find((c) => c.id === court.parent_court_id)?.name ?? '',
                          })}
                        </Badge>
                      ) : null}
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
                    {court.parent_court_id == null && !hasParts(court) ? (
                      <SplitCourtButton
                        tournamentId={tournamentId}
                        court={court}
                        onSplit={refresh}
                      />
                    ) : null}
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
