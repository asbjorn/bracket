import {
  Anchor,
  Badge,
  Button,
  Checkbox,
  Fieldset,
  Group,
  List,
  SegmentedControl,
  Stack,
  Text,
  Textarea,
} from '@mantine/core';
import { DateTimePicker } from '@mantine/dates';
import { IconArrowRight } from '@tabler/icons-react';
import { showNotification } from '@mantine/notifications';
import dayjs from 'dayjs';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { NotificationsSettings } from '@components/notifications/notifications_panel';
import { getBaseURL } from '@components/utils/util';
import { AnnouncementLevel, Tournament } from '@openapi';
import { requestSucceeded } from '@services/adapter';
import { getNotificationStatus, sendAnnouncementEmail } from '@services/notifications';
import { getAnnouncement, getRules, saveAnnouncement, saveRules } from '@services/public_info';

function saved(t: (key: string) => string) {
  showNotification({ color: 'green', title: t('saved_notification'), message: '' });
}

/** The banner on all public pages, e.g. a weather warning; optionally until a moment. */
export function AnnouncementEditor({ tournamentId }: { tournamentId: number }) {
  const { t } = useTranslation();
  const swrAnnouncement = getAnnouncement(tournamentId);
  const current = swrAnnouncement.data?.data ?? null;
  const [text, setText] = useState('');
  const [level, setLevel] = useState<AnnouncementLevel>('INFO');
  const [until, setUntil] = useState<string | null>(null);
  const [alsoEmail, setAlsoEmail] = useState(false);
  const notificationStatus = getNotificationStatus(tournamentId).data?.data;
  const canEmail =
    notificationStatus != null &&
    notificationStatus.email_enabled &&
    notificationStatus.contact_emails.length > 0;

  useEffect(() => {
    setText(current?.text ?? '');
    setLevel(current?.level ?? 'INFO');
    setUntil(current?.until != null ? dayjs(current.until).format('YYYY-MM-DD HH:mm:ss') : null);
  }, [swrAnnouncement.data]);

  const expired = current?.until != null && dayjs(current.until).isBefore(dayjs());

  return (
    <Stack>
      <Group gap="xs">
        <Text size="sm" c="dimmed">
          {t('announcement_description')}
        </Text>
        {current != null ? (
          <Badge color={expired ? 'gray' : 'green'}>
            {expired ? t('announcement_expired_badge') : t('announcement_shown_badge')}
          </Badge>
        ) : null}
      </Group>
      <Textarea
        label={t('announcement_text_label')}
        placeholder={t('announcement_text_placeholder')}
        value={text}
        maxLength={500}
        autosize
        minRows={2}
        onChange={(event) => setText(event.currentTarget.value)}
      />
      <Group align="end">
        <SegmentedControl
          value={level}
          onChange={(value) => setLevel(value as AnnouncementLevel)}
          data={[
            { value: 'INFO', label: t('announcement_level_info') },
            { value: 'WARNING', label: t('announcement_level_warning') },
          ]}
        />
        <DateTimePicker
          label={t('announcement_until_label')}
          placeholder={t('announcement_until_placeholder')}
          value={until}
          onChange={setUntil}
          clearable
          w="16rem"
        />
      </Group>
      {canEmail ? (
        <Checkbox
          label={t('announcement_also_email_label', {
            count: notificationStatus.contact_emails.length,
          })}
          checked={alsoEmail}
          onChange={(event) => setAlsoEmail(event.currentTarget.checked)}
        />
      ) : null}
      <Group>
        <Button
          disabled={text.trim() === ''}
          onClick={async () => {
            const response = await saveAnnouncement(tournamentId, {
              text,
              level,
              until: until != null ? dayjs(until).toISOString() : null,
            });
            if (requestSucceeded(response)) {
              await swrAnnouncement.mutate();
              saved(t);
              if (canEmail && alsoEmail) {
                const sent = await sendAnnouncementEmail(tournamentId);
                if (requestSucceeded(sent) && 'data' in sent) {
                  showNotification({
                    color: 'green',
                    title: t('announcement_emailed', { count: sent.data.data }),
                    message: '',
                  });
                }
                setAlsoEmail(false);
              }
            }
          }}
        >
          {t('announcement_publish_button')}
        </Button>
        {current != null ? (
          <Button
            variant="default"
            color="red"
            onClick={async () => {
              const response = await saveAnnouncement(tournamentId, null);
              if (requestSucceeded(response)) {
                await swrAnnouncement.mutate();
                saved(t);
              }
            }}
          >
            {t('announcement_remove_button')}
          </Button>
        ) : null}
      </Group>
    </Stack>
  );
}

export function RulesEditor({ tournamentId }: { tournamentId: number }) {
  const { t } = useTranslation();
  const swrRules = getRules(tournamentId);
  const [text, setText] = useState('');
  useEffect(() => setText(swrRules.data?.data.text ?? ''), [swrRules.data]);

  return (
    <Stack>
      <Textarea
        description={t('rules_description')}
        placeholder={t('rules_placeholder')}
        value={text}
        maxLength={20000}
        autosize
        minRows={6}
        maxRows={24}
        onChange={(event) => setText(event.currentTarget.value)}
      />
      <Group>
        <Button
          onClick={async () => {
            const response = await saveRules(tournamentId, text);
            if (requestSucceeded(response)) {
              await swrRules.mutate();
              saved(t);
            }
          }}
        >
          {t('save_button')}
        </Button>
      </Group>
    </Stack>
  );
}

/** Links to the public pages, for sharing and for setting up a big screen. */
export function PublicPagesLinks({ tournament }: { tournament: Tournament }) {
  const { t } = useTranslation();
  if (!tournament.dashboard_public || tournament.dashboard_endpoint == null) {
    return <Text size="sm">{t('public_pages_not_public')}</Text>;
  }
  const base = `${getBaseURL()}/tournaments/${tournament.dashboard_endpoint}/dashboard`;
  const links = [
    { label: t('dashboard_matches_tab'), url: base },
    { label: t('dashboard_teams_tab'), url: `${base}/teams` },
    { label: t('dashboard_courts_tab'), url: `${base}/courts` },
    { label: t('dashboard_rules_tab'), url: `${base}/rules` },
    { label: t('big_screen_link'), url: `${base}/present/rotation?seconds=20` },
    { label: t('poster_button'), url: `${base}/poster` },
  ];
  return (
    <List size="sm" spacing={4}>
      {links.map((link) => (
        <List.Item key={link.url}>
          <Anchor href={link.url} target="_blank">
            {link.label}
          </Anchor>
        </List.Item>
      ))}
    </List>
  );
}

export function PublicInfoSettings({ tournament }: { tournament: Tournament }) {
  const { t } = useTranslation();
  return (
    <>
      <Fieldset legend={t('public_pages_legend')} mt="lg" radius="md">
        <PublicPagesLinks tournament={tournament} />
      </Fieldset>
      <Fieldset legend={t('announcement_legend')} mt="lg" radius="md">
        <AnnouncementEditor tournamentId={tournament.id} />
      </Fieldset>
      <Fieldset legend={t('rules_title')} mt="lg" radius="md">
        <RulesEditor tournamentId={tournament.id} />
      </Fieldset>
      <Fieldset legend={t('notifications_title')} mt="lg" radius="md">
        <NotificationsSettings tournamentId={tournament.id} />
      </Fieldset>
      <Fieldset legend={t('application_title')} mt="lg" radius="md">
        <Group justify="space-between">
          <Text size="sm" c="dimmed" maw="32rem">
            {t('application_description')}
          </Text>
          <Button
            component={Link}
            to={`/tournaments/${tournament.id}/application`}
            variant="light"
            rightSection={<IconArrowRight size={18} />}
          >
            {t('application_open_button')}
          </Button>
        </Group>
      </Fieldset>
    </>
  );
}
