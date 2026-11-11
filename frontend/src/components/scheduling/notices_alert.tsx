import { Alert, Button, Group, Stack, Text } from '@mantine/core';
import { IconBell, IconCheck } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

import { Time } from '@components/utils/datetime';
import { Court } from '@openapi';
import { getNotices, resolveNotice } from '@services/score_links';

/** Unresolved reports from the pitches, e.g. "Bane 2: 10 minutes late". */
export default function NoticesAlert({
  tournamentId,
  courts,
}: {
  tournamentId: number;
  courts: Court[];
}) {
  const { t } = useTranslation();
  const swrNotices = getNotices(tournamentId);
  const open = (swrNotices.data?.data ?? []).filter((notice) => !notice.resolved);
  if (open.length < 1) return null;

  const courtName = (id: number | null) =>
    id == null ? t('score_link_all_courts') : (courts.find((c) => c.id === id)?.name ?? '?');

  return (
    <Alert color="orange" icon={<IconBell />} title={t('notices_title')} mb="md">
      <Stack gap="xs">
        {open.map((notice) => (
          <Group key={notice.id} justify="space-between" wrap="nowrap">
            <Text size="sm">
              <Time datetime={notice.created} /> · <b>{courtName(notice.court_id)}</b>
              {notice.delay_minutes != null
                ? ` · ${t('notice_delay', { minutes: notice.delay_minutes })}`
                : ''}
              {notice.message !== '' ? ` · ${notice.message}` : ''}
            </Text>
            <Button
              size="xs"
              variant="light"
              color="green"
              leftSection={<IconCheck size={14} />}
              onClick={async () => {
                await resolveNotice(tournamentId, notice.id);
                await swrNotices.mutate();
              }}
            >
              {t('notice_resolve_button')}
            </Button>
          </Group>
        ))}
      </Stack>
    </Alert>
  );
}
