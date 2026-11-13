import {
  Badge,
  Button,
  Card,
  Group,
  Progress,
  Stack,
  Table,
  Text,
  ThemeIcon,
  Title,
} from '@mantine/core';
import {
  IconAdjustments,
  IconAlertTriangle,
  IconArrowRight,
  IconCheck,
  IconExternalLink,
} from '@tabler/icons-react';
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { PageTitle } from '@components/help/help_button';
import FitGroupsModal from '@components/modals/fit_groups_modal';
import {
  firstGroupStageOfClass,
  freeSlots,
  teamIdsInStage,
  teamsToPlace,
} from '@components/utils/group_stage';
import PreloadLink from '@components/utils/link';
import { capitalize, getTournamentIdFromRouter } from '@components/utils/util';
import { Category, StageWithStageItems } from '@openapi';
import TournamentLayout from '@pages/tournaments/_tournament_layout';
import {
  getAllTeams,
  getCategories,
  getCourts,
  getStages,
  getTournamentById,
} from '@services/adapter';

type StepState = 'done' | 'warning' | 'todo';

/** A link button; the filled one is where to go next. */
function StepButton({ href, label, primary }: { href: string; label: string; primary: boolean }) {
  return (
    <Button
      component={PreloadLink}
      href={href}
      size="sm"
      variant={primary ? 'filled' : 'default'}
      color="indigo"
      rightSection={primary ? <IconArrowRight size={16} /> : undefined}
    >
      {label}
    </Button>
  );
}

function Step({
  number,
  title,
  status,
  state,
  next,
  children,
  actions,
}: {
  number: number;
  title: string;
  status: string;
  state: StepState;
  next: boolean;
  children?: React.ReactNode;
  actions: React.ReactNode;
}) {
  const { t } = useTranslation();
  const icon =
    state === 'done' ? (
      <ThemeIcon color="green" radius="xl" size="lg">
        <IconCheck size={20} />
      </ThemeIcon>
    ) : state === 'warning' ? (
      <ThemeIcon color="orange" radius="xl" size="lg">
        <IconAlertTriangle size={20} />
      </ThemeIcon>
    ) : (
      <ThemeIcon color={next ? 'indigo' : 'gray'} variant="light" radius="xl" size="lg">
        <Text fw={700}>{number}</Text>
      </ThemeIcon>
    );
  return (
    <Card
      withBorder
      padding="md"
      radius="md"
      style={next ? { borderColor: 'var(--mantine-color-indigo-5)', borderWidth: 2 } : undefined}
    >
      <Group align="flex-start" wrap="nowrap">
        {icon}
        <Stack gap="xs" style={{ flex: 1, minWidth: 0 }}>
          <Group gap="xs">
            <Title order={4}>{title}</Title>
            {next ? (
              <Badge color="indigo" variant="light">
                {t('overview_next_badge')}
              </Badge>
            ) : null}
          </Group>
          <Text size="sm" c="dimmed">
            {status}
          </Text>
          {children}
          <Group gap="xs">{actions}</Group>
        </Stack>
      </Group>
    </Card>
  );
}

interface ClassStatus {
  category: Category;
  stage: StageWithStageItems | null;
  teams: number;
  places: number;
  drawn: number;
}

function placesBadge(item: ClassStatus) {
  if (item.stage == null) return 'gray';
  if (item.teams === item.places) return 'green';
  return item.teams > item.places ? 'red' : 'orange';
}

export default function OverviewPage() {
  const { t } = useTranslation();
  const { tournamentData } = getTournamentIdFromRouter();
  const id = tournamentData.id;
  const prefix = `/tournaments/${id}`;
  const tournament = getTournamentById(id).data?.data;
  const swrCategories = getCategories(id);
  const swrStages = getStages(id);
  const swrTeams = getAllTeams(id);
  const swrCourts = getCourts(id);
  const [fitStage, setFitStage] = useState<ClassStatus | null>(null);

  const categories = swrCategories.data?.data ?? [];
  const stages = swrStages.data?.data ?? [];
  const teams = swrTeams.data ?? [];
  const courts = swrCourts.data?.data ?? [];
  const loading =
    tournament == null ||
    swrCategories.data == null ||
    swrStages.data == null ||
    swrTeams.data == null ||
    swrCourts.data == null;

  const classes: ClassStatus[] = [...categories]
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((category) => {
      const stage = firstGroupStageOfClass(stages, category.id);
      const drawn = stage != null ? teamIdsInStage(stage).size : 0;
      return {
        category,
        stage,
        teams: teamsToPlace(teams, category.id).length,
        places: stage != null ? drawn + freeSlots(stage) : 0,
        drawn,
      };
    });
  const teamsWithoutClass =
    categories.length > 0 ? teams.filter((team) => team.category_id == null).length : 0;
  const matches = stages.flatMap((stage) =>
    stage.stage_items.flatMap((item) => item.rounds.flatMap((round) => round.matches)),
  );
  const plannedMatches = matches.filter((match) => match.start_time != null).length;

  // 1. Classes and their groups
  const classesWithoutGroups = classes.filter((item) => item.stage == null);
  const structureState: StepState =
    stages.length < 1 ? 'todo' : classesWithoutGroups.length > 0 ? 'warning' : 'done';
  // 2. Pitches
  const courtsState: StepState = courts.length > 0 ? 'done' : 'todo';
  // 3. Teams: every class has as many teams as places
  const withGroups = classes.filter((item) => item.stage != null);
  const teamCount = withGroups.reduce((sum, item) => sum + item.teams, 0);
  const teamsState: StepState =
    teamCount < 1
      ? 'todo'
      : withGroups.some((item) => item.teams !== item.places) || teamsWithoutClass > 0
        ? 'warning'
        : 'done';
  // 4. Draw: every team is in a group
  const drawnCount = withGroups.reduce((sum, item) => sum + item.drawn, 0);
  const drawState: StepState =
    teamCount < 1 || drawnCount < 1 ? 'todo' : drawnCount < teamCount ? 'warning' : 'done';
  // 5. Schedule: every match has a time and a pitch
  const scheduleState: StepState =
    matches.length < 1 || plannedMatches < 1
      ? 'todo'
      : plannedMatches < matches.length
        ? 'warning'
        : 'done';
  // 6. Public cup page
  const publicState: StepState = tournament?.dashboard_public ? 'done' : 'todo';

  const states = [structureState, courtsState, teamsState, drawState, scheduleState, publicState];
  const doneCount = states.filter((state) => state === 'done').length;
  const nextIndex = states.findIndex((state) => state !== 'done');
  const isNext = (index: number) => !loading && nextIndex === index;

  return (
    <TournamentLayout tournament_id={id}>
      <Stack maw="60rem">
        <PageTitle help="overview">{t('overview_title')}</PageTitle>
        <Text c="dimmed">{t('overview_description')}</Text>
        <Group gap="sm" wrap="nowrap">
          <Progress
            value={(doneCount / states.length) * 100}
            color={doneCount === states.length ? 'green' : 'indigo'}
            size="lg"
            radius="xl"
            style={{ flex: 1 }}
            aria-label={t('overview_progress', { done: doneCount, total: states.length })}
          />
          <Text size="sm" fw={600} style={{ whiteSpace: 'nowrap' }}>
            {t('overview_progress', { done: doneCount, total: states.length })}
          </Text>
        </Group>

        <Step
          number={1}
          title={t('overview_structure_title')}
          state={structureState}
          next={isNext(0)}
          status={
            stages.length < 1
              ? t('overview_structure_empty')
              : classesWithoutGroups.length > 0
                ? t('overview_structure_missing', {
                    names: classesWithoutGroups.map((item) => item.category.name).join(', '),
                  })
                : t('overview_structure_done', { count: categories.length })
          }
          actions={
            stages.length < 1 && categories.length < 1 ? (
              <>
                <StepButton href={`${prefix}/setup`} label={t('setup_start_button')} primary />
                <StepButton href="/capacity" label={t('capacity_title')} primary={false} />
              </>
            ) : (
              <>
                <StepButton
                  href={`${prefix}/stages`}
                  label={t('stage_title')}
                  primary={isNext(0)}
                />
                <StepButton
                  href={`${prefix}/categories`}
                  label={capitalize(t('categories_title'))}
                  primary={false}
                />
              </>
            )
          }
        />

        <Step
          number={2}
          title={t('overview_courts_title')}
          state={courtsState}
          next={isNext(1)}
          status={
            courts.length > 0
              ? t('overview_courts_done', { count: courts.length })
              : t('overview_courts_empty')
          }
          actions={
            <StepButton
              href={`${prefix}/schedule`}
              label={t('planning_title')}
              primary={isNext(1)}
            />
          }
        />

        <Step
          number={3}
          title={t('overview_teams_title')}
          state={teamsState}
          next={isNext(2)}
          status={
            teamCount < 1
              ? t('overview_teams_empty')
              : teamsState === 'done'
                ? t('overview_teams_done', { count: teamCount })
                : t('overview_teams_mismatch')
          }
          actions={
            <>
              <StepButton
                href={`${prefix}/teams`}
                label={capitalize(t('teams_title'))}
                primary={isNext(2)}
              />
              <StepButton
                href={`${prefix}/registrations`}
                label={t('registrations_title')}
                primary={false}
              />
              <StepButton
                href={`${prefix}/clubs`}
                label={t('participating_clubs_title')}
                primary={false}
              />
            </>
          }
        >
          {withGroups.length > 0 ? (
            <Table.ScrollContainer minWidth={420}>
              <Table verticalSpacing={4}>
                <Table.Tbody>
                  {withGroups.map((item) => (
                    <Table.Tr key={item.category.id}>
                      <Table.Td fw={600}>{item.category.name}</Table.Td>
                      <Table.Td>
                        <Badge color={placesBadge(item)} variant="light">
                          {t('overview_teams_places', { teams: item.teams, places: item.places })}
                        </Badge>
                      </Table.Td>
                      <Table.Td>
                        {item.teams !== item.places && item.drawn === 0 && item.teams >= 2 ? (
                          <Button
                            size="xs"
                            variant="light"
                            color="indigo"
                            leftSection={<IconAdjustments size={16} />}
                            onClick={() => setFitStage(item)}
                          >
                            {t('fit_groups_open_button')}
                          </Button>
                        ) : null}
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
          ) : null}
          {teamsWithoutClass > 0 ? (
            <Text size="sm" c="orange">
              {t('overview_teams_without_class', { count: teamsWithoutClass })}
            </Text>
          ) : null}
        </Step>

        <Step
          number={4}
          title={t('draw_title')}
          state={drawState}
          next={isNext(3)}
          status={
            teamCount < 1
              ? t('overview_draw_no_teams')
              : t('overview_draw_status', { drawn: drawnCount, total: teamCount })
          }
          actions={
            <StepButton href={`${prefix}/draw`} label={t('draw_title')} primary={isNext(3)} />
          }
        />

        <Step
          number={5}
          title={t('overview_schedule_title')}
          state={scheduleState}
          next={isNext(4)}
          status={
            matches.length < 1
              ? t('overview_schedule_no_matches')
              : t('overview_schedule_status', { planned: plannedMatches, total: matches.length })
          }
          actions={
            <>
              <StepButton
                href={`${prefix}/schedule`}
                label={t('planning_title')}
                primary={isNext(4)}
              />
              {plannedMatches > 0 ? (
                <StepButton
                  href={`${prefix}/officials`}
                  label={t('officials_title')}
                  primary={false}
                />
              ) : null}
            </>
          }
        />

        <Step
          number={6}
          title={t('overview_public_title')}
          state={publicState}
          next={isNext(5)}
          status={
            tournament?.dashboard_public ? t('overview_public_done') : t('overview_public_empty')
          }
          actions={
            <>
              <StepButton
                href={`${prefix}/settings`}
                label={t('tournament_setting_title')}
                primary={isNext(5)}
              />
              {tournament?.dashboard_public && tournament.dashboard_endpoint ? (
                <Button
                  component="a"
                  href={`/tournaments/${tournament.dashboard_endpoint}/dashboard`}
                  target="_blank"
                  size="sm"
                  variant="default"
                  rightSection={<IconExternalLink size={16} />}
                >
                  {t('overview_public_open')}
                </Button>
              ) : null}
            </>
          }
        />
      </Stack>
      {fitStage != null && fitStage.stage != null ? (
        <FitGroupsModal
          tournamentId={id}
          stage={fitStage.stage}
          className={fitStage.category.name}
          onClose={() => setFitStage(null)}
          onFitted={() => swrStages.mutate()}
        />
      ) : null}
    </TournamentLayout>
  );
}
