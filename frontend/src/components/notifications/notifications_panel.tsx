import {
  Alert,
  Badge,
  Button,
  CopyButton,
  Group,
  Modal,
  SegmentedControl,
  Stack,
  Table,
  Text,
} from '@mantine/core';
import { showNotification } from '@mantine/notifications';
import { IconCheck, IconCopy, IconMail, IconMailForward } from '@tabler/icons-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { DateTime } from '@components/utils/datetime';
import { EmailLanguage, ScheduleNoticeResult } from '@openapi';
import { requestSucceeded } from '@services/adapter';
import {
  getNotificationStatus,
  saveEmailLanguage,
  sendScheduleNotices,
} from '@services/notifications';

const STATUS_COLORS: Record<string, string> = {
  PENDING: 'yellow',
  SENDING: 'yellow',
  SENT: 'green',
  FAILED: 'red',
};

/** Without email on the server: the organiser writes the email themselves, all teams in BCC. */
export function ContactsFallback({ emails }: { emails: string[] }) {
  const { t } = useTranslation();
  return (
    <Alert color="gray" icon={<IconMail />} title={t('notifications_not_set_up_title')}>
      <Stack gap="xs">
        <Text size="sm">{t('notifications_not_set_up_description', { count: emails.length })}</Text>
        {emails.length > 0 ? (
          <Group>
            <CopyButton value={emails.join(', ')}>
              {({ copied, copy }) => (
                <Button
                  size="xs"
                  variant="default"
                  leftSection={copied ? <IconCheck size={16} /> : <IconCopy size={16} />}
                  onClick={copy}
                >
                  {copied ? t('application_copied') : t('notifications_copy_addresses')}
                </Button>
              )}
            </CopyButton>
            <Button
              size="xs"
              variant="default"
              component="a"
              href={`mailto:?bcc=${encodeURIComponent(emails.join(','))}`}
              leftSection={<IconMailForward size={16} />}
            >
              {t('notifications_open_mail_program')}
            </Button>
          </Group>
        ) : null}
      </Stack>
    </Alert>
  );
}

/** Settings page: whether email works, the language, and what was sent. */
export function NotificationsSettings({ tournamentId }: { tournamentId: number }) {
  const { t } = useTranslation();
  const swrStatus = getNotificationStatus(tournamentId);
  const status = swrStatus.data?.data;
  if (status == null) return null;

  return (
    <Stack>
      <Text size="sm" c="dimmed">
        {t('notifications_description')}
      </Text>
      {status.email_enabled ? (
        <Group>
          <Badge color="green" variant="light">
            {t('notifications_enabled_badge')}
          </Badge>
          <Text size="sm">
            {t('notifications_counts', {
              sent: status.sent,
              pending: status.pending,
              failed: status.failed,
            })}
          </Text>
        </Group>
      ) : (
        <ContactsFallback emails={status.contact_emails} />
      )}
      <Group>
        <Text size="sm">{t('notifications_language_label')}</Text>
        <SegmentedControl
          size="xs"
          value={status.language}
          data={[
            { value: 'nb', label: 'Norsk' },
            { value: 'en', label: 'English' },
          ]}
          onChange={async (value) => {
            const response = await saveEmailLanguage(tournamentId, value as EmailLanguage);
            if (requestSucceeded(response)) await swrStatus.mutate();
          }}
        />
      </Group>
      {status.recent.length > 0 ? (
        <Table.ScrollContainer minWidth={500}>
          <Table striped>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('notifications_time_header')}</Table.Th>
                <Table.Th>{t('notifications_what_header')}</Table.Th>
                <Table.Th>{t('teams_title')}</Table.Th>
                <Table.Th>{t('notifications_status_header')}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {status.recent.map((notification, index) => (
                <Table.Tr key={index}>
                  <Table.Td>
                    <DateTime datetime={notification.created} />
                  </Table.Td>
                  <Table.Td>{t(`notifications_kind_${notification.kind.toLowerCase()}`)}</Table.Td>
                  <Table.Td>{notification.team_name ?? notification.recipient}</Table.Td>
                  <Table.Td>
                    <Badge
                      color={STATUS_COLORS[notification.status] ?? 'gray'}
                      variant="light"
                      title={notification.error ?? undefined}
                    >
                      {t(`notifications_status_${notification.status.toLowerCase()}`)}
                    </Badge>
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

/** Planning page: email each team its new times after the schedule changed. */
export function ScheduleNotice({ tournamentId }: { tournamentId: number }) {
  const { t } = useTranslation();
  const swrStatus = getNotificationStatus(tournamentId);
  const status = swrStatus.data?.data;
  const [preview, setPreview] = useState<ScheduleNoticeResult | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [loading, setLoading] = useState(false);

  async function refresh() {
    const response = await sendScheduleNotices(tournamentId, true);
    if (requestSucceeded(response) && 'data' in response) setPreview(response.data.data);
  }

  useEffect(() => {
    refresh();
  }, [tournamentId]);

  if (status == null) return null;
  if (!status.email_enabled) return <ContactsFallback emails={status.contact_emails} />;

  return (
    <Stack>
      <Text size="sm" c="dimmed">
        {t('schedule_notice_description')}
      </Text>
      {preview != null ? (
        <Text size="sm">
          {t('schedule_notice_preview', {
            count: preview.teams_to_notify,
            total: preview.teams_with_contact,
          })}
        </Text>
      ) : null}
      <Group>
        <Button
          leftSection={<IconMailForward size={18} />}
          disabled={preview == null || preview.teams_to_notify < 1}
          onClick={() => setConfirming(true)}
        >
          {t('schedule_notice_button')}
        </Button>
        <Button variant="subtle" onClick={refresh}>
          {t('schedule_notice_refresh')}
        </Button>
      </Group>
      <Modal
        opened={confirming}
        onClose={() => setConfirming(false)}
        title={t('schedule_notice_button')}
      >
        <Stack>
          <Text size="sm">
            {t('schedule_notice_confirm', { count: preview?.teams_to_notify ?? 0 })}
          </Text>
          <Group justify="right">
            <Button variant="default" onClick={() => setConfirming(false)}>
              {t('cancel_button')}
            </Button>
            <Button
              loading={loading}
              onClick={async () => {
                setLoading(true);
                const response = await sendScheduleNotices(tournamentId, false);
                setLoading(false);
                setConfirming(false);
                if (requestSucceeded(response) && 'data' in response) {
                  showNotification({
                    color: 'green',
                    title: t('schedule_notice_sent', {
                      count: response.data.data.teams_to_notify,
                    }),
                    message: '',
                  });
                  await swrStatus.mutate();
                  await refresh();
                }
              }}
            >
              {t('notifications_send_button')}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}
