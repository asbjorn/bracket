import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  CopyButton,
  Group,
  Modal,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
  Tooltip,
} from '@mantine/core';
import {
  IconCheck,
  IconCopy,
  IconLink,
  IconPrinter,
  IconQrcode,
  IconTrash,
} from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import QRCode from 'react-qr-code';

import { DayAndTime } from '@components/utils/datetime';
import { Court, ScoreLink } from '@openapi';
import { requestSucceeded } from '@services/adapter';
import {
  createScoreLink,
  getScoreLinks,
  revokeScoreLink,
  scoreLinkUrl,
} from '@services/score_links';

const VALIDITY_HOURS = [8, 24, 48, 72, 168];

function linkStatus(link: ScoreLink): 'active' | 'expired' | 'revoked' {
  if (link.revoked_at != null) return 'revoked';
  return new Date(link.expires_at) < new Date() ? 'expired' : 'active';
}

/** Shown once after creating a link: the token is not stored, so it can't be shown again. */
function NewLinkModal({
  token,
  name,
  onClose,
}: {
  token: string | null;
  name: string;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const url = token != null ? scoreLinkUrl(token) : '';
  return (
    <Modal opened={token != null} onClose={onClose} title={name} size="md" centered>
      {/* When printing, only the QR code with its name and link is printed */}
      <style>
        {`@media print {
          body * { visibility: hidden; }
          #score-link-print, #score-link-print * { visibility: visible; }
          #score-link-print { position: fixed; top: 2cm; left: 0; right: 0; text-align: center; }
        }`}
      </style>
      <Stack align="center">
        <Stack id="score-link-print" align="center" gap="xs">
          <Title order={3}>{name}</Title>
          <div style={{ background: 'white', padding: '1rem' }}>
            <QRCode value={url} size={240} />
          </div>
          <Text size="sm" ta="center" style={{ wordBreak: 'break-all' }}>
            {url}
          </Text>
        </Stack>
        <Alert color="orange" w="100%">
          {t('score_link_shown_once_alert')}
        </Alert>
        <Group grow w="100%">
          <CopyButton value={url}>
            {({ copied, copy }) => (
              <Button
                variant="light"
                color={copied ? 'green' : 'indigo'}
                leftSection={copied ? <IconCheck size={18} /> : <IconCopy size={18} />}
                onClick={copy}
              >
                {copied ? t('copied_label') : t('copy_link_button')}
              </Button>
            )}
          </CopyButton>
          <Button
            variant="default"
            leftSection={<IconPrinter size={18} />}
            onClick={() => window.print()}
          >
            {t('print_button')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

export default function ScoreLinksPanel({
  tournamentId,
  courts,
}: {
  tournamentId: number;
  courts: Court[];
}) {
  const { t } = useTranslation();
  const swrLinks = getScoreLinks(tournamentId);
  const [courtId, setCourtId] = useState<string>('all');
  const [name, setName] = useState('');
  const [hours, setHours] = useState('48');
  const [created, setCreated] = useState<{ token: string; name: string } | null>(null);
  const [loading, setLoading] = useState(false);

  const courtName = (id: number | null) =>
    id == null ? t('score_link_all_courts') : (courts.find((c) => c.id === id)?.name ?? '?');
  const defaultName = courtId === 'all' ? t('score_link_secretariat') : courtName(+courtId);
  const links = swrLinks.data?.data ?? [];

  return (
    <Stack>
      <Text size="sm" c="dimmed">
        {t('score_links_description')}
      </Text>
      <Group align="end">
        <Select
          label={t('score_link_court_label')}
          data={[
            { value: 'all', label: t('score_link_all_courts') },
            ...courts.map((court) => ({ value: `${court.id}`, label: court.name })),
          ]}
          value={courtId}
          onChange={(value) => setCourtId(value ?? 'all')}
          allowDeselect={false}
          w="12rem"
        />
        <TextInput
          label={t('name_input_label')}
          placeholder={defaultName}
          value={name}
          onChange={(event) => setName(event.currentTarget.value)}
          w="12rem"
        />
        <Select
          label={t('score_link_valid_label')}
          data={VALIDITY_HOURS.map((h) => ({
            value: `${h}`,
            label: t('score_link_valid_hours', { count: h }),
          }))}
          value={hours}
          onChange={(value) => setHours(value ?? '48')}
          allowDeselect={false}
          w="10rem"
        />
        <Button
          leftSection={<IconQrcode size={18} />}
          loading={loading}
          onClick={async () => {
            setLoading(true);
            const linkName = name.trim() === '' ? defaultName : name.trim();
            const response = await createScoreLink(tournamentId, {
              name: linkName,
              court_id: courtId === 'all' ? null : +courtId,
              valid_hours: +hours,
            });
            setLoading(false);
            if (requestSucceeded(response) && 'data' in response) {
              setCreated({ token: response.data.data.token, name: linkName });
              setName('');
              await swrLinks.mutate();
            }
          }}
        >
          {t('score_link_create_button')}
        </Button>
      </Group>

      {links.length > 0 ? (
        <Table.ScrollContainer minWidth={500}>
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('name_input_label')}</Table.Th>
                <Table.Th>{t('score_link_court_label')}</Table.Th>
                <Table.Th>{t('score_link_expires_header')}</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {links.map((link) => {
                const status = linkStatus(link);
                return (
                  <Table.Tr key={link.id}>
                    <Table.Td>
                      <Group gap="xs">
                        <IconLink size={16} />
                        {link.name}
                      </Group>
                    </Table.Td>
                    <Table.Td>{courtName(link.court_id)}</Table.Td>
                    <Table.Td>
                      {status === 'active' ? (
                        <DayAndTime datetime={link.expires_at} />
                      ) : (
                        <Badge color="gray">{t(`score_link_status_${status}`)}</Badge>
                      )}
                    </Table.Td>
                    <Table.Td>
                      {status === 'active' ? (
                        <Tooltip label={t('score_link_revoke_button')}>
                          <ActionIcon
                            variant="subtle"
                            color="red"
                            aria-label={t('score_link_revoke_button')}
                            onClick={async () => {
                              await revokeScoreLink(tournamentId, link.id);
                              await swrLinks.mutate();
                            }}
                          >
                            <IconTrash size={18} />
                          </ActionIcon>
                        </Tooltip>
                      ) : null}
                    </Table.Td>
                  </Table.Tr>
                );
              })}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      ) : null}

      <NewLinkModal
        token={created?.token ?? null}
        name={created?.name ?? ''}
        onClose={() => setCreated(null)}
      />
    </Stack>
  );
}
