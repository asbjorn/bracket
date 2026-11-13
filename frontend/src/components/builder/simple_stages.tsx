import { Badge, Group, Stack, Text, Title } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { SWRResponse } from 'swr';

import KnockoutBracket from '@components/brackets/knockout_bracket';
import { isGroupStage } from '@components/utils/group_stage';
import { formatStageItemInput } from '@components/utils/stage_item_input';
import { StageWithStageItems, StagesWithStageItemsResponse } from '@openapi';
import { getMatchLookup, getStageItemLookup } from '@services/lookups';
import GroupBoard, { TeamCountBadge } from './group_board';
import classes from './stages.module.css';

/**
 * The stages of a class for everyday use: groups as cards with draggable teams, playoffs as
 * brackets. Hovering a group highlights where its teams go in the playoffs, and the other way.
 */
export default function SimpleStages({
  tournamentId,
  stages,
  swrStagesResponse,
}: {
  tournamentId: number;
  stages: StageWithStageItems[];
  swrStagesResponse: SWRResponse<StagesWithStageItemsResponse>;
}) {
  const { t } = useTranslation();
  const [hoveredGroupId, setHoveredGroupId] = useState<number | null>(null);
  const stageItemsLookup = getStageItemLookup(swrStagesResponse);
  const matchesLookup = getMatchLookup(swrStagesResponse);

  return (
    <Stack gap="xl">
      {[...stages]
        .sort((a, b) => a.id - b.id)
        .map((stage) => (
          <section key={stage.id} className={classes.stageSection}>
            <Group gap="xs" mb="sm">
              <Title order={4}>{stage.name}</Title>
              {stage.is_active ? (
                <Badge color="green" variant="light">
                  {t('active_badge_label')}
                </Badge>
              ) : null}
              {isGroupStage(stage) ? <TeamCountBadge stage={stage} /> : null}
            </Group>
            {isGroupStage(stage) ? (
              <GroupBoard
                tournamentId={tournamentId}
                stage={stage}
                swrStagesResponse={swrStagesResponse}
                hoveredGroupId={hoveredGroupId}
                onHoverGroup={setHoveredGroupId}
              />
            ) : (
              <Stack gap="lg">
                {[...stage.stage_items]
                  .sort((a, b) => a.name.localeCompare(b.name) || a.id - b.id)
                  .map((item) => (
                    <div key={item.id} className={classes.groupCard}>
                      <Text fw={800} mb="xs">
                        {item.name}
                      </Text>
                      {item.type === 'SINGLE_ELIMINATION' ? (
                        <KnockoutBracket
                          stageItem={item}
                          stageItemsLookup={stageItemsLookup}
                          matchesLookup={matchesLookup}
                          hoveredGroupId={hoveredGroupId}
                          onHoverGroup={setHoveredGroupId}
                        />
                      ) : (
                        <Stack gap={4}>
                          {[...item.inputs]
                            .sort((a, b) => a.slot - b.slot)
                            .map((input) => (
                              <Text key={input.id} size="sm">
                                {formatStageItemInput(input, stageItemsLookup) ?? t('empty_place')}
                              </Text>
                            ))}
                        </Stack>
                      )}
                    </div>
                  ))}
              </Stack>
            )}
          </section>
        ))}
    </Stack>
  );
}
