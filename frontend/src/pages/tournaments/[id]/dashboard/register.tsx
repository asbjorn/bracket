import {
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Container,
  Group,
  NumberInput,
  Select,
  Stack,
  Text,
  TextInput,
  Textarea,
  ThemeIcon,
  Title,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { IconCircleCheck, IconHourglass, IconPlus } from '@tabler/icons-react';
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { DashboardFooter } from '@components/dashboard/footer';
import { DoubleHeader, getTournamentHeadTitle } from '@components/dashboard/layout';
import { NoContent } from '@components/no_content/empty_table_info';
import { DateTime } from '@components/utils/datetime';
import { TableSkeletonTwoColumns } from '@components/utils/skeletons';
import { setTitle } from '@components/utils/util';
import { PublicRegistrationClass, PublicRegistrationResult } from '@openapi';
import { requestSucceeded } from '@services/adapter';
import { getTournamentResponseByEndpointName } from '@services/dashboard';
import { getOpenClasses, registerTeam } from '@services/registration';

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const PHONE_PATTERN = /^\+?[0-9 ]{5,20}$/;

function ClassOption({ value }: { value: PublicRegistrationClass }) {
  const { t } = useTranslation();
  return (
    <Group justify="space-between" wrap="nowrap" w="100%">
      <Stack gap={2}>
        <Text fw={600}>{value.name}</Text>
        {value.registration_deadline != null ? (
          <Text size="xs" c="dimmed">
            {t('registration_deadline_short')} <DateTime datetime={value.registration_deadline} />
          </Text>
        ) : null}
      </Stack>
      <Stack gap={4} align="flex-end">
        {value.spots_left === 0 ? (
          <Badge color="orange">{t('registration_waitlist_badge')}</Badge>
        ) : value.spots_left != null ? (
          <Badge color="green">{t('registration_spots_left', { count: value.spots_left })}</Badge>
        ) : null}
        {value.entry_fee != null ? (
          <Text size="sm">{t('registration_fee_amount', { amount: value.entry_fee })}</Text>
        ) : null}
      </Stack>
    </Group>
  );
}

function Result({
  result,
  classes,
  onAnother,
}: {
  result: PublicRegistrationResult;
  classes: PublicRegistrationClass[];
  onAnother: () => void;
}) {
  const { t } = useTranslation();
  const anyWaitlist = result.teams.some((team) => team.registration_status === 'WAITLIST');
  const allWaitlist = result.teams.every((team) => team.registration_status === 'WAITLIST');
  const className = (id: number) => classes.find((c) => c.id === id)?.name ?? '';
  return (
    <Card withBorder radius="md" p="xl">
      <Stack align="center" ta="center">
        <ThemeIcon size={64} radius="xl" color={allWaitlist ? 'orange' : 'green'}>
          {allWaitlist ? <IconHourglass size={36} /> : <IconCircleCheck size={36} />}
        </ThemeIcon>
        <Title order={2}>
          {allWaitlist
            ? t('registration_waitlist_title')
            : t('registration_done_title', { count: result.teams.length })}
        </Title>
        <Stack gap="xs" w="100%">
          {result.teams.map((team) => (
            <Group key={`${team.category_id}:${team.team_name}`} justify="space-between">
              <Text fw={500}>
                {team.team_name}{' '}
                <Text span c="dimmed" size="sm">
                  {className(team.category_id)}
                </Text>
              </Text>
              {team.registration_status === 'WAITLIST' ? (
                <Badge color="orange">
                  {t('registration_waitlist_place', { place: team.waitlist_place ?? '?' })}
                </Badge>
              ) : (
                <Badge color="green">{t('registration_registered_badge')}</Badge>
              )}
            </Group>
          ))}
        </Stack>
        <Text size="sm" c="dimmed">
          {anyWaitlist ? t('registration_waitlist_note') : t('registration_done_note')}
        </Text>
        <Button variant="light" onClick={onAnother}>
          {t('registration_another_button')}
        </Button>
      </Stack>
    </Card>
  );
}

interface TeamRow {
  category_id: string;
  team_name: string;
  squad_size: number | string;
}

/** A name for the next team of the club in a class: "Brann", then "Brann 2", ... */
function suggestedName(club: string, rows: TeamRow[], categoryId: string) {
  const inClass = rows.filter((row) => row.category_id === categoryId).length;
  if (club.trim() === '') return '';
  return inClass === 0 ? club.trim() : `${club.trim()} ${inClass + 1}`;
}

export default function DashboardRegisterPage() {
  const { t } = useTranslation();
  const tournamentDataFull = getTournamentResponseByEndpointName();
  const tournamentValid = !React.isValidElement(tournamentDataFull);
  const tournamentId = tournamentValid ? tournamentDataFull.id : null;
  const swrClassesResponse = getOpenClasses(tournamentId);
  const [result, setResult] = useState<PublicRegistrationResult | null>(null);
  const [loading, setLoading] = useState(false);

  const form = useForm({
    initialValues: {
      teams: [{ category_id: '', team_name: '', squad_size: '' }] as TeamRow[],
      club_name: '',
      contact_name: '',
      contact_email: '',
      contact_phone: '',
      comment: '',
      consent: false,
      website: '',
    },
    validate: {
      teams: {
        category_id: (value) => (value === '' ? t('registration_choose_class_validation') : null),
        team_name: (value) => (value.trim().length > 0 ? null : t('too_short_name_validation')),
      },
      contact_name: (value) => (value.trim().length > 0 ? null : t('too_short_name_validation')),
      contact_email: (value) =>
        EMAIL_PATTERN.test(value.trim()) ? null : t('registration_email_validation'),
      contact_phone: (value) =>
        PHONE_PATTERN.test(value.trim()) ? null : t('registration_phone_validation'),
      consent: (value) => (value ? null : t('registration_consent_validation')),
    },
  });

  // Only one class open: choose it already
  const openClasses = swrClassesResponse.data?.data;
  const onlyClassId = openClasses != null && openClasses.length === 1 ? openClasses[0].id : null;
  useEffect(() => {
    if (onlyClassId != null && form.values.teams[0]?.category_id === '') {
      form.setFieldValue('teams.0.category_id', `${onlyClassId}`);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onlyClassId, form.values.teams[0]?.category_id]);

  if (!tournamentValid) return tournamentDataFull;
  setTitle(getTournamentHeadTitle(tournamentDataFull));
  const classes = swrClassesResponse.data?.data;

  let content;
  if (classes == null) {
    content = <TableSkeletonTwoColumns />;
  } else if (result != null) {
    content = (
      <Result
        result={result}
        classes={classes}
        onAnother={() => {
          setResult(null);
          form.setValues({
            teams: [
              {
                category_id: onlyClassId != null ? `${onlyClassId}` : '',
                team_name: '',
                squad_size: '',
              },
            ],
            comment: '',
          });
          swrClassesResponse.mutate();
        }}
      />
    );
  } else if (classes.length < 1) {
    content = (
      <NoContent
        title={t('registration_closed_title')}
        description={t('registration_closed_description')}
      />
    );
  } else {
    content = (
      <form
        onSubmit={form.onSubmit(async (values) => {
          setLoading(true);
          const response = await registerTeam(tournamentDataFull.id, {
            category_id: null,
            team_name: null,
            teams: values.teams.map((row) => ({
              category_id: Number(row.category_id),
              team_name: row.team_name.trim(),
              squad_size: row.squad_size === '' ? null : Number(row.squad_size),
            })),
            club_name: values.club_name.trim() === '' ? null : values.club_name.trim(),
            contact_name: values.contact_name.trim(),
            contact_email: values.contact_email.trim(),
            contact_phone: values.contact_phone.trim(),
            comment: values.comment.trim() === '' ? null : values.comment.trim(),
            consent: true,
            website: values.website,
          });
          setLoading(false);
          if (requestSucceeded(response) && 'data' in response) setResult(response.data.data);
        })}
      >
        <Stack>
          <Stack gap="xs">
            <Text fw={500} size="sm">
              {t('registration_open_classes_label')}
            </Text>
            {classes.map((value) => (
              <Card key={value.id} withBorder radius="md" p="sm">
                <ClassOption value={value} />
              </Card>
            ))}
          </Stack>
          <TextInput
            size="md"
            label={t('club_name_input_label')}
            description={t('registration_club_description')}
            maxLength={50}
            {...form.getInputProps('club_name')}
            onBlur={() => {
              // Suggest team names from the club once it's typed
              form.values.teams.forEach((row, index) => {
                if (row.team_name.trim() === '') {
                  form.setFieldValue(
                    `teams.${index}.team_name`,
                    suggestedName(
                      form.values.club_name,
                      form.values.teams.slice(0, index),
                      row.category_id,
                    ),
                  );
                }
              });
            }}
          />
          <Title order={4} mt="sm">
            {t('registration_teams_title')}
          </Title>
          {form.values.teams.map((row, index) => (
            <Card key={index} withBorder radius="md" p="sm">
              <Stack gap="xs">
                <Group justify="space-between">
                  <Text fw={600}>{t('registration_team_number', { number: index + 1 })}</Text>
                  {form.values.teams.length > 1 ? (
                    <Button
                      variant="subtle"
                      color="red"
                      size="xs"
                      onClick={() => form.removeListItem('teams', index)}
                    >
                      {t('registration_remove_team_button')}
                    </Button>
                  ) : null}
                </Group>
                <Select
                  withAsterisk
                  size="md"
                  label={t('registration_class_label')}
                  data={classes.map((value) => ({ value: `${value.id}`, label: value.name }))}
                  allowDeselect={false}
                  {...form.getInputProps(`teams.${index}.category_id`)}
                />
                <TextInput
                  withAsterisk
                  size="md"
                  label={t('registration_team_name_label')}
                  placeholder={t('registration_team_name_placeholder')}
                  maxLength={50}
                  {...form.getInputProps(`teams.${index}.team_name`)}
                />
                <NumberInput
                  size="md"
                  label={t('squad_size_label')}
                  description={t('squad_size_description')}
                  min={1}
                  max={60}
                  inputMode="numeric"
                  {...form.getInputProps(`teams.${index}.squad_size`)}
                />
              </Stack>
            </Card>
          ))}
          {form.values.teams.length < 10 ? (
            <Button
              variant="light"
              leftSection={<IconPlus size={18} />}
              onClick={() => {
                const previous = form.values.teams[form.values.teams.length - 1];
                const categoryId = previous?.category_id ?? '';
                form.insertListItem('teams', {
                  category_id: categoryId,
                  team_name: suggestedName(form.values.club_name, form.values.teams, categoryId),
                  squad_size: '',
                });
              }}
            >
              {t('registration_add_team_button')}
            </Button>
          ) : null}
          <Title order={4} mt="sm">
            {t('registration_contact_title')}
          </Title>
          <TextInput
            withAsterisk
            size="md"
            label={t('registration_contact_name_label')}
            autoComplete="name"
            maxLength={100}
            {...form.getInputProps('contact_name')}
          />
          <TextInput
            withAsterisk
            size="md"
            type="email"
            inputMode="email"
            autoComplete="email"
            label={t('email_input_label')}
            maxLength={254}
            {...form.getInputProps('contact_email')}
          />
          <TextInput
            withAsterisk
            size="md"
            type="tel"
            inputMode="tel"
            autoComplete="tel"
            label={t('registration_phone_label')}
            placeholder="+47 912 34 567"
            maxLength={21}
            {...form.getInputProps('contact_phone')}
          />
          <Textarea
            size="md"
            label={t('registration_comment_label')}
            autosize
            minRows={2}
            maxLength={500}
            {...form.getInputProps('comment')}
          />
          {/* Honeypot: hidden from people, bots fill it in */}
          <div aria-hidden="true" style={{ position: 'absolute', left: '-10000px' }}>
            <input
              type="text"
              tabIndex={-1}
              autoComplete="off"
              {...form.getInputProps('website')}
            />
          </div>
          <Checkbox
            label={t('registration_consent_label')}
            {...form.getInputProps('consent', { type: 'checkbox' })}
          />
          <Button type="submit" size="lg" loading={loading} fullWidth>
            {form.values.teams.length > 1
              ? t('registration_submit_teams_button', { count: form.values.teams.length })
              : t('registration_submit_button')}
          </Button>
        </Stack>
      </form>
    );
  }

  return (
    <>
      <DoubleHeader tournamentData={tournamentDataFull} />
      <Container size="xs" px="md">
        <Stack>
          <Title>{t('registration_title')}</Title>
          {result == null && classes != null && classes.length > 0 ? (
            <Alert color="gray">{t('registration_description')}</Alert>
          ) : null}
          {content}
        </Stack>
      </Container>
      <DashboardFooter />
    </>
  );
}
