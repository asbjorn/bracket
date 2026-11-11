import {
  Alert,
  Badge,
  Button,
  Card,
  Group,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Title,
  UnstyledButton,
} from '@mantine/core';
import { IconBuildingCommunity, IconInfoCircle, IconPlus, IconSearch } from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import ClubEditModal from '@components/participating_clubs/club_edit_modal';
import ClubWizard from '@components/participating_clubs/club_wizard';
import { getTournamentIdFromRouter } from '@components/utils/util';
import TournamentLayout from '@pages/tournaments/_tournament_layout';
import { getAllTeams, getCategories, getParticipatingClubs } from '@services/adapter';

export default function ParticipatingClubsPage() {
  const { t } = useTranslation();
  const { tournamentData } = getTournamentIdFromRouter();
  const tournamentId = tournamentData.id;
  const swrClubsResponse = getParticipatingClubs(tournamentId);
  const swrTeamsResponse = getAllTeams(tournamentId);
  const categories = getCategories(tournamentId).data?.data ?? [];
  const clubs = swrClubsResponse.data?.data ?? [];
  const teams = swrTeamsResponse.data ?? [];

  const [wizardOpen, setWizardOpen] = useState(false);
  const [editedClubId, setEditedClubId] = useState<number | null>(null);
  const [search, setSearch] = useState('');

  const refresh = async () => {
    await Promise.all([swrClubsResponse.mutate(), swrTeamsResponse.mutate()]);
  };
  const categoryName = (id: number | null) => categories.find((c) => c.id === id)?.name;
  const query = search.trim().toLowerCase();
  const shown = clubs.filter(
    (club) =>
      club.name.toLowerCase().includes(query) ||
      club.teams.some((team) => team.name.toLowerCase().includes(query)),
  );
  const withoutClub = teams.filter((team) => team.club_id == null).length;
  const editedClub = clubs.find((club) => club.id === editedClubId) ?? null;
  const loaded = swrClubsResponse.data != null;

  const addButton = (size: 'md' | 'lg') => (
    <Button size={size} leftSection={<IconPlus size={20} />} onClick={() => setWizardOpen(true)}>
      {t('club_add_button')}
    </Button>
  );

  return (
    <TournamentLayout tournament_id={tournamentId}>
      {wizardOpen ? (
        <ClubWizard
          tournamentId={tournamentId}
          clubs={clubs}
          teams={teams}
          categories={categories}
          onClose={() => setWizardOpen(false)}
          onCreated={refresh}
        />
      ) : null}
      {editedClub != null ? (
        <ClubEditModal
          key={editedClub.id}
          tournamentId={tournamentId}
          club={editedClub}
          teams={teams}
          categories={categories}
          onClose={() => setEditedClubId(null)}
          onChanged={refresh}
        />
      ) : null}

      <Stack>
        <Group justify="space-between">
          <Title>{t('participating_clubs_title')}</Title>
          {clubs.length > 0 ? addButton('md') : null}
        </Group>
        <Text c="dimmed">{t('participating_clubs_description')}</Text>

        {loaded && clubs.length < 1 ? (
          <Stack align="center" py="xl">
            <IconBuildingCommunity size={64} stroke={1.2} color="var(--mantine-color-dimmed)" />
            <Title order={3}>{t('participating_clubs_empty_title')}</Title>
            <Text c="dimmed" ta="center" maw="32rem">
              {t('participating_clubs_empty_description')}
            </Text>
            {addButton('lg')}
          </Stack>
        ) : null}

        {clubs.length > 0 ? (
          <>
            <Group>
              <TextInput
                placeholder={t('search_placeholder')}
                leftSection={<IconSearch size={16} />}
                value={search}
                onChange={(event) => setSearch(event.currentTarget.value)}
                w="20rem"
              />
              <Text size="sm" c="dimmed">
                {t('participating_clubs_count', { count: clubs.length })}
              </Text>
            </Group>
            {withoutClub > 0 ? (
              <Alert color="gray" icon={<IconInfoCircle />}>
                {t('participating_clubs_teams_without_club', { count: withoutClub })}
              </Alert>
            ) : null}
            <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
              {shown.map((club) => (
                <UnstyledButton key={club.id} onClick={() => setEditedClubId(club.id)}>
                  <Card withBorder shadow="xs" padding="md" radius="md" h="100%">
                    <Group justify="space-between" wrap="nowrap" mb="xs">
                      <Text fw={700} size="lg" truncate>
                        {club.name}
                      </Text>
                      <Badge variant="light">
                        {t('participating_clubs_team_count', { count: club.teams.length })}
                      </Badge>
                    </Group>
                    {club.teams.length < 1 ? (
                      <Text size="sm" c="dimmed">
                        {t('participating_clubs_no_teams')}
                      </Text>
                    ) : (
                      <Group gap={6}>
                        {club.teams.map((team) => (
                          <Badge key={team.id} variant="outline" color="gray" tt="none">
                            {team.name}
                            {team.category_id != null ? ` · ${categoryName(team.category_id)}` : ''}
                          </Badge>
                        ))}
                      </Group>
                    )}
                  </Card>
                </UnstyledButton>
              ))}
            </SimpleGrid>
          </>
        ) : null}
      </Stack>
    </TournamentLayout>
  );
}
