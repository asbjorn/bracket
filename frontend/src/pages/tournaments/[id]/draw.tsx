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

import { getTournamentIdFromRouter } from '@components/utils/util';
import { DrawPlacement, StageWithStageItems } from '@openapi';
import TournamentLayout from '@pages/tournaments/_tournament_layout';
import {
  getAllTeamsOfCategory,
  getCategories,
  getStages,
  requestSucceeded,
} from '@services/adapter';
import { drawTeams } from '@services/draw';

const REVEAL_INTERVAL_MS = 1500;
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
}: {
  stage: StageWithStageItems;
  hidden: Set<number>;
  latest: number | null;
}) {
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
                  <Text
                    key={input.id}
                    size="xl"
                    fw={input.team.id === latest ? 700 : 400}
                    c={input.team.id === latest ? 'indigo' : undefined}
                  >
                    {input.team.name}
                  </Text>
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
  const teams = getAllTeamsOfCategory(tournamentData.id, stage?.category_id ?? null).data ?? [];

  const [potCount, setPotCount] = useState(1);
  const [potOfTeam, setPotOfTeam] = useState<Record<number, number>>({});
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
  const potOf = (teamId: number) => Math.min(potOfTeam[teamId] ?? 1, potCount);
  const categoryName = (id: number | null) => categories.find((c) => c.id === id)?.name ?? '';

  async function draw() {
    if (stage == null) return;
    setLoading(true);
    const pots = Array.from({ length: potCount }, (_, index) =>
      toDraw.filter((team) => potOf(team.id) === index + 1).map((team) => team.id),
    ).filter((pot) => pot.length > 0);
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
        <Title>{t('draw_title')}</Title>
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
              max={10}
              onChange={(value) => setPotCount(Math.max(1, Number(value) || 1))}
              w="14rem"
            />
            {potCount > 1 ? (
              <Table maw="40rem">
                <Table.Tbody>
                  {toDraw.map((team) => (
                    <Table.Tr key={team.id}>
                      <Table.Td>{team.name}</Table.Td>
                      <Table.Td>
                        <SegmentedControl
                          size="xs"
                          data={Array.from({ length: potCount }, (_, i) => `${i + 1}`)}
                          value={`${potOf(team.id)}`}
                          onChange={(value) =>
                            setPotOfTeam({ ...potOfTeam, [team.id]: Number(value) })
                          }
                        />
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
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
            <DrawBoard
              stage={stage}
              hidden={hidden}
              latest={revealed > 0 ? (placements[revealed - 1]?.team_id ?? null) : null}
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
