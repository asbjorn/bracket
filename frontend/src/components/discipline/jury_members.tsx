import {
  ActionIcon,
  Alert,
  Autocomplete,
  Badge,
  Button,
  Card,
  Group,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
} from '@mantine/core';
import { IconAlertTriangle, IconPencil, IconTrash } from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { JuryMember, JuryRole } from '@openapi';
import { getJuryMembers, getParticipatingClubs, requestSucceeded } from '@services/adapter';
import { createJuryMember, deleteJuryMember, updateJuryMember } from '@services/discipline';

interface Draft {
  id: number | null;
  name: string;
  club_name: string;
  phone: string;
  role: JuryRole;
}

const EMPTY: Draft = { id: null, name: '', club_name: '', phone: '', role: 'MEMBER' };

/** The cup's jury: NFF wants at least three members, at most one from each club. */
export default function JuryMembers({ tournamentId }: { tournamentId: number }) {
  const { t } = useTranslation();
  const swrJury = getJuryMembers(tournamentId);
  const clubs = getParticipatingClubs(tournamentId).data?.data ?? [];
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [saving, setSaving] = useState(false);
  const overview = swrJury.data?.data;
  const members: JuryMember[] = overview?.members ?? [];

  async function save() {
    setSaving(true);
    const body = {
      name: draft.name.trim(),
      club_name: draft.club_name.trim() || null,
      phone: draft.phone.trim() || null,
      role: draft.role,
    };
    const response =
      draft.id == null
        ? await createJuryMember(tournamentId, body)
        : await updateJuryMember(tournamentId, draft.id, body);
    setSaving(false);
    if (requestSucceeded(response)) {
      setDraft(EMPTY);
      await swrJury.mutate();
    }
  }

  return (
    <Card withBorder padding="md">
      <Stack>
        <Text size="sm" c="dimmed">
          {t('jury_members_description')}
        </Text>
        {(overview?.warnings ?? []).map((warning) => (
          <Alert key={warning} color="orange" icon={<IconAlertTriangle size={18} />} p="xs">
            {t(`jury_warning_${warning.toLowerCase()}`)}
          </Alert>
        ))}
        {members.length > 0 ? (
          <Table.ScrollContainer minWidth={500}>
            <Table>
              <Table.Tbody>
                {members.map((member) => (
                  <Table.Tr key={member.id}>
                    <Table.Td>
                      <Text fw={500}>{member.name}</Text>
                    </Table.Td>
                    <Table.Td>{member.club_name ?? '–'}</Table.Td>
                    <Table.Td>
                      {member.phone != null ? (
                        <a href={`tel:${member.phone}`}>{member.phone}</a>
                      ) : (
                        '–'
                      )}
                    </Table.Td>
                    <Table.Td>
                      {member.role === 'CHAIR' ? (
                        <Badge>{t('jury_role_chair')}</Badge>
                      ) : (
                        <Badge variant="light" color="gray">
                          {t('jury_role_member')}
                        </Badge>
                      )}
                    </Table.Td>
                    <Table.Td>
                      <Group gap={4} justify="flex-end" wrap="nowrap">
                        <ActionIcon
                          variant="subtle"
                          aria-label={t('edit_jury_member_label')}
                          onClick={() =>
                            setDraft({
                              id: member.id,
                              name: member.name,
                              club_name: member.club_name ?? '',
                              phone: member.phone ?? '',
                              role: member.role,
                            })
                          }
                        >
                          <IconPencil size={16} />
                        </ActionIcon>
                        <ActionIcon
                          variant="subtle"
                          color="red"
                          aria-label={t('delete_jury_member_label')}
                          onClick={async () => {
                            await deleteJuryMember(tournamentId, member.id);
                            await swrJury.mutate();
                          }}
                        >
                          <IconTrash size={16} />
                        </ActionIcon>
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        ) : null}
        <Group align="end" wrap="wrap">
          <TextInput
            label={t('name_input_label')}
            value={draft.name}
            maxLength={100}
            onChange={(event) => setDraft({ ...draft, name: event.currentTarget.value })}
            w="12rem"
          />
          <Autocomplete
            label={t('club_name_input_label')}
            data={clubs.map((club) => club.name)}
            value={draft.club_name}
            maxLength={100}
            onChange={(value) => setDraft({ ...draft, club_name: value })}
            w="12rem"
          />
          <TextInput
            label={t('registration_phone_label')}
            type="tel"
            value={draft.phone}
            maxLength={30}
            onChange={(event) => setDraft({ ...draft, phone: event.currentTarget.value })}
            w="10rem"
          />
          <Select
            label={t('jury_role_label')}
            data={[
              { value: 'CHAIR', label: t('jury_role_chair') },
              { value: 'MEMBER', label: t('jury_role_member') },
            ]}
            value={draft.role}
            onChange={(value) => setDraft({ ...draft, role: (value ?? 'MEMBER') as JuryRole })}
            allowDeselect={false}
            w="9rem"
          />
          <Button loading={saving} disabled={draft.name.trim() === ''} onClick={save}>
            {draft.id == null ? t('add_jury_member_button') : t('save_button')}
          </Button>
          {draft.id != null ? (
            <Button variant="default" onClick={() => setDraft(EMPTY)}>
              {t('cancel_button')}
            </Button>
          ) : null}
        </Group>
      </Stack>
    </Card>
  );
}
