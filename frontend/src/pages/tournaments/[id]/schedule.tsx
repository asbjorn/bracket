import { DragDropContext, Draggable, Droppable } from '@hello-pangea/dnd';
import {
  ActionIcon,
  Alert,
  Badge,
  Box,
  Button,
  Card,
  Grid,
  Group,
  Menu,
  ScrollArea,
  SegmentedControl,
  Stack,
  Text,
  Title,
} from '@mantine/core';
import { useMediaQuery } from '@mantine/hooks';
import { AiFillWarning } from '@react-icons/all-files/ai/AiFillWarning';
import { IconAlertCircle, IconDots, IconTrash, IconWand } from '@tabler/icons-react';
import dayjs from 'dayjs';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { SWRResponse } from 'swr';

import { PageTitle } from '@components/help/help_button';
import CourtModal from '@components/modals/create_court_modal';
import MatchModal from '@components/modals/match_modal';
import MatchPlanPanel from '@components/scheduling/match_plan_panel';
import NoticesAlert from '@components/scheduling/notices_alert';
import { PlanIssues } from '@components/scheduling/plan_issues';
import { NoContent } from '@components/no_content/empty_table_info';
import { courtLabel } from '@components/scheduling/courts_panel';
import { Day, DayAndTime, Time, spansMultipleDays } from '@components/utils/datetime';
import PreloadLink from '@components/utils/link';
import { formatMatchInput1, formatMatchInput2 } from '@components/utils/match';
import { TournamentMinimal } from '@components/utils/tournament';
import { Translator } from '@components/utils/types';
import { getTournamentIdFromRouter, responseIsValid } from '@components/utils/util';
import {
  StageItemClassContext,
  StageItemTitle,
  stageItemClassNames,
} from '@components/utils/category';
import { Court, CourtsResponse, MatchWithDetails } from '@openapi';
import TournamentLayout from '@pages/tournaments/_tournament_layout';
import { getCourts, getStages, getCategories } from '@services/adapter';
import { deleteCourt } from '@services/court';
import { getMatchOfficials, refereeNamesByMatch } from '@services/officials';
import {
  getMatchLookup,
  getMatchLookupByCourt,
  getScheduleData,
  getStageItemLookup,
  stringToColour,
} from '@services/lookups';
import { rescheduleMatch } from '@services/match';

function ScheduleRow({
  index,
  match,
  openMatchModal,
  stageItemsLookup,
  matchesLookup,
  multipleDays,
}: {
  index: number;
  match: MatchWithDetails;
  openMatchModal: any;
  stageItemsLookup: any;
  matchesLookup: any;
  multipleDays: boolean;
}) {
  const { t } = useTranslation();
  const { tournamentData } = getTournamentIdFromRouter();
  // SWR shares one request between all rows
  const referee = refereeNamesByMatch(getMatchOfficials(tournamentData.id).data?.data ?? [])[
    match.id
  ];
  return (
    <Draggable key={match.id} index={index} draggableId={`${match.id}`}>
      {(provided) => (
        <div ref={provided.innerRef} {...provided.draggableProps}>
          <Card
            shadow="sm"
            padding="lg"
            radius="md"
            withBorder
            mt="md"
            onClick={() => {
              openMatchModal(match);
            }}
            {...provided.dragHandleProps}
          >
            <Grid>
              <Grid.Col span="auto">
                <Group gap="xs">
                  {match.stage_item_input1_conflict && <AiFillWarning color="red" />}
                  <Text fw={500}>
                    {formatMatchInput1(t, stageItemsLookup, matchesLookup, match)}
                  </Text>
                </Group>
                <Group gap="xs">
                  {match.stage_item_input2_conflict && <AiFillWarning color="red" />}
                  <Text fw={500}>
                    {formatMatchInput2(t, stageItemsLookup, matchesLookup, match)}
                  </Text>
                </Group>
                {referee != null ? (
                  <Text size="xs" c="dimmed" mt={4}>
                    {t('referee_label')}: {referee}
                  </Text>
                ) : null}
              </Grid.Col>
              <Grid.Col span="content">
                <Stack gap="xs" align="end">
                  <Badge variant="default" size="lg">
                    {match.start_time == null ? null : multipleDays ? (
                      <DayAndTime datetime={match.start_time} />
                    ) : (
                      <Time datetime={match.start_time} />
                    )}
                  </Badge>
                  <Badge
                    color={stringToColour(`${matchesLookup[match.id].stageItem.id}`)}
                    variant="outline"
                  >
                    <StageItemTitle
                      id={matchesLookup[match.id].stageItem.id}
                      name={matchesLookup[match.id].stageItem.name}
                    />
                  </Badge>
                </Stack>
              </Grid.Col>
            </Grid>
          </Card>
        </div>
      )}
    </Draggable>
  );
}

function ScheduleColumn({
  tournamentId,
  court,
  matches,
  openMatchModal,
  stageItemsLookup,
  swrCourtsResponse,
  matchesLookup,
  multipleDays,
}: {
  tournamentId: number;
  court: Court;
  matches: MatchWithDetails[];
  openMatchModal: any;
  stageItemsLookup: any;
  swrCourtsResponse: SWRResponse<CourtsResponse>;
  matchesLookup: any;
  multipleDays: boolean;
}) {
  const { t } = useTranslation();
  const allCourts = swrCourtsResponse.data?.data ?? [];
  const rows = matches.map((match: MatchWithDetails, index: number) => (
    <ScheduleRow
      index={index}
      stageItemsLookup={stageItemsLookup}
      matchesLookup={matchesLookup}
      match={match}
      openMatchModal={openMatchModal}
      multipleDays={multipleDays}
      key={match.id}
    />
  ));

  const noItemsAlert =
    matches.length < 1 ? (
      <Alert
        icon={<IconAlertCircle size={16} />}
        title={t('no_matches_title')}
        color="gray"
        radius="md"
        mt="1rem"
      >
        {t('drop_match_alert_title')}
      </Alert>
    ) : null;

  return (
    <Droppable droppableId={`${court.id}`} direction="vertical">
      {(provided) => (
        <div {...provided.droppableProps} ref={provided.innerRef}>
          <div style={{ width: 'min(25rem, calc(100vw - 2rem))' }}>
            <Group
              justify="space-between"
              wrap="nowrap"
              style={{
                position: 'sticky',
                top: 0,
                zIndex: 2,
                background: 'var(--mantine-color-body)',
                paddingBottom: '0.25rem',
              }}
            >
              <Group>
                <h4 style={{ marginTop: '0', margin: 'auto' }}>
                  {courtLabel(t, court, allCourts)}
                  {court.game_format != null ? ` (${court.game_format})` : ''}
                </h4>
              </Group>
              <Menu withinPortal position="bottom-end" shadow="sm">
                <Menu.Target>
                  <ActionIcon variant="transparent" color="gray">
                    <IconDots size="1.25rem" />
                  </ActionIcon>
                </Menu.Target>

                <Menu.Dropdown>
                  <Menu.Item
                    leftSection={<IconTrash size="1.5rem" />}
                    onClick={async () => {
                      await deleteCourt(tournamentId, court.id);
                      await swrCourtsResponse.mutate();
                    }}
                    color="red"
                  >
                    {t('delete_court_button')}
                  </Menu.Item>
                </Menu.Dropdown>
              </Menu>
            </Group>
            {rows}
            {noItemsAlert}
            {provided.placeholder}
          </div>
        </div>
      )}
    </Droppable>
  );
}

function Schedule({
  t,
  tournament,
  swrCourtsResponse,
  stageItemsLookup,
  matchesLookup,
  schedule,
  openMatchModal,
}: {
  t: Translator;
  tournament: TournamentMinimal;
  swrCourtsResponse: SWRResponse<CourtsResponse>;
  stageItemsLookup: any;
  matchesLookup: any;
  schedule: { court: Court; matches: MatchWithDetails[] }[];
  openMatchModal: CallableFunction;
}) {
  const multipleDays = spansMultipleDays(
    schedule.flatMap((item) =>
      item.matches.flatMap((match) => (match.start_time == null ? [] : [match.start_time])),
    ),
  );
  const columns = schedule.map((item) => (
    <ScheduleColumn
      tournamentId={tournament.id}
      swrCourtsResponse={swrCourtsResponse}
      stageItemsLookup={stageItemsLookup}
      matchesLookup={matchesLookup}
      key={item.court.id}
      court={item.court}
      matches={item.matches}
      openMatchModal={openMatchModal}
      multipleDays={multipleDays}
    />
  ));

  columns.push(
    <div key="add-court" style={{ width: '12rem' }}>
      <CourtModal
        swrCourtsResponse={swrCourtsResponse}
        tournamentId={tournament.id}
        buttonSize="xs"
      />
    </div>,
  );
  if (columns.length < 2) {
    return (
      <Stack align="center">
        <NoContent title={t('no_courts_title')} description={t('no_courts_description')} />
        <CourtModal
          swrCourtsResponse={swrCourtsResponse}
          tournamentId={tournament.id}
          buttonSize="lg"
        />
      </Stack>
    );
  }

  // The board scrolls inside its own box (the page never gets wider than the screen), with
  // the pitch names staying on top while scrolling down
  return (
    <ScrollArea.Autosize mah="calc(100vh - 7rem)" type="auto" offsetScrollbars>
      <Group wrap="nowrap" align="top">
        {columns}
      </Group>
    </ScrollArea.Autosize>
  );
}

/** For phones: all matches by time, per day, with the pitch as a badge. */
function ScheduleList({
  schedule,
  courts,
  stageItemsLookup,
  matchesLookup,
  openMatchModal,
}: {
  schedule: { court: Court; matches: MatchWithDetails[] }[];
  courts: Court[];
  stageItemsLookup: any;
  matchesLookup: any;
  openMatchModal: CallableFunction;
}) {
  const { t } = useTranslation();
  const matches = schedule
    .flatMap((item) => item.matches.map((match) => ({ match, court: item.court })))
    .filter((item) => item.match.start_time != null)
    .sort((a, b) => (a.match.start_time ?? '').localeCompare(b.match.start_time ?? ''));
  if (matches.length < 1) {
    return <NoContent title={t('no_matches_title')} description={t('drop_match_alert_title')} />;
  }
  const days = [
    ...new Set(matches.map((item) => dayjs(item.match.start_time).format('YYYY-MM-DD'))),
  ];
  return (
    <Stack gap="xs">
      {days.map((day) => (
        <Stack key={day} gap="xs">
          <Title order={4} mt="sm">
            <Day datetime={`${day}T12:00:00`} />
          </Title>
          {matches
            .filter((item) => dayjs(item.match.start_time).format('YYYY-MM-DD') === day)
            .map(({ match, court }) => (
              <Card
                key={match.id}
                withBorder
                padding="sm"
                radius="md"
                style={{ cursor: 'pointer' }}
                onClick={() => openMatchModal(match)}
              >
                <Group justify="space-between" wrap="nowrap" align="flex-start">
                  <Stack gap={0} style={{ minWidth: 0 }}>
                    <Text fw={500} truncate>
                      {formatMatchInput1(t, stageItemsLookup, matchesLookup, match)}
                    </Text>
                    <Text fw={500} truncate>
                      {formatMatchInput2(t, stageItemsLookup, matchesLookup, match)}
                    </Text>
                  </Stack>
                  <Stack gap={4} align="end">
                    <Badge variant="default" size="lg">
                      <Time datetime={match.start_time as string} />
                    </Badge>
                    <Badge variant="light" size="sm">
                      {courtLabel(t, court, courts)}
                    </Badge>
                    {match.started_at != null && !match.played ? (
                      <Badge color="green" size="sm">
                        {t('match_started_badge')}
                      </Badge>
                    ) : null}
                  </Stack>
                </Group>
              </Card>
            ))}
        </Stack>
      ))}
    </Stack>
  );
}

export default function SchedulePage() {
  const [modalOpened, modalSetOpened] = useState(false);
  const [match, setMatch] = useState<MatchWithDetails | null>(null);
  // Phones get the list by default; the board (drag and drop) needs a wide screen
  const isPhone = useMediaQuery('(max-width: 48em)');
  const [chosenView, setView] = useState<'board' | 'list' | null>(null);
  const view = chosenView ?? (isPhone ? 'list' : 'board');

  const { t } = useTranslation();
  const { tournamentData } = getTournamentIdFromRouter();
  const swrStagesResponse = getStages(tournamentData.id);
  const categoriesForTitles = getCategories(tournamentData.id).data?.data ?? [];
  const swrCourtsResponse = getCourts(tournamentData.id);

  const stageItemsLookup = responseIsValid(swrStagesResponse)
    ? getStageItemLookup(swrStagesResponse)
    : [];
  const matchesLookup = responseIsValid(swrStagesResponse) ? getMatchLookup(swrStagesResponse) : [];
  const matchesByCourtId = responseIsValid(swrStagesResponse)
    ? getMatchLookupByCourt(swrStagesResponse)
    : [];

  const data =
    responseIsValid(swrCourtsResponse) && responseIsValid(swrStagesResponse)
      ? getScheduleData(swrCourtsResponse, matchesByCourtId)
      : [];

  if (!responseIsValid(swrStagesResponse)) return null;
  if (!responseIsValid(swrCourtsResponse)) return null;

  function openMatchModal(matchToOpen: MatchWithDetails) {
    setMatch(matchToOpen);
    modalSetOpened(true);
  }

  return (
    <StageItemClassContext.Provider
      value={stageItemClassNames(swrStagesResponse.data?.data ?? [], categoriesForTitles)}
    >
      <TournamentLayout tournament_id={tournamentData.id}>
        {match != null ? (
          <MatchModal
            swrStagesResponse={swrStagesResponse}
            swrUpcomingMatchesResponse={null}
            tournamentData={tournamentData}
            match={match}
            opened={modalOpened}
            setOpened={modalSetOpened}
            round={null}
          />
        ) : null}
        <PageTitle help="schedule" mb="md">
          {t('planning_title')}
        </PageTitle>
        <NoticesAlert
          tournamentId={tournamentData.id}
          courts={swrCourtsResponse.data?.data ?? []}
        />
        <MatchPlanPanel
          tournamentId={tournamentData.id}
          swrCourtsResponse={swrCourtsResponse}
          onApplied={async () => {
            await swrStagesResponse.mutate();
          }}
          matchLabel={(matchId) => {
            const found = (matchesLookup as Record<number, any>)[matchId];
            if (found == null) return `#${matchId}`;
            return `${formatMatchInput1(t, stageItemsLookup, matchesLookup, found.match)} – ${formatMatchInput2(t, stageItemsLookup, matchesLookup, found.match)}`;
          }}
        />
        <PlanIssues
          tournamentId={tournamentData.id}
          swrStagesResponse={swrStagesResponse}
          matchesLookup={matchesLookup}
          stageItemsLookup={stageItemsLookup}
        />
        {(swrStagesResponse.data?.data ?? []).length < 1 ? (
          <Alert color="indigo" icon={<IconWand />} title={t('no_matches_title')} mt="md">
            <Stack gap="xs" align="flex-start">
              <Text size="sm">{t('schedule_empty_wizard_hint')}</Text>
              <Button
                component={PreloadLink}
                href={`/tournaments/${tournamentData.id}/setup`}
                leftSection={<IconWand size={18} />}
              >
                {t('setup_start_button')}
              </Button>
            </Stack>
          </Alert>
        ) : null}
        <Group mt="lg" justify="flex-end">
          <SegmentedControl
            value={view}
            onChange={(value) => setView(value as 'board' | 'list')}
            data={[
              { value: 'board', label: t('schedule_view_board') },
              { value: 'list', label: t('schedule_view_list') },
            ]}
          />
        </Group>
        {view === 'list' ? (
          <Box mt="md">
            <ScheduleList
              schedule={data}
              courts={swrCourtsResponse.data?.data ?? []}
              stageItemsLookup={stageItemsLookup}
              matchesLookup={matchesLookup}
              openMatchModal={openMatchModal}
            />
          </Box>
        ) : null}
        <Box mt="1rem" display={view === 'board' ? undefined : 'none'}>
          <DragDropContext
            onDragEnd={async ({ destination, source, draggableId: matchId }) => {
              if (destination == null || source == null) return;
              await rescheduleMatch(tournamentData.id, +matchId, {
                old_court_id: +source.droppableId,
                old_position: source.index,
                new_court_id: +destination.droppableId,
                new_position: destination.index,
              });
              await swrStagesResponse.mutate();
            }}
          >
            <Schedule
              t={t}
              tournament={tournamentData}
              swrCourtsResponse={swrCourtsResponse}
              schedule={data}
              stageItemsLookup={stageItemsLookup}
              matchesLookup={matchesLookup}
              openMatchModal={openMatchModal}
            />
          </DragDropContext>
        </Box>
      </TournamentLayout>
    </StageItemClassContext.Provider>
  );
}
