import { ActionIcon, Button, Group, Menu, Stack, Text, Title } from '@mantine/core';
import {
  IconAdjustments,
  IconArrowRight,
  IconCheck,
  IconDots,
  IconSquareArrowLeft,
  IconSquareArrowRight,
} from '@tabler/icons-react';
import { ReactNode, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { SWRResponse } from 'swr';

import ActivateNextStageModal from '@components/modals/activate_next_stage_modal';
import ActivatePreviousStageModal from '@components/modals/activate_previous_stage_modal';
import PreloadLink from '@components/utils/link';
import { StageRankingResponse, StagesWithStageItemsResponse } from '@openapi';
import { ClassStatus, Phase } from './class_status';
import classes from './stages.module.css';

function LinkButton({ href, label, primary }: { href: string; label: string; primary: boolean }) {
  return (
    <Button
      component={PreloadLink}
      href={href}
      variant={primary ? 'filled' : 'default'}
      color="indigo"
      rightSection={primary ? <IconArrowRight size={16} /> : undefined}
    >
      {label}
    </Button>
  );
}

/**
 * Where a class is (setup → draw → groups → playoffs → done) as animated steps, what that
 * means, and the one thing to do next as the main button.
 */
export default function PhaseBar({
  tournamentId,
  categoryId,
  className,
  status,
  canChangeFormat,
  swrStagesResponse,
  swrRankingsPerStageItemResponse,
  onFit,
  onFormat,
  modeSwitch,
}: {
  tournamentId: number;
  categoryId: number | null;
  className: string;
  status: ClassStatus;
  canChangeFormat: boolean;
  swrStagesResponse: SWRResponse<StagesWithStageItemsResponse>;
  swrRankingsPerStageItemResponse: SWRResponse<StageRankingResponse>;
  onFit: () => void;
  onFormat: () => void;
  modeSwitch: ReactNode;
}) {
  const { t } = useTranslation();
  const [stageDialog, setStageDialog] = useState<'previous' | 'next' | null>(null);
  const prefix = `/tournaments/${tournamentId}`;
  const phases: Phase[] = ['setup', 'draw', 'groups', 'playoffs', 'done'].filter(
    (phase) => phase !== 'playoffs' || status.playoffStage != null,
  ) as Phase[];
  const current = Math.max(0, phases.indexOf(status.phase));

  let description: string;
  let action: ReactNode;
  switch (status.phase) {
    case 'draw':
      description = t('phase_draw_description', {
        drawn: status.drawn,
        teams: status.teams,
        places: status.places,
      });
      action =
        status.teams !== status.places && status.drawn === 0 && status.teams >= 2 ? (
          <>
            <Button color="indigo" leftSection={<IconAdjustments size={18} />} onClick={onFit}>
              {t('fit_groups_open_button')}
            </Button>
            <LinkButton href={`${prefix}/draw`} label={t('draw_title')} primary={false} />
          </>
        ) : (
          <LinkButton href={`${prefix}/draw`} label={t('phase_draw_button')} primary />
        );
      break;
    case 'groups':
    case 'playoffs': {
      const finished = status.total > 0 && status.played === status.total;
      description = t(
        status.phase === 'groups' ? 'phase_groups_description' : 'phase_playoffs_description',
        { played: status.played, total: status.total },
      );
      action =
        finished && status.nextStage != null ? (
          <Button
            color="green"
            leftSection={<IconSquareArrowRight size={18} />}
            onClick={() => setStageDialog('next')}
          >
            {t('phase_start_next_button', { name: status.nextStage.name })}
          </Button>
        ) : (
          <>
            <LinkButton href={`${prefix}/results`} label={t('phase_results_button')} primary />
            <LinkButton href={`${prefix}/schedule`} label={t('planning_title')} primary={false} />
          </>
        );
      break;
    }
    case 'done':
      description = t('phase_done_description');
      action = (
        <LinkButton href={`${prefix}/ceremony`} label={t('phase_ceremony_button')} primary />
      );
      break;
    default:
      description = t('phase_setup_description');
      action = null;
  }

  return (
    <div className={classes.phaseBar}>
      <Group justify="space-between" align="flex-start" wrap="nowrap">
        <Title order={3} style={{ minWidth: 0 }}>
          {className}
        </Title>
        <Group gap="xs" wrap="nowrap">
          {modeSwitch}
          <Menu withinPortal position="bottom-end" shadow="md">
            <Menu.Target>
              <ActionIcon variant="subtle" color="gray" aria-label={t('phase_more_label')}>
                <IconDots size={20} />
              </ActionIcon>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Item
                leftSection={<IconSquareArrowLeft size={18} />}
                onClick={() => setStageDialog('previous')}
              >
                {t('previous_stage_button')}
              </Menu.Item>
              <Menu.Item
                leftSection={<IconSquareArrowRight size={18} />}
                onClick={() => setStageDialog('next')}
              >
                {t('next_stage_button')}
              </Menu.Item>
            </Menu.Dropdown>
          </Menu>
        </Group>
      </Group>

      <div
        className={classes.steps}
        style={{
          ['--step-count' as string]: phases.length,
          ['--fill' as string]: phases.length > 1 ? current / (phases.length - 1) : 0,
        }}
        role="list"
      >
        <div className={classes.track} />
        <div className={classes.trackFill} />
        {phases.map((phase, index) => {
          const state = index < current ? 'done' : index === current ? 'current' : 'todo';
          return (
            <div
              key={phase}
              className={classes.step}
              data-state={state}
              role="listitem"
              aria-current={state === 'current' ? 'step' : undefined}
            >
              <div className={classes.dot}>
                {state === 'done' ? <IconCheck size={16} /> : index + 1}
              </div>
              <span className={classes.stepLabel}>{t(`phase_${phase}`)}</span>
            </div>
          );
        })}
      </div>

      <Stack gap="sm">
        <Text size="sm">{description}</Text>
        <Group gap="xs">
          {action}
          {canChangeFormat ? (
            <Button
              variant="default"
              leftSection={<IconAdjustments size={18} />}
              onClick={onFormat}
            >
              {t('format_open_button')}
            </Button>
          ) : null}
        </Group>
      </Stack>

      <ActivatePreviousStageModal
        tournamentId={tournamentId}
        categoryId={categoryId}
        swrStagesResponse={swrStagesResponse}
        swrRankingsPerStageItemResponse={swrRankingsPerStageItemResponse}
        opened={stageDialog === 'previous'}
        onClose={() => setStageDialog(null)}
      />
      <ActivateNextStageModal
        tournamentId={tournamentId}
        categoryId={categoryId}
        swrStagesResponse={swrStagesResponse}
        swrRankingsPerStageItemResponse={swrRankingsPerStageItemResponse}
        opened={stageDialog === 'next'}
        onClose={() => setStageDialog(null)}
      />
    </div>
  );
}
