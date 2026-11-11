import {
  ActionIcon,
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  CopyButton,
  Group,
  Modal,
  NumberInput,
  Progress,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Textarea,
  Title,
  Tooltip,
} from '@mantine/core';
import {
  IconArrowUp,
  IconCheck,
  IconCopy,
  IconDownload,
  IconInfoCircle,
  IconPencil,
} from '@tabler/icons-react';
import dayjs from 'dayjs';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { NoContent } from '@components/no_content/empty_table_info';
import { getBaseURL, getTournamentIdFromRouter } from '@components/utils/util';
import { contentLanguage } from '@components/utils/language';
import { DateTimeField } from '@components/utils/time_fields';
import { Category, Registration, RegistrationStatus, Tournament } from '@openapi';
import TournamentLayout from '@pages/tournaments/_tournament_layout';
import { getCategories, getTournamentById, requestSucceeded } from '@services/adapter';
import {
  downloadRegistrationsCsv,
  getRegistrations,
  promoteFromWaitlist,
  saveEntryFees,
  saveRegistrationSettings,
  updateRegistration,
} from '@services/registration';

const STATUSES: RegistrationStatus[] = ['APPROVED', 'REGISTERED', 'WAITLIST', 'REJECTED'];
const STATUS_COLORS: Record<RegistrationStatus, string> = {
  APPROVED: 'green',
  REGISTERED: 'blue',
  WAITLIST: 'orange',
  REJECTED: 'gray',
};

function participates(status: RegistrationStatus) {
  return status === 'APPROVED' || status === 'REGISTERED';
}

/** (fixed + variable × teams) × (1 + margin) / teams, rounded up to the nearest 50 NOK. */
function suggestedEntryFee(
  fixedCosts: number,
  costPerTeam: number,
  marginPercent: number,
  teams: number,
) {
  if (teams < 1) return 0;
  const perTeam = ((fixedCosts + costPerTeam * teams) * (1 + marginPercent / 100)) / teams;
  return Math.ceil(perTeam / 50) * 50;
}

function formatNok(amount: number) {
  return `${amount.toLocaleString('nb-NO')} kr`;
}

type Refresh = () => Promise<unknown>;

function ClassCard({
  tournamentId,
  category,
  registrations,
  refresh,
}: {
  tournamentId: number;
  category: Category;
  registrations: Registration[];
  refresh: Refresh;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(category.registration_open);
  const [deadline, setDeadline] = useState<string | null>(null);
  const [maxTeams, setMaxTeams] = useState<number | string>(category.max_teams ?? '');
  const [fee, setFee] = useState<number | string>(category.entry_fee ?? '');
  useEffect(() => {
    setOpen(category.registration_open);
    setDeadline(
      category.registration_deadline != null
        ? dayjs(category.registration_deadline).format('YYYY-MM-DD HH:mm:ss')
        : null,
    );
    setMaxTeams(category.max_teams ?? '');
    setFee(category.entry_fee ?? '');
  }, [category]);

  const taking = registrations.filter((r) => participates(r.registration_status)).length;
  const waiting = registrations.filter((r) => r.registration_status === 'WAITLIST').length;
  const freeSpots = category.max_teams != null ? category.max_teams - taking : null;
  const pastDeadline =
    category.registration_deadline != null &&
    dayjs(category.registration_deadline).isBefore(dayjs());

  return (
    <Card withBorder radius="md" padding="lg">
      <Stack gap="sm">
        <Group justify="space-between">
          <Title order={3}>{category.name}</Title>
          {category.registration_open && !pastDeadline ? (
            <Badge color="green">{t('registration_open_badge')}</Badge>
          ) : (
            <Badge color="gray">{t('registration_closed_badge')}</Badge>
          )}
        </Group>
        <Text size="sm">
          {category.max_teams != null
            ? t('registration_teams_of_max', { count: taking, max: category.max_teams })
            : t('registration_teams_count', { count: taking })}
          {waiting > 0 ? ` · ${t('registration_waiting_count', { count: waiting })}` : ''}
        </Text>
        {category.max_teams != null ? (
          <Progress value={Math.min(100, (100 * taking) / category.max_teams)} />
        ) : null}
        {waiting > 0 && freeSpots != null && freeSpots > 0 ? (
          <Alert color="orange" p="xs">
            <Group justify="space-between" gap="xs">
              <Text size="sm">{t('registration_free_spot_hint', { count: freeSpots })}</Text>
              <Button
                size="xs"
                style={{ flexShrink: 0 }}
                leftSection={<IconArrowUp size={16} />}
                onClick={async () => {
                  if (requestSucceeded(await promoteFromWaitlist(tournamentId, category.id)))
                    await refresh();
                }}
              >
                {t('registration_promote_button')}
              </Button>
            </Group>
          </Alert>
        ) : null}
        <Switch
          label={t('registration_open_label')}
          checked={open}
          onChange={(event) => setOpen(event.currentTarget.checked)}
        />
        <DateTimeField
          label={t('registration_deadline_label')}
          value={deadline}
          onChange={setDeadline}
          clearable
        />
        <Group grow>
          <NumberInput
            label={t('registration_max_teams_label')}
            placeholder={t('registration_no_limit_placeholder')}
            value={maxTeams}
            onChange={setMaxTeams}
            min={1}
            max={256}
          />
          <NumberInput
            label={t('registration_entry_fee_label')}
            value={fee}
            onChange={setFee}
            min={0}
            max={100000}
            suffix=" kr"
            thousandSeparator=" "
          />
        </Group>
        <Group justify="right">
          <Button
            variant="light"
            onClick={async () => {
              const result = await saveRegistrationSettings(tournamentId, category.id, {
                registration_open: open,
                registration_deadline: deadline != null ? dayjs(deadline).toISOString() : null,
                max_teams: maxTeams === '' ? null : Number(maxTeams),
                entry_fee: fee === '' ? null : Number(fee),
              });
              if (requestSucceeded(result)) await refresh();
            }}
          >
            {t('save_button')}
          </Button>
        </Group>
      </Stack>
    </Card>
  );
}

function ContactModal({
  registration,
  onClose,
  onSave,
}: {
  registration: Registration | null;
  onClose: () => void;
  onSave: (changes: Partial<Registration>) => Promise<void>;
}) {
  const { t } = useTranslation();
  const [values, setValues] = useState({ name: '', email: '', phone: '', comment: '' });
  useEffect(() => {
    if (registration == null) return;
    setValues({
      name: registration.contact_name ?? '',
      email: registration.contact_email ?? '',
      phone: registration.contact_phone ?? '',
      comment: registration.comment ?? '',
    });
  }, [registration]);
  const orNull = (value: string) => (value.trim() === '' ? null : value.trim());

  return (
    <Modal opened={registration != null} onClose={onClose} title={registration?.team_name ?? ''}>
      <Stack>
        <TextInput
          label={t('registration_contact_name_label')}
          value={values.name}
          onChange={(e) => setValues({ ...values, name: e.currentTarget.value })}
        />
        <TextInput
          label={t('email_input_label')}
          type="email"
          value={values.email}
          onChange={(e) => setValues({ ...values, email: e.currentTarget.value })}
        />
        <TextInput
          label={t('registration_phone_label')}
          type="tel"
          value={values.phone}
          onChange={(e) => setValues({ ...values, phone: e.currentTarget.value })}
        />
        <Textarea
          label={t('registration_comment_label')}
          autosize
          minRows={2}
          value={values.comment}
          onChange={(e) => setValues({ ...values, comment: e.currentTarget.value })}
        />
        <Group justify="right">
          <Button
            onClick={() =>
              onSave({
                contact_name: orNull(values.name),
                contact_email: orNull(values.email),
                contact_phone: orNull(values.phone),
                comment: orNull(values.comment),
              })
            }
          >
            {t('save_button')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function EntryFeeCalculator({
  tournamentId,
  categories,
  registrations,
  refresh,
}: {
  tournamentId: number;
  categories: Category[];
  registrations: Registration[];
  refresh: Refresh;
}) {
  const { t } = useTranslation();
  const participating = registrations.filter((r) => participates(r.registration_status));
  const [fixed, setFixed] = useState<number | string>(20000);
  const [perTeam, setPerTeam] = useState<number | string>(300);
  const [margin, setMargin] = useState<number | string>(15);
  // Empty: use the teams taking part, or else the maximum number of teams of the classes
  const [teams, setTeams] = useState<number | string>('');
  const [classIds, setClassIds] = useState<string[]>([]);
  const maxTeamsSum = categories.reduce((sum, c) => sum + (c.max_teams ?? 0), 0);
  const autoTeams = participating.length > 0 ? participating.length : maxTeamsSum;
  const expectedTeams = teams === '' ? autoTeams : Number(teams);
  const fee =
    expectedTeams > 0
      ? suggestedEntryFee(Number(fixed), Number(perTeam), Number(margin), expectedTeams)
      : null;

  const feeOf = (r: Registration) => categories.find((c) => c.id === r.category_id)?.entry_fee ?? 0;
  const paid = participating.filter((r) => r.paid).reduce((sum, r) => sum + feeOf(r), 0);
  const unpaid = participating.filter((r) => !r.paid).reduce((sum, r) => sum + feeOf(r), 0);

  return (
    <Card withBorder radius="md" padding="lg">
      <Stack>
        <Title order={3}>{t('entry_fee_calculator_title')}</Title>
        <Text size="sm" c="dimmed">
          {t('entry_fee_calculator_description')}
        </Text>
        <SimpleGrid cols={{ base: 1, xs: 2, md: 4 }}>
          <NumberInput
            label={t('entry_fee_fixed_costs_label')}
            value={fixed}
            onChange={setFixed}
            min={0}
            suffix=" kr"
            thousandSeparator=" "
          />
          <NumberInput
            label={t('entry_fee_cost_per_team_label')}
            value={perTeam}
            onChange={setPerTeam}
            min={0}
            suffix=" kr"
            thousandSeparator=" "
          />
          <NumberInput
            label={t('entry_fee_margin_label')}
            value={margin}
            onChange={setMargin}
            min={0}
            max={100}
            suffix=" %"
          />
          <NumberInput
            label={t('entry_fee_teams_label')}
            value={teams}
            onChange={setTeams}
            min={1}
            placeholder={autoTeams > 0 ? `${autoTeams}` : t('entry_fee_teams_placeholder')}
          />
        </SimpleGrid>
        <Group align="end">
          <Stack gap={0}>
            <Text size="sm" c="dimmed">
              {t('entry_fee_suggested_label')}
            </Text>
            {fee != null ? (
              <Title order={2}>{formatNok(fee)}</Title>
            ) : (
              <Text c="dimmed">{t('entry_fee_needs_teams')}</Text>
            )}
          </Stack>
          <Select
            data={categories.map((c) => ({ value: `${c.id}`, label: c.name }))}
            placeholder={t('entry_fee_classes_placeholder')}
            value={null}
            onChange={(value) => value != null && setClassIds([...new Set([...classIds, value])])}
            w="12rem"
          />
          {classIds.map((id) => (
            <Badge
              key={id}
              size="lg"
              variant="light"
              rightSection={
                <ActionIcon
                  size="xs"
                  variant="transparent"
                  onClick={() => setClassIds(classIds.filter((other) => other !== id))}
                >
                  ×
                </ActionIcon>
              }
            >
              {categories.find((c) => `${c.id}` === id)?.name}
            </Badge>
          ))}
          <Button
            disabled={classIds.length < 1 || fee == null}
            onClick={async () => {
              if (fee == null) return;
              const result = await saveEntryFees(tournamentId, {
                category_ids: classIds.map(Number),
                entry_fee: fee,
              });
              if (requestSucceeded(result)) {
                setClassIds([]);
                await refresh();
              }
            }}
          >
            {t('entry_fee_apply_button')}
          </Button>
        </Group>
        <Group>
          <Badge size="lg" color="green" variant="light">
            {t('entry_fee_paid_total', { amount: formatNok(paid) })}
          </Badge>
          <Badge size="lg" color="orange" variant="light">
            {t('entry_fee_unpaid_total', { amount: formatNok(unpaid) })}
          </Badge>
        </Group>
      </Stack>
    </Card>
  );
}

function PublicFormLink({ tournament }: { tournament: Tournament | undefined }) {
  const { t } = useTranslation();
  if (tournament == null) return null;
  if (!tournament.dashboard_public || !tournament.dashboard_endpoint) {
    return (
      <Alert color="orange" icon={<IconInfoCircle />}>
        {tournament.dashboard_public
          ? t('registration_no_address_alert')
          : t('registration_not_public_alert')}
      </Alert>
    );
  }
  const url = `${getBaseURL()}/tournaments/${tournament.dashboard_endpoint}/dashboard/register`;
  return (
    <Group gap="xs">
      <Text size="sm">{t('registration_form_link_label')}</Text>
      <Anchor href={url} target="_blank" size="sm">
        {url}
      </Anchor>
      <CopyButton value={url}>
        {({ copied, copy }) => (
          <Tooltip label={copied ? t('copied_label') : t('copy_label')}>
            <ActionIcon variant="subtle" onClick={copy}>
              {copied ? <IconCheck size={16} /> : <IconCopy size={16} />}
            </ActionIcon>
          </Tooltip>
        )}
      </CopyButton>
    </Group>
  );
}

export default function RegistrationsPage() {
  const { t, i18n } = useTranslation();
  const { tournamentData } = getTournamentIdFromRouter();
  const tournament = getTournamentById(tournamentData.id).data?.data;
  const swrCategories = getCategories(tournamentData.id);
  const swrRegistrations = getRegistrations(tournamentData.id);
  const categories = swrCategories.data?.data ?? [];
  const registrations = swrRegistrations.data?.data ?? [];

  const [classFilter, setClassFilter] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [editing, setEditing] = useState<Registration | null>(null);

  const refresh = () => Promise.all([swrCategories.mutate(), swrRegistrations.mutate()]);
  const save = async (registration: Registration, changes: Partial<Registration>) => {
    const next = { ...registration, ...changes };
    const result = await updateRegistration(tournamentData.id, registration.team_id, {
      registration_status: next.registration_status,
      paid: next.paid,
      squad_reported: next.squad_reported,
      contact_name: next.contact_name,
      contact_email: next.contact_email,
      contact_phone: next.contact_phone,
      comment: next.comment,
    });
    if (requestSucceeded(result)) await swrRegistrations.mutate();
    return requestSucceeded(result);
  };

  const query = search.trim().toLowerCase();
  const shown = registrations.filter(
    (r) =>
      (classFilter == null || `${r.category_id}` === classFilter) &&
      (statusFilter === 'all' ||
        (statusFilter === 'participating' && participates(r.registration_status)) ||
        r.registration_status === statusFilter) &&
      (query === '' ||
        [r.team_name, r.club_name, r.contact_name, r.contact_email]
          .filter(Boolean)
          .some((value) => `${value}`.toLowerCase().includes(query))),
  );
  const className = (id: number | null) => categories.find((c) => c.id === id)?.name ?? '–';

  return (
    <TournamentLayout tournament_id={tournamentData.id}>
      <Stack>
        <Group justify="space-between">
          <Title>{t('registrations_title')}</Title>
          <Button
            variant="default"
            leftSection={<IconDownload size={18} />}
            disabled={registrations.length < 1}
            onClick={() => downloadRegistrationsCsv(tournamentData.id, contentLanguage(i18n))}
          >
            {t('registrations_export_button')}
          </Button>
        </Group>
        <PublicFormLink tournament={tournament} />

        {categories.length < 1 ? (
          <NoContent title={t('no_categories_title')} description={t('registrations_no_classes')} />
        ) : (
          <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
            {categories.map((category) => (
              <ClassCard
                key={category.id}
                tournamentId={tournamentData.id}
                category={category}
                registrations={registrations.filter((r) => r.category_id === category.id)}
                refresh={refresh}
              />
            ))}
          </SimpleGrid>
        )}

        <Group align="end">
          <TextInput
            label={t('search_label')}
            value={search}
            onChange={(e) => setSearch(e.currentTarget.value)}
            w="14rem"
          />
          <Select
            label={t('category_select_label')}
            data={categories.map((c) => ({ value: `${c.id}`, label: c.name }))}
            value={classFilter}
            onChange={setClassFilter}
            clearable
            w="10rem"
          />
          <SegmentedControl
            value={statusFilter}
            onChange={setStatusFilter}
            data={[
              { value: 'all', label: t('registration_filter_all') },
              { value: 'participating', label: t('registration_filter_participating') },
              { value: 'WAITLIST', label: t('registration_status_waitlist') },
              { value: 'REJECTED', label: t('registration_status_rejected') },
            ]}
          />
        </Group>

        {shown.length < 1 ? (
          <Text c="dimmed" ta="center" py="xl">
            {t('registrations_empty_title')}
          </Text>
        ) : (
          <Table.ScrollContainer minWidth={1000}>
            <Table striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{t('registration_team_name_label')}</Table.Th>
                  <Table.Th>{t('category_select_label')}</Table.Th>
                  <Table.Th>{t('registration_status_header')}</Table.Th>
                  <Table.Th>{t('registration_contact_title')}</Table.Th>
                  <Table.Th>{t('registration_paid_header')}</Table.Th>
                  <Table.Th>{t('registration_squad_header')}</Table.Th>
                  <Table.Th />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {shown.map((r) => (
                  <Table.Tr key={r.team_id}>
                    <Table.Td>
                      <Text fw={500}>{r.team_name}</Text>
                      {r.club_name != null ? (
                        <Text size="xs" c="dimmed">
                          {r.club_name}
                        </Text>
                      ) : null}
                      {r.withdrawn ? (
                        <Badge size="xs" color="red">
                          {t('withdrawn_badge')}
                        </Badge>
                      ) : null}
                    </Table.Td>
                    <Table.Td>{className(r.category_id)}</Table.Td>
                    <Table.Td>
                      <Group gap={6} wrap="nowrap">
                        <Select
                          size="xs"
                          w="9rem"
                          allowDeselect={false}
                          data={STATUSES.map((s) => ({
                            value: s,
                            label: t(`registration_status_${s.toLowerCase()}`),
                          }))}
                          value={r.registration_status}
                          onChange={(value) =>
                            value != null &&
                            save(r, { registration_status: value as RegistrationStatus })
                          }
                          styles={{
                            input: {
                              color: `var(--mantine-color-${STATUS_COLORS[r.registration_status]}-7)`,
                            },
                          }}
                        />
                        {r.waitlist_place != null ? (
                          <Badge color="orange" variant="light">
                            #{r.waitlist_place}
                          </Badge>
                        ) : null}
                      </Group>
                    </Table.Td>
                    <Table.Td>
                      <Stack gap={0}>
                        <Text size="sm">{r.contact_name ?? '–'}</Text>
                        {r.contact_email != null ? (
                          <Anchor size="xs" href={`mailto:${r.contact_email}`}>
                            {r.contact_email}
                          </Anchor>
                        ) : null}
                        {r.contact_phone != null ? (
                          <Anchor size="xs" href={`tel:${r.contact_phone.replace(/ /g, '')}`}>
                            {r.contact_phone}
                          </Anchor>
                        ) : null}
                        {r.comment != null ? (
                          <Text size="xs" c="dimmed" fs="italic" lineClamp={2}>
                            {r.comment}
                          </Text>
                        ) : null}
                      </Stack>
                    </Table.Td>
                    <Table.Td>
                      <Switch
                        checked={r.paid}
                        onChange={(e) => save(r, { paid: e.currentTarget.checked })}
                        aria-label={t('registration_paid_header')}
                      />
                    </Table.Td>
                    <Table.Td>
                      <Switch
                        checked={r.squad_reported}
                        onChange={(e) => save(r, { squad_reported: e.currentTarget.checked })}
                        aria-label={t('registration_squad_header')}
                      />
                    </Table.Td>
                    <Table.Td>
                      <ActionIcon
                        variant="subtle"
                        onClick={() => setEditing(r)}
                        aria-label={t('edit_button')}
                      >
                        <IconPencil size={18} />
                      </ActionIcon>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        )}

        {categories.length > 0 ? (
          <EntryFeeCalculator
            tournamentId={tournamentData.id}
            categories={categories}
            registrations={registrations}
            refresh={refresh}
          />
        ) : null}
      </Stack>
      <ContactModal
        registration={editing}
        onClose={() => setEditing(null)}
        onSave={async (changes) => {
          if (editing != null && (await save(editing, changes))) setEditing(null);
        }}
      />
    </TournamentLayout>
  );
}
