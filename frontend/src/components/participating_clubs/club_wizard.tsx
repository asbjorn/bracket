import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Checkbox,
  Group,
  List,
  Modal,
  NumberInput,
  ScrollArea,
  Select,
  Stack,
  Stepper,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { IconInfoCircle, IconPlus, IconTrash } from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Category, FullTeamWithPlayers, ParticipatingClubWithTeams } from '@openapi';
import { requestSucceeded } from '@services/adapter';
import { createParticipatingClub } from '@services/participating_clubs';

const MAX_TEAM_NAME = 30;

interface NewTeam {
  name: string;
  categoryId: number | null;
}

/** "Brann" and "Brann 2" belong to the club Brann; "Brannfjell" doesn't. */
export function looksLikeClubTeam(teamName: string, clubName: string) {
  const team = teamName.trim().toLowerCase();
  const club = clubName.trim().toLowerCase();
  return club !== '' && (team === club || team.startsWith(`${club} `));
}

/**
 * Names for `count` new teams of a club in a class, continuing after the teams it already has
 * there: one team is just "Brann", more are "Brann 1", "Brann 2", ...
 */
export function suggestTeamNames(clubName: string, count: number, alreadyInClass: number) {
  const club = clubName.trim();
  if (alreadyInClass === 0 && count === 1) return [club];
  return Array.from({ length: count }, (_, index) => `${club} ${alreadyInClass + index + 1}`);
}

function CategoryBadge({
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
  const [newTeams, setNewTeams] = useState<NewTeam[]>([]);
  const [linkedIds, setLinkedIds] = useState<number[]>([]);
  // New teams go to the first class unless chosen otherwise
  const [addCategory, setAddCategory] = useState<string | null>(
    categories.length > 0 ? `${categories[0].id}` : null,
  );
  const [addCount, setAddCount] = useState<number | string>(1);
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
  const invalidNewTeam = newTeams.some(
    (team) => team.name.trim() === '' || team.name.trim().length > MAX_TEAM_NAME,
  );

  function toTeamsStep() {
    // Suggest the teams that already carry the club's name
    if (linkedIds.length === 0 && newTeams.length === 0) {
      setLinkedIds(
        withoutClub.filter((team) => looksLikeClubTeam(team.name, trimmed)).map((team) => team.id),
      );
    }
    setStep(1);
  }

  function addNewTeams() {
    const categoryId = addCategory != null ? Number(addCategory) : null;
    const inClass =
      newTeams.filter((team) => team.categoryId === categoryId).length +
      linkedIds.filter((id) => teamName(id)?.category_id === categoryId).length;
    const names = suggestTeamNames(trimmed, Number(addCount) || 1, inClass);
    setNewTeams([...newTeams, ...names.map((teamName_) => ({ name: teamName_, categoryId }))]);
  }

  async function create() {
    setSaving(true);
    const response = await createParticipatingClub(tournamentId, {
      name: trimmed,
      new_teams: newTeams.map((team) => ({ name: team.name.trim(), category_id: team.categoryId })),
      team_ids: linkedIds,
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
            <Group align="end">
              <Select
                label={t('category_select_label')}
                placeholder={t('no_category_label')}
                data={categories.map((c) => ({ value: `${c.id}`, label: c.name }))}
                value={addCategory}
                onChange={setAddCategory}
                clearable
                w="12rem"
              />
              <NumberInput
                label={t('club_wizard_count_label')}
                value={addCount}
                onChange={setAddCount}
                min={1}
                max={20}
                w="8rem"
              />
              <Button variant="light" leftSection={<IconPlus size={18} />} onClick={addNewTeams}>
                {t('club_wizard_add_teams_button')}
              </Button>
            </Group>
            {newTeams.map((team, index) => (
              <Group key={index} wrap="nowrap">
                <TextInput
                  style={{ flex: 1 }}
                  value={team.name}
                  aria-label={t('name_input_label')}
                  error={
                    team.name.trim() === ''
                      ? t('too_short_name_validation')
                      : team.name.trim().length > MAX_TEAM_NAME
                        ? t('club_wizard_name_too_long', { max: MAX_TEAM_NAME })
                        : null
                  }
                  onChange={(event) => {
                    const value = event.currentTarget.value;
                    setNewTeams(
                      newTeams.map((t2, i) => (i === index ? { ...t2, name: value } : t2)),
                    );
                  }}
                />
                <CategoryBadge categoryId={team.categoryId} categories={categories} />
                <ActionIcon
                  variant="subtle"
                  color="red"
                  aria-label={t('delete_team_button')}
                  onClick={() => setNewTeams(newTeams.filter((_, i) => i !== index))}
                >
                  <IconTrash size={18} />
                </ActionIcon>
              </Group>
            ))}

            <Title order={5} mt="sm">
              {t('club_wizard_existing_title')}
            </Title>
            {withoutClub.length < 1 ? (
              <Text size="sm" c="dimmed">
                {t('club_wizard_no_teams_without_club')}
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
