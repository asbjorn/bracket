import { DragDropContext, Draggable, DropResult, Droppable } from '@hello-pangea/dnd';
import { Badge, Group, Text, Tooltip } from '@mantine/core';
import { IconGripVertical, IconLock } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { SWRResponse } from 'swr';

import { StageItemInput } from '@components/utils/stage_item_input';
import { StageWithStageItems, StagesWithStageItemsResponse } from '@openapi';
import { moveTeam } from '@services/stage';
import classes from './stages.module.css';

/** A ring that fills up as the matches of a group are played. */
export function ProgressRing({ played, total }: { played: number; total: number }) {
  const { t } = useTranslation();
  const percent = total > 0 ? Math.round((played / total) * 100) : 0;
  return (
    <Tooltip label={t('group_progress_tooltip', { played, total })}>
      <div className={classes.ringWrap} aria-label={t('group_progress_tooltip', { played, total })}>
        <div className={classes.ring} style={{ ['--progress' as string]: percent }} />
        <span className={classes.ringLabel}>{played}</span>
      </div>
    </Tooltip>
  );
}

function hasTeam(
  input: StageItemInput,
): input is StageItemInput & { team: { id: number; name: string } } {
  return 'team' in input && input.team != null;
}

/** The stages with two places swapped (or a team moved to an empty place), shown at once. */
function withMovedTeam(
  data: StagesWithStageItemsResponse,
  sourceId: number,
  targetId: number,
): StagesWithStageItemsResponse {
  const inputs = data.data.flatMap((stage) => stage.stage_items.flatMap((item) => item.inputs));
  const source = inputs.find((input) => input.id === sourceId);
  const target = inputs.find((input) => input.id === targetId);
  if (source == null || target == null) return data;
  const place = (input: StageItemInput, from: StageItemInput) =>
    hasTeam(from)
      ? { ...input, team_id: from.team_id, team: from.team }
      : (() => {
          const { team: _team, ...rest } = input as any;
          return { ...rest, team_id: null };
        })();
  return {
    ...data,
    data: data.data.map((stage) => ({
      ...stage,
      stage_items: stage.stage_items.map((item) => ({
        ...item,
        inputs: item.inputs.map((input) =>
          input.id === sourceId
            ? place(input, target)
            : input.id === targetId
              ? place(input, source)
              : input,
        ),
      })),
    })),
  } as StagesWithStageItemsResponse;
}

/**
 * The groups of a stage as cards with their teams. Teams can be dragged to another group: onto a
 * team to swap the two, or into a group with an empty place. Teams that have played are locked.
 */
export default function GroupBoard({
  tournamentId,
  stage,
  swrStagesResponse,
  hoveredGroupId,
  onHoverGroup,
}: {
  tournamentId: number;
  stage: StageWithStageItems;
  swrStagesResponse: SWRResponse<StagesWithStageItemsResponse>;
  hoveredGroupId: number | null;
  onHoverGroup: (groupId: number | null) => void;
}) {
  const { t } = useTranslation();
  const items = [...stage.stage_items].sort((a, b) => a.name.localeCompare(b.name) || a.id - b.id);
  const inputsById = new Map(
    items.flatMap((item) => item.inputs.map((input) => [input.id, input] as const)),
  );
  const matches = items.flatMap((item) => item.rounds.flatMap((round) => round.matches));
  // Places whose team has played a match: moving it would move its results too
  const lockedInputs = new Set(
    matches
      .filter((match) => match.played)
      .flatMap((match) => [match.stage_item_input1_id, match.stage_item_input2_id]),
  );

  async function onDragEnd(result: DropResult) {
    const source = inputsById.get(Number(result.draggableId));
    if (source == null || !hasTeam(source)) return;
    let targetId: number | null = null;
    if (result.combine != null) {
      targetId = Number(result.combine.draggableId);
    } else if (
      result.destination != null &&
      result.destination.droppableId !== result.source.droppableId
    ) {
      const group = items.find((item) => `${item.id}` === result.destination?.droppableId);
      if (group == null) return;
      const slots = [...group.inputs].sort((a, b) => a.slot - b.slot);
      const empty = slots.find((input) => !hasTeam(input));
      targetId = (empty ?? slots[Math.min(result.destination.index, slots.length - 1)]).id;
    }
    if (targetId == null || targetId === source.id || swrStagesResponse.data == null) return;

    await swrStagesResponse.mutate(withMovedTeam(swrStagesResponse.data, source.id, targetId), {
      revalidate: false,
    });
    // A refused move shows its error, and reloading puts the team back
    await moveTeam(tournamentId, stage.id, source.team.id, targetId);
    await swrStagesResponse.mutate();
  }

  return (
    <DragDropContext onDragEnd={onDragEnd}>
      <div className={classes.groupGrid}>
        {items.map((item) => {
          const groupMatches = item.rounds.flatMap((round) => round.matches);
          const played = groupMatches.filter((match) => match.played).length;
          const slots = [...item.inputs].sort((a, b) => a.slot - b.slot);
          return (
            <div
              key={item.id}
              className={`${classes.groupCard} ${hoveredGroupId === item.id ? classes.linked : ''}`}
              onMouseEnter={() => onHoverGroup(item.id)}
              onMouseLeave={() => onHoverGroup(null)}
            >
              <div className={classes.groupHeader}>
                <div style={{ minWidth: 0 }}>
                  <Text fw={800} truncate>
                    {item.name}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {t('group_match_count', { count: groupMatches.length })}
                  </Text>
                </div>
                {groupMatches.length > 0 ? (
                  <ProgressRing played={played} total={groupMatches.length} />
                ) : null}
              </div>
              <Droppable droppableId={`${item.id}`} isCombineEnabled>
                {(provided) => (
                  <div
                    className={classes.slots}
                    ref={provided.innerRef}
                    {...provided.droppableProps}
                  >
                    {slots.map((input, index) => {
                      const locked = lockedInputs.has(input.id);
                      return (
                        <Draggable
                          key={input.id}
                          draggableId={`${input.id}`}
                          index={index}
                          isDragDisabled={!hasTeam(input) || locked}
                        >
                          {(dragProvided, snapshot) =>
                            hasTeam(input) ? (
                              <div
                                ref={dragProvided.innerRef}
                                {...dragProvided.draggableProps}
                                {...dragProvided.dragHandleProps}
                                className={classes.teamChip}
                                data-dragging={snapshot.isDragging}
                                data-combine={snapshot.combineTargetFor != null}
                                data-locked={locked}
                                title={locked ? t('group_team_locked') : t('group_team_drag')}
                              >
                                {locked ? (
                                  <IconLock size={14} className={classes.handle} />
                                ) : (
                                  <IconGripVertical size={14} className={classes.handle} />
                                )}
                                <span className={classes.teamName}>{input.team.name}</span>
                              </div>
                            ) : (
                              <div
                                ref={dragProvided.innerRef}
                                {...dragProvided.draggableProps}
                                {...dragProvided.dragHandleProps}
                                className={classes.emptySlot}
                                data-combine={snapshot.combineTargetFor != null}
                              >
                                {t('empty_place')}
                              </div>
                            )
                          }
                        </Draggable>
                      );
                    })}
                    {provided.placeholder}
                  </div>
                )}
              </Droppable>
            </div>
          );
        })}
      </div>
    </DragDropContext>
  );
}

/** Number of teams in the groups of a stage, as a small badge. */
export function TeamCountBadge({ stage }: { stage: StageWithStageItems }) {
  const { t } = useTranslation();
  const inputs = stage.stage_items.flatMap((item) => item.inputs);
  const teams = inputs.filter(hasTeam).length;
  return (
    <Group gap={4}>
      <Badge variant="light" color={teams === inputs.length ? 'green' : 'gray'}>
        {t('group_places_badge', { teams, places: inputs.length })}
      </Badge>
    </Group>
  );
}
