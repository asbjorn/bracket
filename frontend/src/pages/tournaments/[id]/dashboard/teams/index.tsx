import {
  CloseButton,
  Container,
  Group,
  Stack,
  Text,
  TextInput,
  Title,
  UnstyledButton,
} from '@mantine/core';
import { IconChevronRight, IconSearch, IconStarFilled } from '@tabler/icons-react';
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { DashboardFooter } from '@components/dashboard/footer';
import { useFollowedTeam } from '@components/dashboard/follow_team';
import { DoubleHeader, getTournamentHeadTitle } from '@components/dashboard/layout';
import { getPublicTeams, normalizeForSearch } from '@components/dashboard/public_teams';
import { NoContent } from '@components/no_content/empty_table_info';
import PreloadLink from '@components/utils/link';
import { TableSkeletonTwoColumns } from '@components/utils/skeletons';
import { setTitle } from '@components/utils/util';
import { getCategories, getStagesLive } from '@services/adapter';
import { getTournamentResponseByEndpointName } from '@services/dashboard';

export default function DashboardTeamsPage() {
  const { t } = useTranslation();
  const tournamentDataFull = getTournamentResponseByEndpointName();
  const tournamentValid = !React.isValidElement(tournamentDataFull);
  const swrStagesResponse = getStagesLive(tournamentValid ? tournamentDataFull.id : null);
  const categories = getCategories(tournamentValid ? tournamentDataFull.id : null).data?.data ?? [];
  const [search, setSearch] = useState('');
  const [followedTeamId] = useFollowedTeam(tournamentValid ? tournamentDataFull.id : null);

  if (!tournamentValid) return tournamentDataFull;
  setTitle(getTournamentHeadTitle(tournamentDataFull));
  if (swrStagesResponse.data == null) return <TableSkeletonTwoColumns />;

  const query = normalizeForSearch(search.trim());
  const teams = getPublicTeams(swrStagesResponse.data.data, categories).filter(
    ({ team, category }) =>
      query === '' ||
      normalizeForSearch(team.name).includes(query) ||
      normalizeForSearch(category?.name ?? '').includes(query),
  );
  const classNames = [...new Set(teams.map(({ category }) => category?.name ?? ''))].sort();
  const base = `/tournaments/${tournamentDataFull.dashboard_endpoint}/dashboard/teams`;

  return (
    <>
      <DoubleHeader tournamentData={tournamentDataFull} />
      <Container size="sm" px="md">
        <Stack>
          <TextInput
            size="md"
            autoFocus
            leftSection={<IconSearch size={18} />}
            placeholder={t('team_search_placeholder')}
            value={search}
            onChange={(event) => setSearch(event.currentTarget.value)}
            rightSection={
              search !== '' ? (
                <CloseButton aria-label={t('clear_search_label')} onClick={() => setSearch('')} />
              ) : null
            }
          />
          {teams.length < 1 ? <NoContent title={t('no_teams_found_title')} description="" /> : null}
          {classNames.map((className) => (
            <Stack key={className} gap={0}>
              {className !== '' ? (
                <Title order={4} mt="sm" mb="xs">
                  {className}
                </Title>
              ) : null}
              {teams
                .filter(({ category }) => (category?.name ?? '') === className)
                // The followed team first
                .sort(
                  (a, b) =>
                    Number(b.team.id === followedTeamId) - Number(a.team.id === followedTeamId),
                )
                .map(({ team }) => (
                  <UnstyledButton
                    key={team.id}
                    component={PreloadLink}
                    href={`${base}/${team.id}`}
                    py="sm"
                    px="xs"
                    style={{ borderBottom: '1px solid var(--mantine-color-default-border)' }}
                  >
                    <Group justify="space-between" wrap="nowrap">
                      <Group gap="xs" wrap="nowrap">
                        {team.id === followedTeamId ? (
                          <IconStarFilled
                            size={18}
                            color="var(--mantine-color-yellow-6)"
                            aria-label={t('follow_team_badge')}
                          />
                        ) : null}
                        <Text size="lg" fw={team.id === followedTeamId ? 700 : undefined}>
                          {team.name}
                        </Text>
                      </Group>
                      <IconChevronRight size={20} color="var(--mantine-color-dimmed)" />
                    </Group>
                  </UnstyledButton>
                ))}
            </Stack>
          ))}
        </Stack>
      </Container>
      <DashboardFooter />
    </>
  );
}
