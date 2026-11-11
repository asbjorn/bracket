import { Alert, Badge, Card, Center, Flex, Grid, Group, Stack, Text } from '@mantine/core';
import { AiOutlineHourglass } from '@react-icons/all-files/ai/AiOutlineHourglass';
import { IconAlertCircle } from '@tabler/icons-react';
import React from 'react';
import { useTranslation } from 'react-i18next';

import { DashboardFooter } from '@components/dashboard/footer';
import { DoubleHeader, getTournamentHeadTitle } from '@components/dashboard/layout';
import { NoContent } from '@components/no_content/empty_table_info';
import {
  CategoryFilterSelect,
  getStageItemCategoryLookup,
  getStageItemIdsWithHiddenResults,
  useCategoryFilter,
} from '@components/utils/category';
import { Time, compareDateTime, spansMultipleDays } from '@components/utils/datetime';
import {
  formatMatchInput1,
  formatMatchInput2,
  formatResultNote,
  getMatchOutcome,
} from '@components/utils/match';
import { getScheduleHeaders } from '@components/utils/schedule_headers';
import { Translator } from '@components/utils/types';
import { responseIsValid, setTitle } from '@components/utils/util';
import { getCategories, getCourtsLive, getStagesLive } from '@services/adapter';
import { getTournamentResponseByEndpointName } from '@services/dashboard';
import { getMatchLookup, getStageItemLookup, stringToColour } from '@services/lookups';

function ScoreBox({ score, color }: { score: number; color: string }) {
  return (
    <div
      style={{
        backgroundColor: color,
        borderRadius: '0.5rem',
        width: '2.5rem',
        color: 'white',
        fontWeight: 800,
      }}
    >
      <Center>{score}</Center>
    </div>
  );
}

function ScheduleRow({
  data,
  stageItemsLookup,
  matchesLookup,
  resultsHidden,
}: {
  data: any;
  stageItemsLookup: any;
  matchesLookup: any;
  // NFF children's football: only show whether the match was played, not the score
  resultsHidden: boolean;
}) {
  const { t } = useTranslation();
  const winColor = '#2a8f37';
  const drawColor = '#656565';
  const loseColor = '#af4034';
  // Penalty shootouts decide the winner of a draw; unplayed matches have no winner yet
  const outcome = getMatchOutcome(data.match);
  const team1_color = outcome === 1 ? winColor : outcome === 2 ? loseColor : drawColor;
  const team2_color = outcome === 2 ? winColor : outcome === 1 ? loseColor : drawColor;
  const resultNote = formatResultNote(t, data.match);

  return (
    <Card shadow="sm" radius="md" withBorder mt="md" pt="0rem">
      <Card.Section withBorder>
        <Grid pt="0.75rem" pb="0.5rem">
          <Grid.Col mb="0rem" span={4}>
            <Text pl="sm" mt="sm" fw={800}>
              {data.match.court.name}
            </Text>
          </Grid.Col>
          <Grid.Col mb="0rem" span={4}>
            <Center>
              <Text mt="sm" fw={800}>
                {data.match.start_time != null ? <Time datetime={data.match.start_time} /> : null}
              </Text>
            </Center>
          </Grid.Col>
          <Grid.Col mb="0rem" span={4}>
            <Flex justify="right">
              <Badge
                color={stringToColour(`${data.stageItem.id}`)}
                variant="outline"
                mr="md"
                mt="0.8rem"
                size="md"
              >
                {data.stageItem.name}
              </Badge>
            </Flex>
          </Grid.Col>
        </Grid>
      </Card.Section>
      <Stack pt="sm">
        <Grid>
          <Grid.Col span="auto" pb="0rem">
            <Text fw={500}>
              {formatMatchInput1(t, stageItemsLookup, matchesLookup, data.match)}
            </Text>
          </Grid.Col>
          <Grid.Col span="content" pb="0rem">
            {resultsHidden ? (
              data.match.played ? (
                <Badge color="gray" variant="light">
                  {t('played_badge')}
                </Badge>
              ) : null
            ) : (
              <ScoreBox score={data.match.stage_item_input1_score} color={team1_color} />
            )}
          </Grid.Col>
        </Grid>
        <Grid mb="0rem">
          <Grid.Col span="auto" pb="0rem">
            <Text fw={500}>
              {formatMatchInput2(t, stageItemsLookup, matchesLookup, data.match)}
            </Text>
          </Grid.Col>
          <Grid.Col span="content" pb="0rem">
            {resultsHidden ? null : (
              <ScoreBox score={data.match.stage_item_input2_score} color={team2_color} />
            )}
          </Grid.Col>
        </Grid>
        {!resultsHidden && resultNote != null ? (
          <Text size="sm" c="dimmed" ta="right" mt="-0.5rem">
            {resultNote}
          </Text>
        ) : null}
      </Stack>
    </Card>
  );
}

export function Schedule({
  t,
  stageItemsLookup,
  matchesLookup,
  stageItemIdsWithHiddenResults,
  includeStageItem,
}: {
  t: Translator;
  stageItemsLookup: any;
  matchesLookup: any;
  stageItemIdsWithHiddenResults: Set<number>;
  includeStageItem: (stageItemId: number) => boolean;
}) {
  const matches: any[] = Object.values(matchesLookup);
  const sortedMatches = matches
    .filter((m1: any) => m1.match.start_time != null)
    .filter((m1: any) => includeStageItem(m1.stageItem.id))
    .sort(
      (m1: any, m2: any) =>
        compareDateTime(m1.match.start_time, m2.match.start_time) ||
        (m1.match.court?.name ?? '').localeCompare(m2.match.court?.name ?? ''),
    );
  const multipleDays = spansMultipleDays(sortedMatches.map((m: any) => m.match.start_time));

  const rows: React.JSX.Element[] = [];

  for (let c = 0; c < sortedMatches.length; c += 1) {
    const data = sortedMatches[c];

    rows.push(
      ...getScheduleHeaders({
        startTime: data.match.start_time,
        previousStartTime: c > 0 ? sortedMatches[c - 1].match.start_time : null,
        multipleDays,
        keySuffix: c,
      }),
    );

    rows.push(
      <ScheduleRow
        key={data.match.id}
        data={data}
        stageItemsLookup={stageItemsLookup}
        matchesLookup={matchesLookup}
        resultsHidden={stageItemIdsWithHiddenResults.has(data.stageItem.id)}
      />,
    );
  }

  if (rows.length < 1) {
    return <NoContent title={t('no_matches_title')} description="" icon={<AiOutlineHourglass />} />;
  }

  const noItemsAlert =
    matchesLookup.length < 1 ? (
      <Alert
        icon={<IconAlertCircle size={16} />}
        title={t('no_matches_title')}
        color="gray"
        radius="md"
      >
        {t('drop_match_alert_title')}
      </Alert>
    ) : null;

  return (
    <Group wrap="nowrap" align="top" style={{ width: '100%' }}>
      <div style={{ width: '100%' }}>
        {rows}
        {noItemsAlert}
      </div>
    </Group>
  );
}
export default function DashboardSchedulePage() {
  const { t } = useTranslation();
  const tournamentDataFull = getTournamentResponseByEndpointName();
  const tournamentValid = !React.isValidElement(tournamentDataFull);

  const swrStagesResponse = getStagesLive(tournamentValid ? tournamentDataFull.id : null);
  const swrCourtsResponse = getCourtsLive(tournamentValid ? tournamentDataFull.id : null);
  const categories = getCategories(tournamentValid ? tournamentDataFull.id : null).data?.data ?? [];
  const { filterValue, setFilterValue, filterCategoryId } = useCategoryFilter(categories);

  if (!tournamentValid) {
    return tournamentDataFull;
  }

  setTitle(getTournamentHeadTitle(tournamentDataFull));

  const stageItemsLookup = responseIsValid(swrStagesResponse)
    ? getStageItemLookup(swrStagesResponse)
    : [];
  const matchesLookup = responseIsValid(swrStagesResponse) ? getMatchLookup(swrStagesResponse) : [];

  // TODO: show loading icon.
  if (!responseIsValid(swrStagesResponse)) return null;
  if (!responseIsValid(swrCourtsResponse)) return null;

  const stages = swrStagesResponse.data?.data ?? [];
  const stageItemCategories = getStageItemCategoryLookup(stages);

  return (
    <>
      <DoubleHeader tournamentData={tournamentDataFull} />
      <Center>
        <Group style={{ maxWidth: '48rem', width: '100%' }} px="1rem">
          <Stack style={{ width: '100%' }}>
            <CategoryFilterSelect
              categories={categories}
              value={filterValue}
              setValue={setFilterValue}
            />
            <Schedule
              t={t}
              matchesLookup={matchesLookup}
              stageItemsLookup={stageItemsLookup}
              stageItemIdsWithHiddenResults={getStageItemIdsWithHiddenResults(stages, categories)}
              includeStageItem={(stageItemId) =>
                filterCategoryId === undefined ||
                stageItemCategories[stageItemId] === filterCategoryId
              }
            />
          </Stack>
        </Group>
      </Center>
      <DashboardFooter />
    </>
  );
}
