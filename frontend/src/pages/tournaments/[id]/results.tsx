import {
  Alert,
  Badge,
  Card,
  Center,
  Flex,
  Grid,
  Group,
  Stack,
  Text,
  Title,
  UnstyledButton,
} from '@mantine/core';
import { AiOutlineHourglass } from '@react-icons/all-files/ai/AiOutlineHourglass';
import { IconAlertCircle } from '@tabler/icons-react';
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

import MatchModal from '@components/modals/match_modal';
import { NoContent } from '@components/no_content/empty_table_info';
import { Time, compareDateTime, spansMultipleDays } from '@components/utils/datetime';
import {
  formatMatchInput1,
  formatMatchInput2,
  formatResultNote,
  getMatchOutcome,
  isLiveScore,
} from '@components/utils/match';
import { getScheduleHeaders } from '@components/utils/schedule_headers';
import { Translator } from '@components/utils/types';
import { getTournamentIdFromRouter, responseIsValid } from '@components/utils/util';
import { MatchWithDetails } from '@openapi';
import TournamentLayout from '@pages/tournaments/_tournament_layout';
import { getCourts, getStages } from '@services/adapter';
import { getMatchLookup, getStageItemLookup, stringToColour } from '@services/lookups';

function ScheduleRow({
  data,
  openMatchModal,
  stageItemsLookup,
  matchesLookup,
}: {
  data: any;
  openMatchModal: any;
  stageItemsLookup: any;
  matchesLookup: any;
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
    <UnstyledButton style={{ width: '100%', maxWidth: '48rem' }}>
      <Card
        shadow="sm"
        radius="md"
        withBorder
        mt="md"
        pt="0rem"
        onClick={() => {
          openMatchModal(data.match);
        }}
      >
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
                  {isLiveScore(data.match) ? (
                    <Badge color="red" variant="filled" size="sm" ml="xs">
                      {t('live_badge')}
                    </Badge>
                  ) : null}
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
              <div
                style={{
                  backgroundColor: team1_color,
                  borderRadius: '0.5rem',
                  paddingLeft: '1rem',
                  paddingRight: '1rem',
                  color: 'white',
                  fontWeight: 800,
                }}
              >
                {data.match.stage_item_input1_score}
              </div>
            </Grid.Col>
          </Grid>
          <Grid mb="0rem">
            <Grid.Col span="auto" pb="0rem">
              <Text fw={500}>
                {formatMatchInput2(t, stageItemsLookup, matchesLookup, data.match)}
              </Text>
            </Grid.Col>
            <Grid.Col span="content" pb="0rem">
              <div
                style={{
                  backgroundColor: team2_color,
                  borderRadius: '0.5rem',
                  paddingLeft: '1rem',
                  paddingRight: '1rem',
                  color: 'white',
                  fontWeight: 800,
                }}
              >
                {data.match.stage_item_input2_score}
              </div>
            </Grid.Col>
          </Grid>
          {resultNote != null ? (
            <Text size="sm" c="dimmed" ta="right" mt="-0.5rem">
              {resultNote}
            </Text>
          ) : null}
        </Stack>
      </Card>
    </UnstyledButton>
  );
}

function Schedule({
  t,
  stageItemsLookup,
  openMatchModal,
  matchesLookup,
}: {
  t: Translator;
  stageItemsLookup: any;
  openMatchModal: CallableFunction;
  matchesLookup: any;
}) {
  const matches: any[] = Object.values(matchesLookup);
  const sortedMatches = matches
    .filter((m1: any) => m1.match.start_time != null)
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
        openMatchModal={openMatchModal}
        stageItemsLookup={stageItemsLookup}
        matchesLookup={matchesLookup}
      />,
    );
  }

  if (rows.length < 1) {
    return (
      <NoContent
        title={t('no_matches_title')}
        description={t('no_matches_description')}
        icon={<AiOutlineHourglass />}
      />
    );
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
    <Group wrap="nowrap" align="top">
      <div style={{ width: '100%', maxWidth: '48rem' }}>
        {rows}
        {noItemsAlert}
      </div>
    </Group>
  );
}

export default function ResultsPage() {
  const [modalOpened, modalSetOpened] = useState(false);
  const [match, setMatch] = useState<MatchWithDetails | null>(null);

  const { t } = useTranslation();
  const { tournamentData } = getTournamentIdFromRouter();
  const swrStagesResponse = getStages(tournamentData.id);
  const swrCourtsResponse = getCourts(tournamentData.id);

  const stageItemsLookup = responseIsValid(swrStagesResponse)
    ? getStageItemLookup(swrStagesResponse)
    : [];
  const matchesLookup = responseIsValid(swrStagesResponse) ? getMatchLookup(swrStagesResponse) : [];

  if (!responseIsValid(swrStagesResponse)) return null;
  if (!responseIsValid(swrCourtsResponse)) return null;

  function openMatchModal(matchToOpen: MatchWithDetails) {
    setMatch(matchToOpen);
    modalSetOpened(true);
  }

  function modalSetOpenedAndUpdateMatch(opened: boolean) {
    if (!opened) {
      setMatch(null);
    }
    modalSetOpened(opened);
  }

  return (
    <TournamentLayout tournament_id={tournamentData.id}>
      <MatchModal
        swrStagesResponse={swrStagesResponse}
        swrUpcomingMatchesResponse={null}
        tournamentData={tournamentData}
        match={match}
        opened={modalOpened}
        setOpened={modalSetOpenedAndUpdateMatch}
        round={null}
      />
      <Title>{t('results_title')}</Title>
      <Center mt="1rem">
        <Schedule
          t={t}
          matchesLookup={matchesLookup}
          stageItemsLookup={stageItemsLookup}
          openMatchModal={openMatchModal}
        />
      </Center>
    </TournamentLayout>
  );
}
