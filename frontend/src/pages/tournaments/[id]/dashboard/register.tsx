import {
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Container,
  Group,
  Radio,
  Stack,
  Text,
  TextInput,
  Textarea,
  ThemeIcon,
  Title,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { IconCircleCheck, IconHourglass } from '@tabler/icons-react';
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
  onAnother,
}: {
  result: PublicRegistrationResult;
  onAnother: () => void;
}) {
  const { t } = useTranslation();
  const waitlist = result.registration_status === 'WAITLIST';
  return (
    <Card withBorder radius="md" p="xl">
      <Stack align="center" ta="center">
        <ThemeIcon size={64} radius="xl" color={waitlist ? 'orange' : 'green'}>
          {waitlist ? <IconHourglass size={36} /> : <IconCircleCheck size={36} />}
        </ThemeIcon>
        <Title order={2}>
          {waitlist ? t('registration_waitlist_title') : t('registration_done_title')}
        </Title>
        <Text>
          {waitlist
            ? t('registration_waitlist_description', {
                team: result.team_name,
                place: result.waitlist_place ?? '?',
              })
            : t('registration_done_description', { team: result.team_name })}
        </Text>
        <Button variant="light" onClick={onAnother}>
          {t('registration_another_button')}
        </Button>
      </Stack>
    </Card>
  );
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
      category_id: '',
      team_name: '',
      club_name: '',
      contact_name: '',
      contact_email: '',
      contact_phone: '',
      comment: '',
      consent: false,
      website: '',
    },
    validate: {
      category_id: (value) => (value === '' ? t('registration_choose_class_validation') : null),
      team_name: (value) => (value.trim().length > 0 ? null : t('too_short_name_validation')),
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
    if (onlyClassId != null && form.values.category_id === '') {
      form.setFieldValue('category_id', `${onlyClassId}`);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onlyClassId, form.values.category_id]);

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
        onAnother={() => {
          setResult(null);
          form.setValues({ category_id: '', team_name: '', comment: '' });
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
            category_id: Number(values.category_id),
            team_name: values.team_name.trim(),
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
          <Radio.Group
            label={t('registration_class_label')}
            withAsterisk
            {...form.getInputProps('category_id')}
          >
            <Stack gap="xs" mt="xs">
              {classes.map((value) => (
                <Radio.Card key={value.id} value={`${value.id}`} radius="md" p="md">
                  <Group wrap="nowrap" align="flex-start">
                    <Radio.Indicator />
                    <ClassOption value={value} />
                  </Group>
                </Radio.Card>
              ))}
            </Stack>
          </Radio.Group>
          <TextInput
            withAsterisk
            size="md"
            label={t('registration_team_name_label')}
            placeholder={t('registration_team_name_placeholder')}
            maxLength={30}
            {...form.getInputProps('team_name')}
          />
          <TextInput
            size="md"
            label={t('club_name_input_label')}
            maxLength={50}
            {...form.getInputProps('club_name')}
          />
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
            {t('registration_submit_button')}
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
