import {
  Alert,
  Badge,
  Button,
  Checkbox,
  Group,
  Modal,
  Select,
  Stack,
  Table,
  Text,
} from '@mantine/core';
import { Dropzone } from '@mantine/dropzone';
import { IconDownload, IconFileSpreadsheet, IconFileUpload } from '@tabler/icons-react';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { SWRResponse } from 'swr';

import { normalizeName, parseCsv } from '@components/utils/csv';
import { FullTeamWithPlayers, PlayerImportResult, PlayersResponse } from '@openapi';
import { getAllPlayers, getAllTeams, requestSucceeded } from '@services/adapter';
import { PlayerImportRowValue, importPlayers } from '@services/player';

const MAX_NAME_LENGTH = 100;
const MAX_ROWS = 2000;

const NAME_HEADERS = ['navn', 'name', 'spiller', 'player', 'fullt navn', 'full name'];
const FIRST_NAME_HEADERS = ['fornavn', 'first name', 'firstname'];
const LAST_NAME_HEADERS = ['etternavn', 'last name', 'lastname', 'surname'];
const TEAM_HEADERS = ['lag', 'team'];
const ACTIVE_HEADERS = ['aktiv', 'active'];
const NO_VALUES = ['nei', 'no', 'false', '0', 'n'];

type RowStatus = 'new' | 'exists' | 'duplicate' | 'invalid';

interface PreviewRow {
  line: number;
  name: string;
  teamText: string;
  team: FullTeamWithPlayers | null;
  active: boolean | null;
  status: RowStatus;
  reason: string | null;
}

interface Columns {
  name: number | null;
  firstName: number | null;
  lastName: number | null;
  team: number | null;
  active: number | null;
}

/** Which columns hold what, when the first row is a header ("Navn;Lag" or "Fornavn;Etternavn"). */
function headerColumns(firstRow: string[]): Columns | null {
  const headers = firstRow.map((cell) => normalizeName(cell));
  const find = (names: string[]) => {
    const index = headers.findIndex((header) => names.includes(header));
    return index < 0 ? null : index;
  };
  const columns = {
    name: find(NAME_HEADERS),
    firstName: find(FIRST_NAME_HEADERS),
    lastName: find(LAST_NAME_HEADERS),
    team: find(TEAM_HEADERS),
    active: find(ACTIVE_HEADERS),
  };
  return Object.values(columns).some((index) => index != null) ? columns : null;
}

function buildPreview(
  text: string,
  teams: FullTeamWithPlayers[],
  existingNames: Set<string>,
  t: (key: string, options?: any) => string,
): PreviewRow[] {
  const rows = parseCsv(text);
  if (rows.length < 1) return [];
  const header = headerColumns(rows[0]);
  const columns: Columns = header ?? {
    name: 0,
    firstName: null,
    lastName: null,
    team: rows[0].length > 1 ? 1 : null,
    active: null,
  };
  const teamByName = new Map(teams.map((team) => [normalizeName(team.name), team]));
  const seen = new Set<string>();
  return rows.slice(header != null ? 1 : 0).map((cells, index) => {
    const cell = (column: number | null) => (column == null ? '' : (cells[column] ?? ''));
    const name =
      columns.name != null
        ? cell(columns.name)
        : [cell(columns.firstName), cell(columns.lastName)].filter(Boolean).join(' ');
    const teamText = cell(columns.team);
    const team = teamText === '' ? null : (teamByName.get(normalizeName(teamText)) ?? null);
    const activeText = normalizeName(cell(columns.active));
    const active = activeText === '' ? null : !NO_VALUES.includes(activeText);
    const key = normalizeName(name);
    let status: RowStatus = 'new';
    let reason: string | null = null;
    if (name === '') {
      status = 'invalid';
      reason = t('player_import_reason_empty');
    } else if (name.length > MAX_NAME_LENGTH) {
      status = 'invalid';
      reason = t('player_import_reason_too_long', { count: MAX_NAME_LENGTH });
    } else if (seen.has(key)) {
      status = 'duplicate';
    } else if (existingNames.has(key)) {
      status = 'exists';
    }
    if (team == null && teamText !== '' && status !== 'invalid') {
      reason = t('player_import_reason_team_not_found', { team: teamText });
    }
    seen.add(key);
    return {
      line: index + (header != null ? 2 : 1),
      name,
      teamText,
      team,
      active,
      status,
      reason,
    };
  });
}

function StatusBadge({ row }: { row: PreviewRow }) {
  const { t } = useTranslation();
  const colors: Record<RowStatus, string> = {
    new: 'green',
    exists: 'gray',
    duplicate: 'gray',
    invalid: 'red',
  };
  return (
    <Badge color={colors[row.status]} variant="light">
      {t(`player_import_status_${row.status}`)}
    </Badge>
  );
}

function downloadTemplate(t: (key: string) => string) {
  const lines = [
    `${t('player_import_template_name')};${t('player_import_template_team')}`,
    'Ola Nordmann;Brann 1',
    'Kari Nordmann;Brann 1',
  ];
  // BOM + semicolons: opens correctly in Norwegian Excel
  const blob = new Blob([`﻿${lines.join('\r\n')}\r\n`], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'spillere.csv';
  link.click();
  URL.revokeObjectURL(url);
}

export default function PlayerImportModal({
  tournamentId,
  swrPlayersResponse,
}: {
  tournamentId: number;
  swrPlayersResponse: SWRResponse<PlayersResponse>;
}) {
  const { t } = useTranslation();
  const [opened, setOpened] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);
  const [text, setText] = useState('');
  const [defaultTeamId, setDefaultTeamId] = useState<string | null>(null);
  const [active, setActive] = useState(true);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PlayerImportResult | null>(null);
  const swrTeams = getAllTeams(tournamentId);
  const swrAllPlayers = getAllPlayers(tournamentId);
  const teams = swrTeams.data ?? [];
  const existingNames = useMemo(
    () => new Set((swrAllPlayers.data ?? []).map((player) => normalizeName(player.name))),
    [swrAllPlayers.data],
  );
  const preview = useMemo(
    () => (text === '' ? [] : buildPreview(text, teams, existingNames, t)),
    [text, teams, existingNames, t],
  );
  const defaultTeam = teams.find((team) => `${team.id}` === defaultTeamId) ?? null;
  const importable = preview.filter((row) => row.status !== 'invalid');
  const newCount = preview.filter((row) => row.status === 'new').length;
  const tooMany = importable.length > MAX_ROWS;

  function reset() {
    setFileName(null);
    setText('');
    setResult(null);
    setDefaultTeamId(null);
    setActive(true);
  }

  async function runImport() {
    setLoading(true);
    const rows: PlayerImportRowValue[] = importable.map((row) => ({
      name: row.name,
      team_id: (row.team ?? defaultTeam)?.id ?? null,
      active: row.active,
    }));
    const response = await importPlayers(tournamentId, rows, active);
    setLoading(false);
    if (requestSucceeded(response) && 'data' in response) {
      setResult(response.data.data);
      await swrPlayersResponse.mutate();
      await swrAllPlayers.mutate();
      await swrTeams.mutate();
    }
  }

  return (
    <>
      <Modal
        opened={opened}
        onClose={() => {
          setOpened(false);
          reset();
        }}
        title={t('player_import_title')}
        size="56rem"
      >
        {result != null ? (
          <Stack>
            <Alert color="green" title={t('player_import_done_title')}>
              <Text size="sm">
                {t('player_import_done_created', { count: result.created })}
                {result.added_to_team > 0
                  ? ` ${t('player_import_done_added', { count: result.added_to_team })}`
                  : ''}
                {result.skipped.length > 0
                  ? ` ${t('player_import_done_skipped', { count: result.skipped.length })}`
                  : ''}
                {result.not_added_to_team.length > 0
                  ? ` ${t('player_import_done_not_added', {
                      count: result.not_added_to_team.length,
                      names: result.not_added_to_team.slice(0, 5).join(', '),
                    })}`
                  : ''}
              </Text>
            </Alert>
            <Group justify="right">
              <Button variant="default" onClick={reset}>
                {t('player_import_another_button')}
              </Button>
              <Button
                onClick={() => {
                  setOpened(false);
                  reset();
                }}
              >
                {t('close_button')}
              </Button>
            </Group>
          </Stack>
        ) : (
          <Stack>
            <Text size="sm" c="dimmed">
              {t('player_import_description')}
            </Text>
            <Dropzone
              onDrop={async (files) => {
                const [file] = files;
                if (file == null) return;
                setFileName(file.name);
                setText(await file.text());
              }}
              accept={['text/csv', 'text/plain', 'text/tab-separated-values', '.csv', '.txt']}
              maxFiles={1}
              maxSize={2 * 1024 * 1024}
            >
              <Group justify="center" gap="md" mih={90} style={{ pointerEvents: 'none' }}>
                <IconFileSpreadsheet size={36} stroke={1.5} />
                <Stack gap={2}>
                  <Text fw={600}>{fileName ?? t('player_import_drop_title')}</Text>
                  <Text size="sm" c="dimmed">
                    {t('player_import_drop_description')}
                  </Text>
                </Stack>
              </Group>
            </Dropzone>
            <Group justify="space-between">
              <Button
                variant="subtle"
                size="compact-sm"
                leftSection={<IconDownload size={16} />}
                onClick={() => downloadTemplate(t)}
              >
                {t('player_import_template_button')}
              </Button>
              <Text size="xs" c="dimmed">
                {t('player_import_excel_hint')}
              </Text>
            </Group>

            {preview.length > 0 ? (
              <>
                <Group align="end">
                  <Select
                    label={t('player_import_default_team_label')}
                    description={t('player_import_default_team_description')}
                    placeholder={t('player_import_no_team')}
                    data={teams.map((team) => ({ value: `${team.id}`, label: team.name }))}
                    value={defaultTeamId}
                    onChange={setDefaultTeamId}
                    searchable
                    clearable
                    w="20rem"
                  />
                  <Checkbox
                    label={t('player_import_active_label')}
                    checked={active}
                    onChange={(event) => setActive(event.currentTarget.checked)}
                    mb={8}
                  />
                </Group>
                <Group gap="xs">
                  <Badge color="green" variant="light">
                    {t('player_import_count_new', { count: newCount })}
                  </Badge>
                  <Badge color="gray" variant="light">
                    {t('player_import_count_skipped', {
                      count: importable.length - newCount,
                    })}
                  </Badge>
                  {preview.length - importable.length > 0 ? (
                    <Badge color="red" variant="light">
                      {t('player_import_count_invalid', {
                        count: preview.length - importable.length,
                      })}
                    </Badge>
                  ) : null}
                </Group>
                <Table.ScrollContainer minWidth={520} mah="22rem">
                  <Table striped stickyHeader>
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th w="4rem">{t('player_import_line_header')}</Table.Th>
                        <Table.Th>{t('name_table_header')}</Table.Th>
                        <Table.Th w="9rem">{t('player_import_team_header')}</Table.Th>
                        <Table.Th w="12rem">{t('status')}</Table.Th>
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {preview.map((row) => (
                        <Table.Tr key={row.line}>
                          <Table.Td>
                            <Text size="sm" c="dimmed">
                              {row.line}
                            </Text>
                          </Table.Td>
                          <Table.Td>
                            <Text size="sm" lineClamp={2} style={{ wordBreak: 'break-word' }}>
                              {row.name || '–'}
                            </Text>
                          </Table.Td>
                          <Table.Td>
                            <Text size="sm">
                              {row.team?.name ??
                                (row.teamText === '' ? defaultTeam?.name : '') ??
                                ''}
                            </Text>
                          </Table.Td>
                          <Table.Td>
                            <Stack gap={2}>
                              <StatusBadge row={row} />
                              {row.reason != null ? (
                                <Text size="xs" c={row.status === 'invalid' ? 'red' : 'orange'}>
                                  {row.reason}
                                </Text>
                              ) : null}
                            </Stack>
                          </Table.Td>
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                  </Table>
                </Table.ScrollContainer>
                {tooMany ? (
                  <Alert color="red">{t('player_import_too_many', { count: MAX_ROWS })}</Alert>
                ) : null}
                <Group justify="right">
                  <Button variant="default" onClick={reset}>
                    {t('player_import_choose_other_button')}
                  </Button>
                  <Button
                    color="green"
                    loading={loading}
                    disabled={importable.length < 1 || tooMany}
                    leftSection={<IconFileUpload size={18} />}
                    onClick={runImport}
                  >
                    {t('player_import_button', { count: newCount })}
                  </Button>
                </Group>
              </>
            ) : fileName != null ? (
              <Alert color="orange">{t('player_import_empty_file')}</Alert>
            ) : null}
          </Stack>
        )}
      </Modal>
      <Button
        variant="light"
        leftSection={<IconFileSpreadsheet size={20} />}
        onClick={() => setOpened(true)}
      >
        {t('player_import_open_button')}
      </Button>
    </>
  );
}
