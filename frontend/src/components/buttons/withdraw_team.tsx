import { Button, Group, Modal, Stack, Text } from '@mantine/core';
import { showNotification } from '@mantine/notifications';
import { IconArrowBackUp, IconFlagOff } from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { FullTeamWithPlayers } from '@openapi';
import { requestSucceeded } from '@services/adapter';
import { reinstateTeam, withdrawTeam } from '@services/team';

/** Withdraw a team (its remaining matches become walkovers), with a confirmation first. */
export default function WithdrawButton({
  tournamentId,
  team,
  onChanged,
}: {
  tournamentId: number;
  team: FullTeamWithPlayers;
  onChanged: () => Promise<void>;
}) {
  const { t } = useTranslation();
  const [opened, setOpened] = useState(false);
  const [loading, setLoading] = useState(false);

  if (team.withdrawn) {
    return (
      <Button
        size="xs"
        variant="default"
        mx="xs"
        leftSection={<IconArrowBackUp size={18} />}
        onClick={async () => {
          await reinstateTeam(tournamentId, team.id);
          showNotification({ message: t('team_reinstated_message', { team: team.name }) });
          await onChanged();
        }}
      >
        {t('reinstate_team_button')}
      </Button>
    );
  }

  return (
    <>
      <Button
        size="xs"
        color="orange"
        variant="light"
        mx="xs"
        leftSection={<IconFlagOff size={18} />}
        onClick={() => setOpened(true)}
      >
        {t('withdraw_team_button')}
      </Button>
      <Modal
        opened={opened}
        onClose={() => setOpened(false)}
        title={t('withdraw_team_title', { team: team.name })}
        centered
      >
        <Stack>
          <Text size="sm">{t('withdraw_team_description')}</Text>
          <Group justify="right">
            <Button variant="default" onClick={() => setOpened(false)}>
              {t('cancel_button')}
            </Button>
            <Button
              color="orange"
              loading={loading}
              onClick={async () => {
                setLoading(true);
                const response = await withdrawTeam(tournamentId, team.id);
                setLoading(false);
                if (requestSucceeded(response) && 'data' in response) {
                  showNotification({
                    color: 'orange',
                    message: t('team_withdrawn_message', {
                      team: team.name,
                      count: response.data.data,
                    }),
                  });
                  setOpened(false);
                  await onChanged();
                }
              }}
            >
              {t('withdraw_team_button')}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
}
