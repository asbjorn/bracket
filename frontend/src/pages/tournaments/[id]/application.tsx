import {
  Alert,
  Button,
  Card,
  CopyButton,
  Group,
  List,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Textarea,
  Title,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { IconAlertTriangle, IconCheck, IconCopy, IconDeviceFloppy } from '@tabler/icons-react';
import { TFunction } from 'i18next';
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import useSWR from 'swr';

import { PrintButton } from '@components/print/print_button';
import { getTournamentIdFromRouter } from '@components/utils/util';
import { contentLanguage } from '@components/utils/language';
import { DistrictApplication, DistrictApplicationResponse, TournamentDetails } from '@openapi';
import TournamentLayout from '@pages/tournaments/_tournament_layout';
import { createAxios, requestSucceeded } from '@services/adapter';
import { saveTournamentDetails } from '@services/district_application';

const EMPTY_DETAILS: TournamentDetails = {
  organiser_club: null,
  contact_name: null,
  contact_phone: null,
  contact_email: null,
  jury_chair_name: null,
  jury_chair_phone: null,
  venue: null,
  rules_summary: null,
  notes: null,
};

type DetailField = keyof TournamentDetails;

const SHORT_FIELDS: DetailField[] = [
  'organiser_club',
  'venue',
  'contact_name',
  'contact_phone',
  'contact_email',
  'jury_chair_name',
  'jury_chair_phone',
];

function formatDay(day: string, language: string) {
  return new Intl.DateTimeFormat(language === 'nb' ? 'nb-NO' : 'en-GB', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(`${day}T00:00:00Z`));
}

/** What the district needs but is still missing, so the organiser can fill it in first. */
function missingItems(application: DistrictApplication, t: TFunction): string[] {
  const missing: string[] = [];
  const { details } = application;
  if (!details.organiser_club) missing.push(t('application_field_organiser_club'));
  if (!details.contact_name || !details.contact_phone) {
    missing.push(t('application_field_contact_name'));
  }
  // The jury is kept on the discipline page; the old chair fields count when it's empty
  if (application.jury_members.length > 0) {
    for (const warning of application.jury_warnings) {
      missing.push(t(`jury_warning_${warning.toLowerCase()}`));
    }
  } else if (!details.jury_chair_name || !details.jury_chair_phone) {
    missing.push(t('application_missing_jury'));
  }
  if (!details.venue) missing.push(t('application_field_venue'));
  if (application.days.length < 1) missing.push(t('application_missing_days'));
  if (application.classes.length < 1) missing.push(t('application_missing_classes'));
  if (application.courts.length < 1) missing.push(t('application_missing_courts'));
  return missing;
}

/** Plain text in the language of the page, to paste into the application in FIKS. */
function applicationText(application: DistrictApplication, t: TFunction, language: string): string {
  const { details } = application;
  const dash = '–';
  const value = (text: string | null | undefined) => (text ? text : dash);
  const lines: string[] = [
    t('application_text_heading').toUpperCase(),
    '',
    `${t('application_text_tournament')}: ${application.tournament_name}`,
    `${t('application_field_organiser_club')}: ${value(details.organiser_club)}`,
    `${t('application_field_venue')}: ${value(details.venue)}`,
    `${t('application_text_contact')}: ${
      [details.contact_name, details.contact_phone, details.contact_email]
        .filter(Boolean)
        .join(', ') || dash
    }`,
    ...(application.jury_members.length > 0
      ? [
          `${t('application_text_jury')}:`,
          ...application.jury_members.map(
            (member) =>
              `  - ${[
                member.name,
                member.role === 'CHAIR' ? t('jury_role_chair') : null,
                member.club_name,
                member.phone,
              ]
                .filter(Boolean)
                .join(', ')}`,
          ),
        ]
      : [
          `${t('application_text_jury_chair')}: ${
            [details.jury_chair_name, details.jury_chair_phone].filter(Boolean).join(', ') || dash
          }`,
        ]),
    '',
    `${t('application_text_days')}:`,
  ];
  if (application.days.length < 1) lines.push(`  ${dash}`);
  for (const day of application.days) {
    const windows = day.windows.length > 1 ? ` (${day.windows.join(', ')})` : '';
    lines.push(`  - ${formatDay(day.day, language)}: ${day.first_start}-${day.last_end}${windows}`);
  }
  const courtCount = application.courts.reduce((sum, court) => sum + court.count, 0);
  const courts = application.courts
    .map((court) => `${court.count} × ${court.game_format ?? t('game_format_any')}`)
    .join(', ');
  lines.push(
    '',
    `${t('application_text_courts')}: ${courtCount > 0 ? `${courts} (${courtCount})` : dash}`,
  );
  lines.push('', `${t('application_text_classes')}:`);
  if (application.classes.length < 1) lines.push(`  ${dash}`);
  for (const item of application.classes) {
    const parts = [
      item.game_format ?? t('game_format_any'),
      t('application_text_match_length', {
        duration: item.duration_minutes,
        margin: item.margin_minutes,
      }),
      item.max_teams != null
        ? t('application_text_teams_of_max', { count: item.team_count, max: item.max_teams })
        : t('application_text_teams', { count: item.team_count }),
      t('application_text_matches', { count: item.match_count }),
      item.has_playoffs ? t('application_text_with_playoffs') : t('application_text_no_playoffs'),
      item.results_public
        ? t('application_text_results_public')
        : t('application_text_results_hidden'),
    ];
    if (item.entry_fee != null) {
      parts.push(t('application_text_fee', { fee: item.entry_fee }));
    }
    const age = item.age != null ? ` (${t('application_text_age', { age: item.age })})` : '';
    lines.push(`  - ${item.name}${age}: ${parts.join(', ')}`);
  }
  lines.push(
    '',
    t('application_text_totals', {
      teams: application.team_count,
      matches: application.match_count,
    }),
  );
  const rules = details.rules_summary || application.rules_text;
  lines.push('', `${t('application_text_rules')}:`, rules ? rules : dash);
  if (details.notes) lines.push('', `${t('application_field_notes')}:`, details.notes);
  return lines.join('\n');
}

export default function DistrictApplicationPage() {
  const { t, i18n } = useTranslation();
  const { tournamentData } = getTournamentIdFromRouter();
  const swr = useSWR<DistrictApplicationResponse>(
    `tournaments/${tournamentData.id}/district_application`,
    (url: string) =>
      createAxios()
        .get(url)
        .then((res) => res.data),
  );
  const application = swr.data?.data ?? null;

  const form = useForm<Record<DetailField, string>>({
    initialValues: Object.fromEntries(Object.keys(EMPTY_DETAILS).map((key) => [key, ''])) as Record<
      DetailField,
      string
    >,
  });

  // Fill the form once the saved details are loaded
  useEffect(() => {
    if (application == null || form.isDirty()) return;
    const values = Object.fromEntries(
      Object.entries(application.details).map(([key, value]) => [key, value ?? '']),
    ) as Record<DetailField, string>;
    form.setValues(values);
    form.resetDirty(values);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [application]);

  // The text follows what is typed, also before it is saved
  const preview: DistrictApplication | null =
    application == null
      ? null
      : {
          ...application,
          details: Object.fromEntries(
            Object.entries(form.values).map(([key, value]) => [key, value.trim() || null]),
          ) as TournamentDetails,
        };
  const text = preview != null ? applicationText(preview, t, contentLanguage(i18n)) : '';
  const missing = preview != null ? missingItems(preview, t) : [];

  return (
    <TournamentLayout tournament_id={tournamentData.id}>
      <Stack>
        <Group justify="space-between" className="no-print">
          <div>
            <Title>{t('application_title')}</Title>
            <Text c="dimmed">{t('application_description')}</Text>
          </div>
          <Group>
            <CopyButton value={text}>
              {({ copied, copy }) => (
                <Button
                  color={copied ? 'green' : 'indigo'}
                  leftSection={copied ? <IconCheck size={18} /> : <IconCopy size={18} />}
                  onClick={copy}
                  disabled={preview == null}
                >
                  {copied ? t('application_copied') : t('application_copy_button')}
                </Button>
              )}
            </CopyButton>
            <PrintButton />
          </Group>
        </Group>

        {missing.length > 0 ? (
          <Alert
            className="no-print"
            color="orange"
            icon={<IconAlertTriangle />}
            title={t('application_missing_title')}
          >
            <List size="sm">
              {missing.map((item) => (
                <List.Item key={item}>{item}</List.Item>
              ))}
            </List>
          </Alert>
        ) : null}

        <SimpleGrid cols={{ base: 1, md: 2 }}>
          <Card withBorder className="no-print">
            <form
              onSubmit={form.onSubmit(async (values) => {
                const details = Object.fromEntries(
                  Object.entries(values).map(([key, value]) => [key, value.trim() || null]),
                ) as TournamentDetails;
                const response = await saveTournamentDetails(tournamentData.id, details);
                if (requestSucceeded(response)) {
                  form.resetDirty();
                  await swr.mutate();
                }
              })}
            >
              <Stack>
                <Title order={3}>{t('application_details_title')}</Title>
                {SHORT_FIELDS.map((field) => (
                  <TextInput
                    key={field}
                    label={t(`application_field_${field}`)}
                    maxLength={200}
                    {...form.getInputProps(field)}
                  />
                ))}
                <Textarea
                  label={t('application_field_rules_summary')}
                  description={t('application_rules_summary_description')}
                  autosize
                  minRows={3}
                  maxLength={4000}
                  {...form.getInputProps('rules_summary')}
                />
                <Textarea
                  label={t('application_field_notes')}
                  autosize
                  minRows={2}
                  maxLength={4000}
                  {...form.getInputProps('notes')}
                />
                <Group justify="right">
                  <Button
                    type="submit"
                    leftSection={<IconDeviceFloppy size={18} />}
                    disabled={!form.isDirty()}
                  >
                    {t('save_button')}
                  </Button>
                </Group>
              </Stack>
            </form>
          </Card>
          <Card withBorder>
            <Stack>
              <Title order={3} className="no-print">
                {t('application_text_title')}
              </Title>
              <Text
                component="pre"
                ff="monospace"
                size="sm"
                style={{ whiteSpace: 'pre-wrap', margin: 0 }}
              >
                {text}
              </Text>
            </Stack>
          </Card>
        </SimpleGrid>
      </Stack>
    </TournamentLayout>
  );
}
