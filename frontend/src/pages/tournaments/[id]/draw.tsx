import {
  Alert,
  Badge,
  Button,
  Card,
  Group,
  NumberInput,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core';
import { IconArrowsShuffle, IconInfoCircle, IconMaximize } from '@tabler/icons-react';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { PageTitle } from '@components/help/help_button';
import { getTournamentIdFromRouter } from '@components/utils/util';
import { DrawPlacement, FullTeamWithPlayers, StageWithStageItems } from '@openapi';
import TournamentLayout from '@pages/tournaments/_tournament_layout';
import {
  getAllTeamsOfCategory,
  getCategories,
  getParticipatingClubs,
  getStages,
  requestSucceeded,
} from '@services/adapter';
import { drawTeams } from '@services/draw';
import { setTeamPots } from '@services/team';

const REVEAL_INTERVAL_MS = 1500;
const MAX_POTS = 10;
// More pots than this don't fit as buttons on a phone
const MAX_POT_BUTTONS = 5;

/** The saved pot of a team; no pot means pot 1. */
function savedPot(team: { pot?: number | null }) {
  return team.pot ?? 1;
}
const GROUP_TYPES = new Set(['ROUND_ROBIN', 'SWISS']);

function isGroupStage(stage: StageWithStageItems) {
  return (
    stage.stage_items.length > 0 && stage.stage_items.every((item) => GROUP_TYPES.has(item.type))
  );
}

function teamIdsInStage(stage: StageWithStageItems) {
  return new Set(
    stage.stage_items.flatMap((item) =>
      item.inputs.flatMap((input) =>
        'team' in input && input.team != null ? [input.team.id] : [],
      ),
    ),
  );
}

function freeSlots(stage: StageWithStageItems) {
  return stage.stage_items
    .flatMap((item) => item.inputs)
    .filter(
      (input) =>
        input.team_id == null && input.winner_from_stage_item_id == null && input.best_rank == null,
    ).length;
}

/** The groups with their teams; teams of the current draw only once they are revealed. */
function DrawBoard({
  stage,
  hidden,
  latest,
  showPots,
}: {
  stage: StageWithStageItems;
  hidden: Set<number>;
  latest: number | null;
  showPots: boolean;
}) {
  const { t } = useTranslation();
  const items = [...stage.stage_items].sort((a, b) => a.name.localeCompare(b.name) || a.id - b.id);
  return (
    <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
      {items.map((item) => (
        <Card key={item.id} withBorder shadow="sm" padding="lg">
          <Title order={3} mb="sm">
            {item.name}
          </Title>
          <Stack gap="xs">
            {[...item.inputs]
              .sort((a, b) => a.slot - b.slot)
              .map((input) =>
                'team' in input && input.team != null && !hidden.has(input.team.id) ? (
                  <Group key={input.id} gap="xs" wrap="nowrap" justify="space-between">
                    <Text
                      size="xl"
                      fw={input.team.id === latest ? 700 : 400}
                      c={input.team.id === latest ? 'indigo' : undefined}
                    >
                      {input.team.name}
                    </Text>
                    {showPots ? (
                      <Badge color="gray" variant="light" style={{ flexShrink: 0 }}>
                        {t('draw_pot_badge', { pot: savedPot(input.team) })}
                      </Badge>
                    ) : null}
                  </Group>
                ) : (
                  <Text key={input.id} size="xl" c="dimmed">
                    –
                  </Text>
                ),
              )}
          </Stack>
        </Card>
      ))}
    </SimpleGrid>
  );
}

export default function DrawPage() {
  const { t } = useTranslation();
  const { tournamentData } = getTournamentIdFromRouter();
  const swrStagesResponse = getStages(tournamentData.id);
  const categories = getCategories(tournamentData.id).data?.data ?? [];
  const stages = (swrStagesResponse.data?.data ?? []).filter(isGroupStage);

  const [stageId, setStageId] = useState<string | null>(null);
  // Start with the first class that still has empty places to draw into
  useEffect(() => {
    if (stageId != null || stages.length < 1) return;
    const firstOpen = stages.find((s) => freeSlots(s) > 0) ?? stages[0];
    setStageId(`${firstOpen.id}`);
  }, [stageId, stages.length]);
  const stage = stages.find((s) => `${s.id}` === stageId) ?? null;
  const swrTeams = getAllTeamsOfCategory(tournamentData.id, stage?.category_id ?? null);
  const teams = swrTeams.data ?? [];
  const clubNames = Object.fromEntries(
    (getParticipatingClubs(tournamentData.id).data?.data ?? []).map((club) => [club.id, club.name]),
  );

  // The number of pots: at least the highest saved pot of the teams to draw
  const [potCountChoice, setPotCountChoice] = useState<number | null>(null);
  const [placements, setPlacements] = useState<DrawPlacement[]>([]);
  const [revealed, setRevealed] = useState(0);
  const [loading, setLoading] = useState(false);
  const boardRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (revealed >= placements.length) return undefined;
    const timer = setTimeout(() => setRevealed(revealed + 1), REVEAL_INTERVAL_MS);
    return () => clearTimeout(timer);
  }, [revealed, placements]);

  const placed = stage != null ? teamIdsInStage(stage) : new Set<number>();
  const hidden = new Set(placements.slice(revealed).map((placement) => placement.team_id));
  const toDraw = teams.filter((team) => !placed.has(team.id));
  const free = stage != null ? freeSlots(stage) : 0;
  const groupCount = stage?.stage_items.length ?? 0;
  const highestPot = Math.max(1, ...toDraw.map(savedPot));
  const potCount = Math.min(MAX_POTS, Math.max(potCountChoice ?? 1, highestPot));
  const potNumbers = Array.from({ length: potCount }, (_, index) => index + 1);
  const teamsInPot = (pot: number) => toDraw.filter((team) => savedPot(team) === pot);
  const overfullPots =
    potCount > 1 ? potNumbers.filter((pot) => teamsInPot(pot).length > groupCount) : [];
  const categoryName = (id: number | null) => categories.find((c) => c.id === id)?.name ?? '';
  const groupName = (id: number) => stage?.stage_items.find((item) => item.id === id)?.name ?? '';
  const latestPlacement = revealed > 0 ? (placements[revealed - 1] ?? null) : null;
  const latestTeam =
    latestPlacement != null
      ? stage?.stage_items
          .flatMap((item) => item.inputs)
          .find((input) => input.id === latestPlacement.stage_item_input_id)
      : undefined;
  const showPots =
    potCount > 1 ||
    (stage?.stage_items ?? []).some((item) =>
      item.inputs.some(
        (input) => 'team' in input && input.team != null && savedPot(input.team) > 1,
      ),
    );

  /** Saves pots right away (shown at once, saved in the background). Pot 1 is saved as empty. */
  async function savePots(changes: { team: FullTeamWithPlayers; pot: number }[]) {
    const changed = changes.filter(
      ({ team, pot }) => savedPot(team) !== pot || (pot === 1 && team.pot != null),
    );
    if (changed.length < 1) return;
    const potOfTeam = new Map(changed.map(({ team, pot }) => [team.id, pot === 1 ? null : pot]));
    await swrTeams.mutate(
      teams.map((team) =>
        potOfTeam.has(team.id) ? { ...team, pot: potOfTeam.get(team.id) ?? null } : team,
      ),
      { revalidate: false },
    );
    await setTeamPots(
      tournamentData.id,
      [...potOfTeam].map(([team_id, pot]) => ({ team_id, pot })),
    );
    await swrTeams.mutate();
  }

  async function changePotCount(count: number) {
    setPotCountChoice(count);
    // Teams in pots that no longer exist move to the last pot
    if (count < highestPot) {
      await savePots(
        toDraw.filter((team) => savedPot(team) > count).map((team) => ({ team, pot: count })),
      );
    }
  }

  async function draw() {
    if (stage == null) return;
    setLoading(true);
    const pots = potNumbers
      .map((pot) => teamsInPot(pot).map((team) => team.id))
      .filter((pot) => pot.length > 0);
    const response = await drawTeams(tournamentData.id, stage.id, { pots, seed: null });
    if (requestSucceeded(response) && 'data' in response) {
      setPlacements(response.data.data);
      setRevealed(0);
      await swrStagesResponse.mutate();
    }
    setLoading(false);
  }

  return (
    <TournamentLayout tournament_id={tournamentData.id}>
      <Stack>
        <PageTitle help="draw">{t('draw_title')}</PageTitle>
        <Alert color="gray" icon={<IconInfoCircle />}>
          {t('draw_description')}
        </Alert>
        <Select
          label={t('draw_stage_label')}
          data={stages.map((s) => ({
            value: `${s.id}`,
            label: [categoryName(s.category_id), s.name].filter(Boolean).join(' – '),
          }))}
          value={stageId}
          onChange={(value) => {
            setStageId(value);
            setPotCountChoice(null);
            setPlacements([]);
            setRevealed(0);
          }}
          maw="30rem"
        />

        {stage != null && toDraw.length > 0 ? (
          <Stack>
            <NumberInput
              label={t('draw_pot_count_label')}
              description={t('draw_pot_count_description')}
              value={potCount}
              min={1}
              max={MAX_POTS}
              onChange={(value) =>
                changePotCount(Math.min(MAX_POTS, Math.max(1, Number(value) || 1)))
              }
              w="14rem"
            />
            {potCount > 1 ? (
              <>
                <Text size="sm" c="dimmed">
                  {t('draw_pots_saved_note')}
                </Text>
                <Group gap="xs">
                  {potNumbers.map((pot) => {
                    const count = teamsInPot(pot).length;
                    return (
                      <Badge
                        key={pot}
                        size="lg"
                        variant="light"
                        color={count > groupCount ? 'orange' : count === 0 ? 'gray' : 'indigo'}
                      >
                        {t('draw_pot_summary', { pot, count })}
                      </Badge>
                    );
                  })}
                  <Text size="sm" c="dimmed">
                    {t('draw_group_count', { count: groupCount })}
                  </Text>
                </Group>
                {overfullPots.map((pot) => (
                  <Alert key={pot} color="orange" maw="40rem">
                    {t('draw_pot_too_big_alert', {
                      pot,
                      count: teamsInPot(pot).length,
                      groups: groupCount,
                    })}
                  </Alert>
                ))}
                <Table maw="40rem" striped>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>{t('team_title')}</Table.Th>
                      <Table.Th visibleFrom="xs">{t('club_name_input_label')}</Table.Th>
                      <Table.Th>{t('draw_pot_column')}</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {[...toDraw]
                      .sort((a, b) => savedPot(a) - savedPot(b) || a.name.localeCompare(b.name))
                      .map((team) => (
                        <Table.Tr key={team.id}>
                          <Table.Td>{team.name}</Table.Td>
                          <Table.Td visibleFrom="xs">
                            {team.club_id != null ? clubNames[team.club_id] : '–'}
                          </Table.Td>
                          <Table.Td>
                            {potCount <= MAX_POT_BUTTONS ? (
                              <SegmentedControl
                                size="xs"
                                aria-label={t('draw_pot_of_team', { team: team.name })}
                                data={potNumbers.map((pot) => `${pot}`)}
                                value={`${savedPot(team)}`}
                                onChange={(value) => savePots([{ team, pot: Number(value) }])}
                              />
                            ) : (
                              <Select
                                size="xs"
                                w="6rem"
                                aria-label={t('draw_pot_of_team', { team: team.name })}
                                data={potNumbers.map((pot) => `${pot}`)}
                                value={`${savedPot(team)}`}
                                allowDeselect={false}
                                onChange={(value) =>
                                  value != null && savePots([{ team, pot: Number(value) }])
                                }
                              />
                            )}
                          </Table.Td>
                        </Table.Tr>
                      ))}
                  </Table.Tbody>
                </Table>
              </>
            ) : null}
            <Text size="sm">
              {t('draw_teams_and_places', { teams: toDraw.length, places: free })}
            </Text>
            {toDraw.length > free ? (
              <Alert color="orange">{t('draw_too_many_teams_alert')}</Alert>
            ) : null}
            {toDraw.length < free ? (
              <Alert color="yellow">
                {t('draw_empty_places_alert', { count: free - toDraw.length })}
              </Alert>
            ) : null}
            <Group>
              <Button
                size="md"
                color="indigo"
                loading={loading}
                disabled={toDraw.length > free}
                leftSection={<IconArrowsShuffle size={22} />}
                onClick={draw}
              >
                {t('draw_button')}
              </Button>
            </Group>
          </Stack>
        ) : null}
        {stage != null && toDraw.length < 1 && placements.length < 1 ? (
          <Text c="dimmed">{t('draw_no_teams_left')}</Text>
        ) : null}

        {stage != null ? (
          <Stack ref={boardRef} bg="var(--mantine-color-body)" p="md">
            <Group justify="space-between">
              <Badge size="lg" variant="light">
                {categoryName(stage.category_id)}
              </Badge>
              <Group>
                {revealed < placements.length ? (
                  <Button variant="default" onClick={() => setRevealed(placements.length)}>
                    {t('draw_show_all_button')}
                  </Button>
                ) : null}
                <Button
                  variant="default"
                  leftSection={<IconMaximize size={18} />}
                  onClick={() => boardRef.current?.requestFullscreen?.()}
                >
                  {t('draw_full_screen_button')}
                </Button>
              </Group>
            </Group>
            {latestPlacement != null &&
            latestTeam != null &&
            'team' in latestTeam &&
            latestTeam.team != null ? (
              <Text size="xl" fw={700} aria-live="polite">
                {showPots
                  ? t('draw_latest_with_pot', {
                      team: latestTeam.team.name,
                      pot: savedPot(latestTeam.team),
                      group: groupName(latestPlacement.stage_item_id),
                    })
                  : t('draw_latest', {
                      team: latestTeam.team.name,
                      group: groupName(latestPlacement.stage_item_id),
                    })}
              </Text>
            ) : null}
            <DrawBoard
              stage={stage}
              hidden={hidden}
              latest={latestPlacement?.team_id ?? null}
              showPots={showPots}
            />
          </Stack>
        ) : null}
        <Text size="sm" c="dimmed">
          {t('draw_adjust_note')}
        </Text>
      </Stack>
    </TournamentLayout>
  );
}
