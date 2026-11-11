import {
  Alert,
  Badge,
  Button,
  Checkbox,
  Group,
  List,
  Modal,
  ScrollArea,
  Stack,
  Stepper,
  Switch,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { IconInfoCircle } from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import NewTeamsEditor, {
  EMPTY_NEW_TEAMS,
  NewTeamsState,
  looksLikeClubTeam,
  newTeamError,
  newTeamsOf,
} from '@components/participating_clubs/new_teams_editor';
import { Category, FullTeamWithPlayers, ParticipatingClubWithTeams } from '@openapi';
import { requestSucceeded } from '@services/adapter';
import { createParticipatingClub } from '@services/participating_clubs';

export function CategoryBadge({
  categoryId,
  categories,
}: {
  categoryId: number | null;
  categories: Category[];
}) {
  const { t } = useTranslation();
  const category = categories.find((c) => c.id === categoryId);
  return (
    <Badge variant="light" color={category != null ? 'blue' : 'gray'}>
      {category?.name ?? t('no_category_label')}
    </Badge>
  );
}

export default function ClubWizard({
  tournamentId,
  clubs,
  teams,
  categories,
  onClose,
  onCreated,
}: {
  tournamentId: number;
  clubs: ParticipatingClubWithTeams[];
  teams: FullTeamWithPlayers[];
  categories: Category[];
  onClose: () => void;
  onCreated: () => Promise<void>;
}) {
  const { t } = useTranslation();
  const [step, setStep] = useState(0);
  const [name, setName] = useState('');
  const [newTeamsState, setNewTeamsState] = useState<NewTeamsState>(EMPTY_NEW_TEAMS);
  const [linkedIds, setLinkedIds] = useState<number[]>([]);
  const [noOverlap, setNoOverlap] = useState(false);
  const [search, setSearch] = useState('');
  const [saving, setSaving] = useState(false);

  const trimmed = name.trim();
  const duplicate = clubs.some((club) => club.name.toLowerCase() === trimmed.toLowerCase());
  const nameError = trimmed === '' ? null : duplicate ? t('club_wizard_name_taken') : null;
  const withoutClub = teams
    .filter((team) => team.club_id == null)
    .sort((a, b) => a.name.localeCompare(b.name));
  const shownWithoutClub = withoutClub.filter((team) =>
    team.name.toLowerCase().includes(search.trim().toLowerCase()),
  );
  const teamName = (id: number) => teams.find((team) => team.id === id);
  // Linked teams count as the club's teams in their class (new names continue after them)
  const existingPerClass: Record<number, number> = {};
  for (const id of linkedIds) {
    const categoryId = teamName(id)?.category_id;
    if (categoryId != null) existingPerClass[categoryId] = (existingPerClass[categoryId] ?? 0) + 1;
  }
  const newTeams = newTeamsOf(newTeamsState, trimmed, categories, existingPerClass);
  const invalidNewTeam = newTeams.some((team) => newTeamError(team.name) != null);

  function toTeamsStep() {
    // Suggest the teams that already carry the club's name
    if (linkedIds.length === 0 && newTeams.length === 0 && teams.length > 0) {
      setLinkedIds(
        withoutClub.filter((team) => looksLikeClubTeam(team.name, trimmed)).map((team) => team.id),
      );
    }
    setStep(1);
  }

  async function create() {
    setSaving(true);
    const response = await createParticipatingClub(tournamentId, {
      name: trimmed,
      new_teams: newTeams.map((team) => ({ name: team.name.trim(), category_id: team.categoryId })),
      team_ids: linkedIds,
      no_overlap: noOverlap,
    });
    setSaving(false);
    if (requestSucceeded(response)) {
      await onCreated();
      onClose();
    }
  }

  const teamCount = newTeams.length + linkedIds.length;

  return (
    <Modal opened onClose={onClose} title={t('club_wizard_title')} size="44rem">
      <Stepper active={step} onStepClick={setStep} allowNextStepsSelect={false} size="sm">
        <Stepper.Step label={t('club_wizard_step_name')}>
          <Stack mt="md">
            <TextInput
              data-autofocus
              label={t('club_wizard_name_label')}
              placeholder={t('club_wizard_name_placeholder')}
              value={name}
              onChange={(event) => setName(event.currentTarget.value)}
              error={nameError}
              maxLength={50}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && trimmed !== '' && !duplicate) toTeamsStep();
              }}
            />
            <Group justify="right">
              <Button disabled={trimmed === '' || duplicate} onClick={toTeamsStep}>
                {t('setup_next_button')}
              </Button>
            </Group>
          </Stack>
        </Stepper.Step>

        <Stepper.Step label={t('club_wizard_step_teams')}>
          <Stack mt="md">
            <Title order={5}>{t('club_wizard_new_teams_title')}</Title>
            {categories.length > 0 ? (
              <NewTeamsEditor
                value={newTeamsState}
                onChange={setNewTeamsState}
                clubName={trimmed}
                categories={categories}
                existingPerClass={existingPerClass}
              />
            ) : (
              <Text size="sm" c="dimmed">
                {t('club_wizard_no_classes')}
              </Text>
            )}

            <Title order={5} mt="sm">
              {t('club_wizard_existing_title')}
            </Title>
            {withoutClub.length < 1 ? (
              <Text size="sm" c="dimmed">
                {teams.length < 1
                  ? t('club_wizard_no_teams_in_cup')
                  : t('club_wizard_no_teams_without_club')}
              </Text>
            ) : (
              <>
                {withoutClub.length > 8 ? (
                  <TextInput
                    placeholder={t('search_placeholder')}
                    value={search}
                    onChange={(event) => setSearch(event.currentTarget.value)}
                  />
                ) : null}
                <ScrollArea.Autosize mah="16rem">
                  <Stack gap="xs">
                    {shownWithoutClub.map((team) => (
                      <Group key={team.id} justify="space-between" wrap="nowrap">
                        <Checkbox
                          label={team.name}
                          checked={linkedIds.includes(team.id)}
                          onChange={(event) =>
                            setLinkedIds(
                              event.currentTarget.checked
                                ? [...linkedIds, team.id]
                                : linkedIds.filter((id) => id !== team.id),
                            )
                          }
                        />
                        <CategoryBadge categoryId={team.category_id} categories={categories} />
                      </Group>
                    ))}
                  </Stack>
                </ScrollArea.Autosize>
              </>
            )}
            <Switch
              mt="sm"
              label={t('club_no_overlap_label')}
              description={t('club_no_overlap_description')}
              checked={noOverlap}
              onChange={(event) => setNoOverlap(event.currentTarget.checked)}
            />
            <Group justify="space-between">
              <Button variant="default" onClick={() => setStep(0)}>
                {t('club_wizard_back_button')}
              </Button>
              <Button disabled={invalidNewTeam} onClick={() => setStep(2)}>
                {t('setup_next_button')}
              </Button>
            </Group>
          </Stack>
        </Stepper.Step>

        <Stepper.Step label={t('setup_review_step')}>
          <Stack mt="md">
            <Title order={3}>{trimmed}</Title>
            {teamCount < 1 ? (
              <Alert color="gray" icon={<IconInfoCircle />}>
                {t('club_wizard_no_teams_note')}
              </Alert>
            ) : (
              <List spacing={4}>
                {linkedIds.map((id) => (
                  <List.Item key={id}>
                    <Group gap="xs">
                      <Text>{teamName(id)?.name}</Text>
                      <CategoryBadge
                        categoryId={teamName(id)?.category_id ?? null}
                        categories={categories}
                      />
                    </Group>
                  </List.Item>
                ))}
                {newTeams.map((team, index) => (
                  <List.Item key={`new-${index}`}>
                    <Group gap="xs">
                      <Text>{team.name.trim()}</Text>
                      <CategoryBadge categoryId={team.categoryId} categories={categories} />
                      <Badge color="green" variant="outline" size="sm">
                        {t('club_wizard_new_badge')}
                      </Badge>
                    </Group>
                  </List.Item>
                ))}
              </List>
            )}
            <Group justify="space-between">
              <Button variant="default" onClick={() => setStep(1)}>
                {t('club_wizard_back_button')}
              </Button>
              <Button color="green" loading={saving} onClick={create}>
                {t('club_wizard_create_button', { count: teamCount })}
              </Button>
            </Group>
          </Stack>
        </Stepper.Step>
      </Stepper>
    </Modal>
  );
}
