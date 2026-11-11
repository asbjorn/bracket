import {
  ActionIcon,
  Alert,
  Anchor,
  Badge,
  Button,
  Group,
  List,
  Modal,
  MultiSelect,
  NumberInput,
  SegmentedControl,
  Select,
  Stack,
  Switch,
  Table,
  Tabs,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import {
  IconAlertTriangle,
  IconDownload,
  IconPencil,
  IconPlus,
  IconTrash,
  IconUserCheck,
} from '@tabler/icons-react';
import dayjs from 'dayjs';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { NoContent } from '@components/no_content/empty_table_info';
import { Time } from '@components/utils/datetime';
import { formatMatchInput1, formatMatchInput2 } from '@components/utils/match';
import { getTournamentIdFromRouter } from '@components/utils/util';
import { contentLanguage } from '@components/utils/language';
import { DateTimeField } from '@components/utils/time_fields';
import {
  Court,
  MatchWithDetails,
  Official,
  OfficialBody,
  OfficialConflict,
  OfficialsOverview,
} from '@openapi';
import TournamentLayout from '@pages/tournaments/_tournament_layout';
import { getCourts, getStages, requestSucceeded } from '@services/adapter';
import { getMatchLookup, getStageItemLookup } from '@services/lookups';
import {
  assignBlock,
  createCourtHost,
  createOfficial,
  deleteCourtHost,
  deleteOfficial,
  downloadFeesCsv,
  getOfficialsOverview,
  setMatchOfficials,
  updateOfficial,
} from '@services/officials';

type Refresh = () => Promise<unknown>;

const EMPTY_OFFICIAL: OfficialBody = {
  name: '',
  age: null,
  level: null,
  club_name: null,
  phone: null,
  email: null,
  role: 'REFEREE',
  fee_per_match: 0,
  fee_per_day: 0,
  active: true,
};

function formatNok(amount: number) {
  return `${amount.toLocaleString('nb-NO')} kr`;
}

const emptyToNull = (value: string) => (value.trim() === '' ? null : value.trim());

function OfficialModal({
  tournamentId,
  official,
  onClose,
  refresh,
}: {
  tournamentId: number;
  official: Official | null; // null: a new official
  onClose: () => void;
  refresh: Refresh;
}) {
  const { t } = useTranslation();
  const [value, setValue] = useState<OfficialBody>(
    official != null ? { ...EMPTY_OFFICIAL, ...official } : EMPTY_OFFICIAL,
  );
  const [saving, setSaving] = useState(false);
  const update = (changes: Partial<OfficialBody>) => setValue({ ...value, ...changes });

  return (
    <Modal
      opened
      onClose={onClose}
      title={official != null ? t('edit_official_title') : t('add_official_title')}
    >
      <form
        onSubmit={async (event) => {
          event.preventDefault();
          setSaving(true);
          const response =
            official != null
              ? await updateOfficial(tournamentId, official.id, value)
              : await createOfficial(tournamentId, value);
          setSaving(false);
          if (requestSucceeded(response)) {
            await refresh();
            onClose();
          }
        }}
      >
        <Stack>
          <SegmentedControl
            fullWidth
            data={[
              { value: 'REFEREE', label: t('official_role_referee') },
              { value: 'HOST', label: t('official_role_host') },
            ]}
            value={value.role}
            onChange={(role) => update({ role: role as OfficialBody['role'] })}
          />
          <TextInput
            data-autofocus
            withAsterisk
            label={t('name_input_label')}
            value={value.name}
            onChange={(e) => update({ name: e.currentTarget.value })}
          />
          <Group grow>
            <TextInput
              label={t('official_level_label')}
              placeholder={t('official_level_placeholder')}
              value={value.level ?? ''}
              onChange={(e) => update({ level: emptyToNull(e.currentTarget.value) })}
            />
            <NumberInput
              label={t('official_age_label')}
              min={8}
              max={99}
              value={value.age ?? ''}
              onChange={(age) => update({ age: age === '' ? null : Number(age) })}
            />
          </Group>
          <TextInput
            label={t('club_name_input_label')}
            description={t('official_club_description')}
            value={value.club_name ?? ''}
            onChange={(e) => update({ club_name: emptyToNull(e.currentTarget.value) })}
          />
          <Group grow>
            <TextInput
              label={t('registration_phone_label')}
              type="tel"
              value={value.phone ?? ''}
              onChange={(e) => update({ phone: emptyToNull(e.currentTarget.value) })}
            />
            <TextInput
              label={t('email_input_label')}
              type="email"
              value={value.email ?? ''}
              onChange={(e) => update({ email: emptyToNull(e.currentTarget.value) })}
            />
          </Group>
          <Text size="xs" c="dimmed">
            {t('official_contact_private_note')}
          </Text>
          <Group grow>
            <NumberInput
              label={t('official_fee_per_match_label')}
              min={0}
              max={100000}
              suffix=" kr"
              value={value.fee_per_match}
              onChange={(fee) => update({ fee_per_match: Number(fee) || 0 })}
            />
            <NumberInput
              label={t('official_fee_per_day_label')}
              min={0}
              max={100000}
              suffix=" kr"
              value={value.fee_per_day}
              onChange={(fee) => update({ fee_per_day: Number(fee) || 0 })}
            />
          </Group>
          <Switch
            label={t('official_active_label')}
            checked={value.active}
            onChange={(e) => update({ active: e.currentTarget.checked })}
          />
          <Button type="submit" loading={saving} disabled={value.name.trim() === ''}>
            {t('save_button')}
          </Button>
        </Stack>
      </form>
    </Modal>
  );
}

function ConflictsAlert({
  overview,
  matchLabel,
}: {
  overview: OfficialsOverview;
  matchLabel: (matchId: number | null | undefined) => string;
}) {
  const { t } = useTranslation();
  if (overview.conflicts.length < 1) return null;
  const name = (conflict: OfficialConflict) =>
    overview.officials.find((o) => o.id === conflict.official_id)?.name ?? '?';
  return (
    <Alert
      color="orange"
      icon={<IconAlertTriangle />}
      title={t('official_conflicts_title', { count: overview.conflicts.length })}
    >
      <List size="sm">
        {overview.conflicts.map((conflict, index) => (
          <List.Item key={index}>
            {t(`official_conflict_${conflict.kind.toLowerCase()}`, {
              name: name(conflict),
              match: matchLabel(conflict.match_id),
              other:
                conflict.other_match_id != null
                  ? matchLabel(conflict.other_match_id)
                  : t('official_host_block_label'),
            })}
          </List.Item>
        ))}
      </List>
    </Alert>
  );
}

function OfficialsTab({
  tournamentId,
  overview,
  refresh,
}: {
  tournamentId: number;
  overview: OfficialsOverview;
  refresh: Refresh;
}) {
  const { t } = useTranslation();
  const [edited, setEdited] = useState<Official | null | undefined>(undefined);
  const matchCount = (id: number) =>
    overview.assignments.filter((a) => a.official_id === id).length;

  return (
    <Stack>
      {edited !== undefined ? (
        <OfficialModal
          tournamentId={tournamentId}
          official={edited}
          onClose={() => setEdited(undefined)}
          refresh={refresh}
        />
      ) : null}
      <Group>
        <Button leftSection={<IconPlus size={18} />} onClick={() => setEdited(null)}>
          {t('add_official_title')}
        </Button>
      </Group>
      {overview.officials.length < 1 ? (
        <NoContent title={t('no_officials_title')} description={t('no_officials_description')} />
      ) : (
        <Table.ScrollContainer minWidth={700}>
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('name_input_label')}</Table.Th>
                <Table.Th>{t('official_level_label')}</Table.Th>
                <Table.Th>{t('club_name_input_label')}</Table.Th>
                <Table.Th>{t('contact_label')}</Table.Th>
                <Table.Th>{t('official_matches_header')}</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {overview.officials.map((official) => (
                <Table.Tr key={official.id} opacity={official.active ? 1 : 0.5}>
                  <Table.Td>
                    <Group gap="xs">
                      <Text fw={500}>{official.name}</Text>
                      <Badge variant="light" color={official.role === 'HOST' ? 'grape' : 'blue'}>
                        {t(`official_role_${official.role.toLowerCase()}`)}
                      </Badge>
                      {official.age != null ? (
                        <Text size="xs" c="dimmed">
                          {t('official_age_short', { age: official.age })}
                        </Text>
                      ) : null}
                    </Group>
                  </Table.Td>
                  <Table.Td>{official.level ?? '–'}</Table.Td>
                  <Table.Td>{official.club_name ?? '–'}</Table.Td>
                  <Table.Td>
                    <Stack gap={0}>
                      {official.phone != null ? (
                        <Anchor size="sm" href={`tel:${official.phone}`}>
                          {official.phone}
                        </Anchor>
                      ) : null}
                      {official.email != null ? (
                        <Anchor size="sm" href={`mailto:${official.email}`}>
                          {official.email}
                        </Anchor>
                      ) : null}
                    </Stack>
                  </Table.Td>
                  <Table.Td>{matchCount(official.id)}</Table.Td>
                  <Table.Td>
                    <Group gap={4} justify="flex-end" wrap="nowrap">
                      <ActionIcon variant="subtle" onClick={() => setEdited(official)}>
                        <IconPencil size={18} />
                      </ActionIcon>
                      <ActionIcon
                        variant="subtle"
                        color="red"
                        onClick={async () => {
                          if (
                            !window.confirm(t('delete_official_confirm', { name: official.name }))
                          )
                            return;
                          await deleteOfficial(tournamentId, official.id);
                          await refresh();
                        }}
                      >
                        <IconTrash size={18} />
                      </ActionIcon>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
    </Stack>
  );
}

interface MatchRow {
  match: MatchWithDetails;
  team1: string;
  team2: string;
  stageItemName: string;
}

function BlockForm({
  tournamentId,
  courts,
  officials,
  refresh,
  host,
}: {
  tournamentId: number;
  courts: Court[];
  officials: Official[];
  refresh: Refresh;
  host: boolean; // A host block instead of refereeing all matches in the block
}) {
  const { t } = useTranslation();
  const [officialId, setOfficialId] = useState<string | null>(null);
  const [courtId, setCourtId] = useState<string | null>(null);
  const [start, setStart] = useState<string | null>(null);
  const [end, setEnd] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const role = host ? 'HOST' : 'REFEREE';
  const candidates = officials.filter((o) => o.active && (host ? true : o.role === role));

  return (
    <Group align="end">
      <Select
        label={host ? t('official_role_host') : t('official_role_referee')}
        data={candidates.map((o) => ({ value: `${o.id}`, label: o.name }))}
        value={officialId}
        onChange={setOfficialId}
        searchable
        w="14rem"
      />
      <Select
        label={t('court_label')}
        data={courts.map((c) => ({ value: `${c.id}`, label: c.name }))}
        value={courtId}
        onChange={setCourtId}
        w="10rem"
      />
      <DateTimeField
        label={t('official_block_from_label')}
        value={start}
        onChange={setStart}
        w="13rem"
      />
      <DateTimeField label={t('official_block_to_label')} value={end} onChange={setEnd} w="13rem" />
      <Button
        loading={saving}
        disabled={officialId == null || courtId == null || start == null || end == null}
        onClick={async () => {
          setSaving(true);
          const body = {
            official_id: Number(officialId),
            court_id: Number(courtId),
            start_time: dayjs(start).toISOString(),
            end_time: dayjs(end).toISOString(),
          };
          const response = host
            ? await createCourtHost(tournamentId, body)
            : await assignBlock(tournamentId, body);
          setSaving(false);
          if (requestSucceeded(response)) await refresh();
        }}
      >
        {host ? t('add_host_block_button') : t('assign_block_button')}
      </Button>
    </Group>
  );
}

function AssignmentTab({
  tournamentId,
  overview,
  rows,
  courts,
  refresh,
}: {
  tournamentId: number;
  overview: OfficialsOverview;
  rows: MatchRow[];
  courts: Court[];
  refresh: Refresh;
}) {
  const { t } = useTranslation();
  const [courtFilter, setCourtFilter] = useState<string | null>(null);
  const [onlyMissing, setOnlyMissing] = useState(false);
  const referees = overview.officials.filter((o) => o.role === 'REFEREE');
  const options = referees.map((o) => ({
    value: `${o.id}`,
    label: o.club_name != null ? `${o.name} (${o.club_name})` : o.name,
    disabled: !o.active,
  }));
  const conflicted = new Set(
    overview.conflicts.flatMap((c) => [c.match_id, c.other_match_id]).filter((id) => id != null),
  );
  const assignmentsOf = (matchId: number) =>
    overview.assignments.filter((a) => a.match_id === matchId);
  const visible = rows
    .filter((row) => courtFilter == null || `${row.match.court_id}` === courtFilter)
    .filter(
      (row) => !onlyMissing || !assignmentsOf(row.match.id).some((a) => a.role === 'REFEREE'),
    );
  const missing = rows.filter(
    (row) => !assignmentsOf(row.match.id).some((a) => a.role === 'REFEREE'),
  );

  async function save(matchId: number, refereeId: number | null, assistantIds: number[]) {
    const response = await setMatchOfficials(tournamentId, matchId, {
      referee_id: refereeId,
      assistant_ids: assistantIds.filter((id) => id !== refereeId),
    });
    if (requestSucceeded(response)) await refresh();
  }

  return (
    <Stack>
      <Text size="sm" c="dimmed">
        {t('official_block_description')}
      </Text>
      <BlockForm
        tournamentId={tournamentId}
        courts={courts}
        officials={overview.officials}
        refresh={refresh}
        host={false}
      />
      <Group align="end">
        <Select
          label={t('court_label')}
          placeholder={t('all_courts_button')}
          data={courts.map((c) => ({ value: `${c.id}`, label: c.name }))}
          value={courtFilter}
          onChange={setCourtFilter}
          clearable
          w="12rem"
        />
        <Switch
          label={t('official_only_missing_label', { count: missing.length })}
          checked={onlyMissing}
          onChange={(e) => setOnlyMissing(e.currentTarget.checked)}
          mb={6}
        />
      </Group>
      {rows.length < 1 ? (
        <NoContent
          title={t('no_scheduled_matches_title')}
          description={t('official_no_matches_description')}
        />
      ) : (
        <Table.ScrollContainer minWidth={800}>
          <Table striped>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('time_label')}</Table.Th>
                <Table.Th>{t('court_label')}</Table.Th>
                <Table.Th>{t('match_label')}</Table.Th>
                <Table.Th>{t('official_role_referee')}</Table.Th>
                <Table.Th>{t('official_assistants_label')}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {visible.map((row) => {
                const assigned = assignmentsOf(row.match.id);
                const referee = assigned.find((a) => a.role === 'REFEREE')?.official_id ?? null;
                const assistants = assigned
                  .filter((a) => a.role === 'ASSISTANT')
                  .map((a) => a.official_id);
                return (
                  <Table.Tr key={row.match.id}>
                    <Table.Td>
                      {row.match.start_time != null ? (
                        <Text fw={500}>
                          {dayjs(row.match.start_time).format('ddd')}{' '}
                          <Time datetime={row.match.start_time} />
                        </Text>
                      ) : (
                        '–'
                      )}
                    </Table.Td>
                    <Table.Td>{row.match.court?.name ?? '–'}</Table.Td>
                    <Table.Td>
                      <Text size="sm">
                        {row.team1} – {row.team2}
                      </Text>
                      <Text size="xs" c="dimmed">
                        {row.stageItemName}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Group gap={4} wrap="nowrap">
                        <Select
                          data={options}
                          value={referee != null ? `${referee}` : null}
                          onChange={(value) =>
                            save(row.match.id, value != null ? Number(value) : null, assistants)
                          }
                          placeholder={t('official_choose_placeholder')}
                          clearable
                          searchable
                          w="13rem"
                          error={conflicted.has(row.match.id)}
                        />
                        {conflicted.has(row.match.id) ? (
                          <IconAlertTriangle size={18} color="orange" />
                        ) : null}
                      </Group>
                    </Table.Td>
                    <Table.Td>
                      <MultiSelect
                        data={options.filter((o) => o.value !== `${referee}`)}
                        value={assistants.map((id) => `${id}`)}
                        onChange={(values) => save(row.match.id, referee, values.map(Number))}
                        searchable
                        w="16rem"
                        maxValues={4}
                      />
                    </Table.Td>
                  </Table.Tr>
                );
              })}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
    </Stack>
  );
}

function HostsTab({
  tournamentId,
  overview,
  courts,
  refresh,
}: {
  tournamentId: number;
  overview: OfficialsOverview;
  courts: Court[];
  refresh: Refresh;
}) {
  const { t } = useTranslation();
  const name = (id: number) => overview.officials.find((o) => o.id === id)?.name ?? '?';
  const court = (id: number) => courts.find((c) => c.id === id)?.name ?? '?';
  return (
    <Stack>
      <Text size="sm" c="dimmed">
        {t('court_hosts_description')}
      </Text>
      <BlockForm
        tournamentId={tournamentId}
        courts={courts}
        officials={overview.officials}
        refresh={refresh}
        host
      />
      {overview.hosts.length < 1 ? (
        <Text c="dimmed">{t('no_court_hosts')}</Text>
      ) : (
        <Table maw="44rem">
          <Table.Tbody>
            {overview.hosts.map((host) => (
              <Table.Tr key={host.id}>
                <Table.Td>{court(host.court_id)}</Table.Td>
                <Table.Td>
                  {dayjs(host.start_time).format('ddd HH:mm')}–
                  {dayjs(host.end_time).format('HH:mm')}
                </Table.Td>
                <Table.Td fw={500}>{name(host.official_id)}</Table.Td>
                <Table.Td>
                  <ActionIcon
                    variant="subtle"
                    color="red"
                    onClick={async () => {
                      await deleteCourtHost(tournamentId, host.id);
                      await refresh();
                    }}
                  >
                    <IconTrash size={18} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  );
}

function FeesTab({
  tournamentId,
  overview,
}: {
  tournamentId: number;
  overview: OfficialsOverview;
}) {
  const { t, i18n } = useTranslation();
  const total = overview.fees.reduce((sum, fee) => sum + fee.total, 0);
  return (
    <Stack>
      <Group justify="space-between">
        <Text size="sm" c="dimmed">
          {t('official_fees_description')}
        </Text>
        <Button
          variant="light"
          leftSection={<IconDownload size={18} />}
          onClick={() => downloadFeesCsv(tournamentId, contentLanguage(i18n))}
        >
          {t('registrations_export_button')}
        </Button>
      </Group>
      <Table maw="48rem">
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{t('name_input_label')}</Table.Th>
            <Table.Th ta="right">{t('official_matches_header')}</Table.Th>
            <Table.Th ta="right">{t('official_days_header')}</Table.Th>
            <Table.Th ta="right">{t('official_fee_total_header')}</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {overview.fees.map((fee) => (
            <Table.Tr key={fee.official_id}>
              <Table.Td>{fee.name}</Table.Td>
              <Table.Td ta="right">{fee.matches}</Table.Td>
              <Table.Td ta="right">{fee.days}</Table.Td>
              <Table.Td ta="right" fw={500}>
                {formatNok(fee.total)}
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
        <Table.Tfoot>
          <Table.Tr>
            <Table.Th>{t('official_fee_total_header')}</Table.Th>
            <Table.Th />
            <Table.Th />
            <Table.Th ta="right">{formatNok(total)}</Table.Th>
          </Table.Tr>
        </Table.Tfoot>
      </Table>
    </Stack>
  );
}

export default function OfficialsPage() {
  const { t } = useTranslation();
  const { tournamentData } = getTournamentIdFromRouter();
  const tournamentId = tournamentData.id;
  const swrOverview = getOfficialsOverview(tournamentId);
  const swrStagesResponse = getStages(tournamentId);
  const courts = getCourts(tournamentId).data?.data ?? [];
  const overview = swrOverview.data?.data;

  const rows: MatchRow[] = [];
  if (swrStagesResponse.data != null) {
    const matchesLookup = getMatchLookup(swrStagesResponse);
    const stageItemsLookup = getStageItemLookup(swrStagesResponse);
    Object.values(matchesLookup)
      .filter((data: any) => data.match.start_time != null)
      .sort(
        (a: any, b: any) =>
          a.match.start_time.localeCompare(b.match.start_time) ||
          (a.match.court?.name ?? '').localeCompare(b.match.court?.name ?? ''),
      )
      .forEach((data: any) =>
        rows.push({
          match: data.match,
          team1: formatMatchInput1(t, stageItemsLookup, matchesLookup, data.match),
          team2: formatMatchInput2(t, stageItemsLookup, matchesLookup, data.match),
          stageItemName: data.stageItem.name,
        }),
      );
  }
  const matchLabel = (matchId: number | null | undefined) => {
    const row = rows.find((r) => r.match.id === matchId);
    if (row == null) return matchId != null ? `#${matchId}` : '';
    const time =
      row.match.start_time != null ? dayjs(row.match.start_time).format('ddd HH:mm') : '';
    return `${time} ${row.match.court?.name ?? ''}: ${row.team1} – ${row.team2}`.trim();
  };
  const refresh = () => swrOverview.mutate();

  return (
    <TournamentLayout tournament_id={tournamentId}>
      <Stack>
        <Group justify="space-between">
          <Title>{t('officials_title')}</Title>
          {overview != null ? (
            <Badge size="lg" variant="light" leftSection={<IconUserCheck size={14} />}>
              {t('official_coverage_badge', {
                assigned: rows.filter((row) =>
                  overview.assignments.some(
                    (a) => a.match_id === row.match.id && a.role === 'REFEREE',
                  ),
                ).length,
                total: rows.length,
              })}
            </Badge>
          ) : null}
        </Group>
        {overview != null ? (
          <>
            <ConflictsAlert overview={overview} matchLabel={matchLabel} />
            <Tabs defaultValue="officials" keepMounted={false}>
              <Tabs.List>
                <Tabs.Tab value="officials">
                  {t('officials_tab', { count: overview.officials.length })}
                </Tabs.Tab>
                <Tabs.Tab value="assignment">{t('official_assignment_tab')}</Tabs.Tab>
                <Tabs.Tab value="hosts">{t('court_hosts_tab')}</Tabs.Tab>
                <Tabs.Tab value="fees">{t('official_fees_tab')}</Tabs.Tab>
              </Tabs.List>
              <Tabs.Panel value="officials" pt="md">
                <OfficialsTab tournamentId={tournamentId} overview={overview} refresh={refresh} />
              </Tabs.Panel>
              <Tabs.Panel value="assignment" pt="md">
                <AssignmentTab
                  tournamentId={tournamentId}
                  overview={overview}
                  rows={rows}
                  courts={courts}
                  refresh={refresh}
                />
              </Tabs.Panel>
              <Tabs.Panel value="hosts" pt="md">
                <HostsTab
                  tournamentId={tournamentId}
                  overview={overview}
                  courts={courts}
                  refresh={refresh}
                />
              </Tabs.Panel>
              <Tabs.Panel value="fees" pt="md">
                <FeesTab tournamentId={tournamentId} overview={overview} />
              </Tabs.Panel>
            </Tabs>
          </>
        ) : null}
      </Stack>
    </TournamentLayout>
  );
}
