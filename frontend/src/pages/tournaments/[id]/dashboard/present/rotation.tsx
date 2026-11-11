import { Badge, Box, Group, Progress, Stack, Table, Text, Title } from '@mantine/core';
import { parseAsInteger, useQueryState } from 'nuqs';
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { getTournamentHeadTitle } from '@components/dashboard/layout';
import { PublicNoticesBanner } from '@components/dashboard/public_notices';
import {
  StageItemClassContext,
  StageItemTitle,
  getStageItemIdsWithHiddenResults,
  stageItemClassNames,
} from '@components/utils/category';
import { Time } from '@components/utils/datetime';
import { formatMatchInput1, formatMatchInput2 } from '@components/utils/match';
import { TableSkeletonTwoColumns } from '@components/utils/skeletons';
import { setTitle } from '@components/utils/util';
import { MatchWithDetails } from '@openapi';
import CourtsPresentPage from '@pages/tournaments/[id]/dashboard/present/courts';
import StandingsPresentPage from '@pages/tournaments/[id]/dashboard/present/standings';
import { getCategories, getStagesLive } from '@services/adapter';
import { getTournamentResponseByEndpointName } from '@services/dashboard';
import { getMatchLookup, getStageItemLookup } from '@services/lookups';

const DEFAULT_SECONDS = 20;
const UPCOMING_MATCHES = 12;

function UpcomingMatches({ swrStagesResponse }: { swrStagesResponse: any }) {
  const { t } = useTranslation();
  const matchesLookup = getMatchLookup(swrStagesResponse);
  const stageItemsLookup = getStageItemLookup(swrStagesResponse);
  const upcoming = Object.values(matchesLookup)
    .filter((data: any) => !data.match.played && data.match.start_time != null)
    .sort((a: any, b: any) => a.match.start_time.localeCompare(b.match.start_time))
    .slice(0, UPCOMING_MATCHES);

  return (
    <Stack p="xl">
      <Title style={{ fontSize: '3rem' }}>{t('upcoming_matches_title')}</Title>
      <Table fz="1.8rem" verticalSpacing="md">
        <Table.Tbody>
          {upcoming.map((data: any) => {
            const match: MatchWithDetails = data.match;
            return (
              <Table.Tr key={match.id}>
                <Table.Td fw={700}>
                  <Time datetime={match.start_time ?? ''} />
                </Table.Td>
                <Table.Td>{match.court?.name}</Table.Td>
                <Table.Td>
                  {formatMatchInput1(t, stageItemsLookup, matchesLookup, match)} –{' '}
                  {formatMatchInput2(t, stageItemsLookup, matchesLookup, match)}
                </Table.Td>
                <Table.Td>
                  <Badge size="xl" variant="light">
                    <StageItemTitle id={data.stageItem.id} name={data.stageItem.name} />
                  </Badge>
                </Table.Td>
              </Table.Tr>
            );
          })}
        </Table.Tbody>
      </Table>
      {upcoming.length < 1 ? <Text size="xl">{t('no_matches_title')}</Text> : null}
    </Stack>
  );
}

/**
 * For a big screen: shows the courts, the upcoming matches and the tables (only for classes
 * with public results) in turn, every `?seconds=` seconds.
 */
export default function RotationPresentPage() {
  const tournamentDataFull = getTournamentResponseByEndpointName();
  const tournamentValid = !React.isValidElement(tournamentDataFull);
  const swrStagesResponse = getStagesLive(tournamentValid ? tournamentDataFull.id : null);
  const categories = getCategories(tournamentValid ? tournamentDataFull.id : null).data?.data ?? [];
  const [secondsParam] = useQueryState('seconds', parseAsInteger.withDefault(DEFAULT_SECONDS));
  const seconds = Math.max(5, secondsParam);
  const [index, setIndex] = useState(0);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => setElapsed((value) => value + 1), 1000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    if (elapsed >= seconds) {
      setElapsed(0);
      setIndex((value) => value + 1);
    }
  }, [elapsed, seconds]);

  if (!tournamentValid) return tournamentDataFull;
  setTitle(getTournamentHeadTitle(tournamentDataFull));
  if (swrStagesResponse.data == null) return <TableSkeletonTwoColumns />;

  const stages = swrStagesResponse.data.data;
  const hidden = getStageItemIdsWithHiddenResults(stages, categories);
  const hasPublicTables = stages.some((stage) =>
    stage.stage_items.some(
      (item) => !hidden.has(item.id) && (item.type === 'ROUND_ROBIN' || item.type === 'SWISS'),
    ),
  );
  const views = [
    <CourtsPresentPage key="courts" showNotices={false} />,
    <UpcomingMatches key="upcoming" swrStagesResponse={swrStagesResponse} />,
    ...(hasPublicTables ? [<StandingsPresentPage key="standings" showNotices={false} />] : []),
  ];

  return (
    <StageItemClassContext.Provider value={stageItemClassNames(stages, categories)}>
      <Box>
        <Progress
          value={(100 * elapsed) / seconds}
          size="xs"
          radius={0}
          transitionDuration={1000}
        />
        <Group px="xl">
          <Box style={{ flex: 1 }}>
            <PublicNoticesBanner tournamentId={tournamentDataFull.id} size="xl" />
          </Box>
        </Group>
        {views[index % views.length]}
      </Box>
    </StageItemClassContext.Provider>
  );
}
