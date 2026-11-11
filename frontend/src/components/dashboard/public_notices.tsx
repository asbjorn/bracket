import { Alert, Stack } from '@mantine/core';
import { IconAlertTriangle, IconClockPause, IconInfoCircle } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

import { getPublicNotices } from '@services/public_info';

/**
 * The organiser's announcement and delays reported from the pitches, on every public page.
 * Refreshes by itself, so a big screen shows changes without reloading.
 */
export function PublicNoticesBanner({
  tournamentId,
  size = 'md',
}: {
  tournamentId: number;
  size?: 'md' | 'xl';
}) {
  const { t } = useTranslation();
  const notices = getPublicNotices(tournamentId).data?.data;
  if (notices == null || (notices.announcement == null && notices.delays.length < 1)) {
    return null;
  }
  const { announcement } = notices;
  const style = size === 'xl' ? { fontSize: '1.6rem' } : undefined;

  return (
    <Stack gap="xs" my="sm">
      {announcement != null ? (
        <Alert
          color={announcement.level === 'WARNING' ? 'orange' : 'blue'}
          variant={announcement.level === 'WARNING' ? 'filled' : 'light'}
          icon={announcement.level === 'WARNING' ? <IconAlertTriangle /> : <IconInfoCircle />}
          styles={{ message: { ...style, whiteSpace: 'pre-wrap' } }}
        >
          {announcement.text}
        </Alert>
      ) : null}
      {notices.delays.map((delay) => (
        <Alert
          key={`${delay.court_name}-${delay.created}`}
          color="yellow"
          icon={<IconClockPause />}
          styles={{ message: style }}
        >
          {delay.court_name != null
            ? t('public_delay_on_court', { court: delay.court_name, minutes: delay.delay_minutes })
            : t('public_delay', { minutes: delay.delay_minutes })}
        </Alert>
      ))}
    </Stack>
  );
}
