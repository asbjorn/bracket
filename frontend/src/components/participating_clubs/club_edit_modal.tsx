import {
  Alert,
  Button,
  Group,
  Modal,
  MultiSelect,
  Stack,
  Switch,
  Text,
  TextInput,
} from '@mantine/core';
import { IconTrash } from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import NewTeamsEditor, {
  EMPTY_NEW_TEAMS,
  NewTeamsState,
  newTeamError,
  newTeamsOf,
} from '@components/participating_clubs/new_teams_editor';
import { capitalize } from '@components/utils/util';
import { Category, FullTeamWithPlayers, ParticipatingClubWithTeams } from '@openapi';
import { requestSucceeded } from '@services/adapter';
import { deleteParticipatingClub, updateParticipatingClub } from '@services/participating_clubs';

/** Rename a club, change which teams belong to it, or delete it (its teams stay). */
export default function ClubEditModal({
  tournamentId,
  club,
  teams,
  categories,
  onClose,
  onChanged,
}: {
  tournamentId: number;
  club: ParticipatingClubWithTeams;
  teams: FullTeamWithPlayers[];
  categories: Category[];
  onClose: () => void;
  onChanged: () => Promise<void>;
}) {
  const { t } = useTranslation();
  const [name, setName] = useState(club.name);
  const [teamIds, setTeamIds] = useState(club.teams.map((team) => `${team.id}`));
  const [noOverlap, setNoOverlap] = useState(club.no_overlap);
  const [newTeamsState, setNewTeamsState] = useState<NewTeamsState>(EMPTY_NEW_TEAMS);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [saving, setSaving] = useState(false);

  const categoryName = (id: number | null) => categories.find((c) => c.id === id)?.name;
  // Its own teams, and the teams that don't have a club yet
  const options = teams
    .filter((team) => team.club_id == null || team.club_id === club.id)
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((team) => ({
      value: `${team.id}`,
      label: [team.name, categoryName(team.category_id)].filter(Boolean).join(' · '),
    }));

  // The club's chosen teams count per class, so new names continue after them
  const existingPerClass: Record<number, number> = {};
  for (const id of teamIds) {
    const categoryId = teams.find((team) => `${team.id}` === id)?.category_id;
    if (categoryId != null) existingPerClass[categoryId] = (existingPerClass[categoryId] ?? 0) + 1;
  }
  const newTeams = newTeamsOf(newTeamsState, name.trim(), categories, existingPerClass);
  const invalid = name.trim() === '' || newTeams.some((team) => newTeamError(team.name) != null);

  async function save() {
    setSaving(true);
    const response = await updateParticipatingClub(tournamentId, club.id, {
      name: name.trim(),
      team_ids: teamIds.map(Number),
      new_teams: newTeams.map((team) => ({ name: team.name.trim(), category_id: team.categoryId })),
      no_overlap: noOverlap,
    });
    setSaving(false);
    if (requestSucceeded(response)) {
      await onChanged();
      onClose();
    }
  }

  return (
    <Modal opened onClose={onClose} title={t('club_edit_title')} size="36rem">
      <Stack>
        <TextInput
          label={t('club_wizard_name_label')}
          value={name}
          onChange={(event) => setName(event.currentTarget.value)}
          maxLength={50}
          error={name.trim() === '' ? t('too_short_name_validation') : null}
        />
        <MultiSelect
          label={capitalize(t('teams_title'))}
          description={t('club_edit_teams_description')}
          data={options}
          value={teamIds}
          onChange={setTeamIds}
          searchable
          clearable
          hidePickedOptions
          nothingFoundMessage={t('club_select_nothing_found')}
        />
        {categories.length > 0 ? (
          <Stack gap={4}>
            <Text size="sm" fw={500}>
              {t('club_wizard_new_teams_title')}
            </Text>
            <NewTeamsEditor
              value={newTeamsState}
              onChange={setNewTeamsState}
              clubName={name.trim()}
              categories={categories}
              existingPerClass={existingPerClass}
            />
          </Stack>
        ) : null}
        <Switch
          label={t('club_no_overlap_label')}
          description={t('club_no_overlap_description')}
          checked={noOverlap}
          onChange={(event) => setNoOverlap(event.currentTarget.checked)}
        />
        <Button color="green" loading={saving} disabled={invalid} onClick={save}>
          {t('save_button')}
        </Button>
        {confirmDelete ? (
          <Alert color="red" title={t('club_delete_confirm_title', { name: club.name })}>
            <Stack gap="sm">
              <Text size="sm">{t('club_delete_confirm_description')}</Text>
              <Group>
                <Button
                  color="red"
                  onClick={async () => {
                    const response = await deleteParticipatingClub(tournamentId, club.id);
                    if (requestSucceeded(response)) {
                      await onChanged();
                      onClose();
                    }
                  }}
                >
                  {t('club_delete_confirm_button')}
                </Button>
                <Button variant="default" onClick={() => setConfirmDelete(false)}>
                  {t('cancel_button')}
                </Button>
              </Group>
            </Stack>
          </Alert>
        ) : (
          <Button
            variant="subtle"
            color="red"
            leftSection={<IconTrash size={18} />}
            onClick={() => setConfirmDelete(true)}
          >
            {t('club_delete_button')}
          </Button>
        )}
      </Stack>
    </Modal>
  );
}
