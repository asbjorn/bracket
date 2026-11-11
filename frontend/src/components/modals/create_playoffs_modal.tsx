import {
  ActionIcon,
  Alert,
  Button,
  Checkbox,
  Group,
  Modal,
  MultiSelect,
  Stack,
  Text,
  TextInput,
} from '@mantine/core';
import { IconInfoCircle, IconTournament, IconTrash } from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { SWRResponse } from 'swr';

import { PlayoffBody, StageWithStageItems, StagesWithStageItemsResponse } from '@openapi';
import { requestSucceeded } from '@services/adapter';
import { createPlayoffs } from '@services/playoffs';

const PLAYOFF_NAMES = ['A', 'B', 'C', 'D'];

/**
 * Splits the placings 1..groupSize into `count` playoffs of (almost) equal size, best first.
 */
export function splitPlacings(groupSize: number, count: number): number[][] {
  const result: number[][] = [];
  let next = 1;
  for (let index = 0; index < count; index += 1) {
    const size = Math.ceil((groupSize - next + 1) / (count - index));
    result.push(Array.from({ length: size }, (_, i) => next + i));
    next += size;
  }
  return result.filter((placings) => placings.length > 0);
}

function presetPlayoffs(t: any, groupSize: number, count: number): PlayoffBody[] {
  return splitPlacings(groupSize, count).map((placings, index) => ({
    name: t('playoff_default_name', { name: PLAYOFF_NAMES[index] }),
    placings,
    third_place_match: false,
  }));
}

/**
 * Creates a stage with knockout playoffs (e.g. A and B playoffs) after a group stage.
 */
export default function CreatePlayoffsModal({
  tournamentId,
  groupStage,
  swrStagesResponse,
}: {
  tournamentId: number;
  groupStage: StageWithStageItems;
  swrStagesResponse: SWRResponse<StagesWithStageItemsResponse>;
}) {
  const { t } = useTranslation();
  const [opened, setOpened] = useState(false);
  const groups = groupStage.stage_items;
  const smallestGroup = Math.min(...groups.map((group) => group.team_count));
  const [stageName, setStageName] = useState(t('playoffs_stage_default_name'));
  const [playoffs, setPlayoffs] = useState<PlayoffBody[]>(() =>
    presetPlayoffs(t, smallestGroup, 2),
  );

  const placingOptions = Array.from({ length: smallestGroup }, (_, i) => ({
    value: `${i + 1}`,
    label: t('placing_label', { placing: i + 1 }),
  }));

  function updatePlayoff(index: number, update: Partial<PlayoffBody>) {
    setPlayoffs(playoffs.map((playoff, i) => (i === index ? { ...playoff, ...update } : playoff)));
  }

  return (
    <>
      <Modal
        opened={opened}
        onClose={() => setOpened(false)}
        title={t('create_playoffs_title')}
        size="40rem"
      >
        <Stack>
          <Alert color="gray" icon={<IconInfoCircle />}>
            {t('create_playoffs_description', { stage: groupStage.name, count: groups.length })}
          </Alert>
          <Group>
            {[1, 2, 3].map((count) => (
              <Button
                key={count}
                variant="light"
                size="xs"
                onClick={() => setPlayoffs(presetPlayoffs(t, smallestGroup, count))}
              >
                {t(`playoffs_preset_${count}`)}
              </Button>
            ))}
          </Group>
          <TextInput
            label={t('name_input_label')}
            value={stageName}
            onChange={(event) => setStageName(event.currentTarget.value)}
          />
          {playoffs.map((playoff, index) => {
            const teamCount = playoff.placings.length * groups.length;
            return (
              <Stack
                key={index}
                gap="xs"
                p="sm"
                style={{ border: '1px solid var(--mantine-color-default-border)', borderRadius: 8 }}
              >
                <Group align="end">
                  <TextInput
                    style={{ flex: 1 }}
                    label={t('playoff_name_label')}
                    value={playoff.name}
                    onChange={(event) => updatePlayoff(index, { name: event.currentTarget.value })}
                  />
                  <ActionIcon
                    variant="subtle"
                    color="red"
                    size="lg"
                    disabled={playoffs.length < 2}
                    onClick={() => setPlayoffs(playoffs.filter((_, i) => i !== index))}
                  >
                    <IconTrash size={20} />
                  </ActionIcon>
                </Group>
                <MultiSelect
                  label={t('playoff_placings_label')}
                  data={placingOptions}
                  value={playoff.placings.map((placing) => `${placing}`)}
                  onChange={(values) =>
                    updatePlayoff(index, {
                      placings: values.map(Number).sort((a, b) => a - b),
                    })
                  }
                />
                <Checkbox
                  label={t('third_place_match_label')}
                  disabled={teamCount < 4}
                  checked={playoff.third_place_match && teamCount >= 4}
                  onChange={(event) =>
                    updatePlayoff(index, { third_place_match: event.currentTarget.checked })
                  }
                />
                <Text size="sm" c="dimmed">
                  {t('playoff_team_count', { count: teamCount })}
                </Text>
              </Stack>
            );
          })}
          <Button
            variant="subtle"
            onClick={() =>
              setPlayoffs([
                ...playoffs,
                {
                  name: t('playoff_default_name', {
                    name: PLAYOFF_NAMES[playoffs.length] ?? playoffs.length + 1,
                  }),
                  placings: [],
                  third_place_match: false,
                },
              ])
            }
          >
            {t('add_playoff_button')}
          </Button>
          <Button
            color="green"
            onClick={async () => {
              const result = await createPlayoffs(tournamentId, {
                group_stage_id: groupStage.id,
                stage_name: stageName,
                playoffs: playoffs.map((playoff) => ({
                  ...playoff,
                  third_place_match:
                    playoff.third_place_match && playoff.placings.length * groups.length >= 4,
                })),
              });
              if (requestSucceeded(result)) {
                await swrStagesResponse.mutate();
                setOpened(false);
              }
            }}
          >
            {t('create_playoffs_button')}
          </Button>
        </Stack>
      </Modal>
      <Button
        size="md"
        mb="10"
        variant="outline"
        color="indigo"
        leftSection={<IconTournament size={24} />}
        onClick={() => setOpened(true)}
      >
        {t('create_playoffs_title')}
      </Button>
    </>
  );
}
