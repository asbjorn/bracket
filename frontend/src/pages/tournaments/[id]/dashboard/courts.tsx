import {
  Badge,
  Button,
  Card,
  Container,
  Group,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from '@mantine/core';
import { IconArrowLeft, IconList } from '@tabler/icons-react';
import { parseAsInteger, useQueryState } from 'nuqs';
import React from 'react';
import { useTranslation } from 'react-i18next';

import { DashboardFooter } from '@components/dashboard/footer';
import { DoubleHeader, getTournamentHeadTitle } from '@components/dashboard/layout';
import { NoContent } from '@components/no_content/empty_table_info';
import { PrintButton } from '@components/print/print_button';
import { getStageItemIdsWithHiddenResults } from '@components/utils/category';
import { Time } from '@components/utils/datetime';
import {
  formatMatchInput1,
  formatMatchInput2,
  isMatchHappening,
  isMatchInTheFutureOrPresent,
} from '@components/utils/match';
import { TableSkeletonTwoColumns } from '@components/utils/skeletons';
import { setTitle } from '@components/utils/util';
import { MatchWithDetails } from '@openapi';
import { Schedule } from '@pages/tournaments/[id]/dashboard';
import { getCategories, getCourtsLive, getStagesLive } from '@services/adapter';
import { getTournamentResponseByEndpointName } from '@services/dashboard';
import { getMatchLookup, getStageItemLookup } from '@services/lookups';
import { getMatchOfficials, refereeNamesByMatch } from '@services/officials';

function MatchLine({
  label,
  match,
  stageItemsLookup,
  matchesLookup,
  color,
}: {
  label: string;
  match: MatchWithDetails | undefined;
  stageItemsLookup: any;
  matchesLookup: any;
  color: string;
}) {
  const { t } = useTranslation();
  return (
    <Stack gap={2}>
      <Group gap="xs">
        <Badge color={color} variant="light" size="sm">
          {label}
        </Badge>
        {match?.start_time != null ? (
          <Text size="sm" fw={700}>
            <Time datetime={match.start_time} />
          </Text>
        ) : null}
      </Group>
      {match != null ? (
        <Text size="lg" fw={500}>
          {formatMatchInput1(t, stageItemsLookup, matchesLookup, match)} –{' '}
          {formatMatchInput2(t, stageItemsLookup, matchesLookup, match)}
        </Text>
      ) : (
        <Text c="dimmed">{t('no_more_matches_on_court')}</Text>
      )}
    </Stack>
  );
}

export default function DashboardCourtsPage() {
  const { t } = useTranslation();
  const tournamentDataFull = getTournamentResponseByEndpointName();
  const tournamentValid = !React.isValidElement(tournamentDataFull);
  const swrStagesResponse = getStagesLive(tournamentValid ? tournamentDataFull.id : null);
  const referees = refereeNamesByMatch(
    getMatchOfficials(tournamentValid ? tournamentDataFull.id : null).data?.data ?? [],
  );
  const swrCourtsResponse = getCourtsLive(tournamentValid ? tournamentDataFull.id : null);
  const categories = getCategories(tournamentValid ? tournamentDataFull.id : null).data?.data ?? [];
  const [courtId, setCourtId] = useQueryState('court', parseAsInteger);

  if (!tournamentValid) return tournamentDataFull;
  setTitle(getTournamentHeadTitle(tournamentDataFull));
  if (swrStagesResponse.data == null || swrCourtsResponse.data == null) {
    return <TableSkeletonTwoColumns />;
  }

  const courts = swrCourtsResponse.data.data;
  const matchesLookup = getMatchLookup(swrStagesResponse);
  const stageItemsLookup = getStageItemLookup(swrStagesResponse);
  const matches: MatchWithDetails[] = Object.values(matchesLookup)
    .map((data: any) => data.match)
    .filter((match: MatchWithDetails) => match.start_time != null && match.court_id != null)
    .sort((a: MatchWithDetails, b: MatchWithDetails) =>
      (a.start_time ?? '').localeCompare(b.start_time ?? ''),
    );
  const selectedCourt = courts.find((court) => court.id === courtId);

  if (selectedCourt != null) {
    return (
      <>
        <DoubleHeader tournamentData={tournamentDataFull} />
        <Container size="sm" px="md">
          <Stack>
            <Group justify="space-between" className="no-print">
              <Button
                variant="subtle"
                leftSection={<IconArrowLeft size={18} />}
                onClick={() => setCourtId(null)}
              >
                {t('all_courts_button')}
              </Button>
              <PrintButton />
            </Group>
            <Title>{selectedCourt.name}</Title>
            <Schedule
              t={t}
              referees={referees}
              matchesLookup={matchesLookup}
              stageItemsLookup={stageItemsLookup}
              stageItemIdsWithHiddenResults={getStageItemIdsWithHiddenResults(
                swrStagesResponse.data.data,
                categories,
              )}
              includeStageItem={() => true}
              includeMatch={(match) => match.court_id === selectedCourt.id}
            />
          </Stack>
        </Container>
        <DashboardFooter />
      </>
    );
  }

  return (
    <>
      <DoubleHeader tournamentData={tournamentDataFull} />
      <Container size="lg" px="md">
        {courts.length < 1 ? <NoContent title={t('no_courts_title')} description="" /> : null}
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
          {courts.map((court) => {
            const courtMatches = matches.filter((match) => match.court_id === court.id);
            const current = courtMatches.find((match) => isMatchHappening(match));
            const next = courtMatches.find(
              (match) => match !== current && isMatchInTheFutureOrPresent(match) && !match.played,
            );
            return (
              <Card key={court.id} withBorder shadow="sm" radius="md">
                <Stack>
                  <Group justify="space-between">
                    <Title order={3}>{court.name}</Title>
                    <Button
                      variant="subtle"
                      size="xs"
                      leftSection={<IconList size={16} />}
                      onClick={() => setCourtId(court.id)}
                    >
                      {t('court_schedule_button')}
                    </Button>
                  </Group>
                  {current != null ? (
                    <MatchLine
                      label={t('now_badge')}
                      match={current}
                      stageItemsLookup={stageItemsLookup}
                      matchesLookup={matchesLookup}
                      color="teal"
                    />
                  ) : null}
                  <MatchLine
                    label={t('next_match_badge')}
                    match={next}
                    stageItemsLookup={stageItemsLookup}
                    matchesLookup={matchesLookup}
                    color="gray"
                  />
                </Stack>
              </Card>
            );
          })}
        </SimpleGrid>
      </Container>
      <DashboardFooter />
    </>
  );
}
