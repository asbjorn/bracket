import { Alert, Badge, Button, Group, List, Modal, NumberInput, Stack, Text } from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { IconAlertTriangle, IconArrowRight } from '@tabler/icons-react';
import { AxiosError } from 'axios';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { FitGroupsPreview, StageWithStageItems } from '@openapi';
import { requestErrorMessage, requestSucceeded } from '@services/adapter';
import { fitGroups, previewFitGroups } from '@services/stage';

// Fewer matches per team than this is a poor cup day for children (NFF recommends at least 3)
const MIN_MATCHES_PER_TEAM = 3;
const MAX_GROUP_SIZE = 10;

function GroupSizes({ sizes }: { sizes: number[] }) {
  return (
    <Group gap={4}>
      {sizes.map((size, index) => (
        <Badge key={index} variant="light" color="gray" size="lg">
          {size}
        </Badge>
      ))}
    </Group>
  );
}

/**
 * Before the draw: replaces the groups of a class by groups for its registered teams, with a
 * preview of what changes. Mount it only while it's open.
 */
export default function FitGroupsModal({
  tournamentId,
  stage,
  className,
  onClose,
  onFitted,
}: {
  tournamentId: number;
  stage: StageWithStageItems;
  className: string;
  onClose: () => void;
  onFitted: () => Promise<unknown>;
}) {
  const { t } = useTranslation();
  const largestGroup = Math.max(2, ...stage.stage_items.map((item) => item.team_count));
  const [groupSize, setGroupSize] = useState<number>(Math.min(largestGroup, MAX_GROUP_SIZE));
  const [debouncedSize] = useDebouncedValue(groupSize, 300);
  const [preview, setPreview] = useState<FitGroupsPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let current = true;
    previewFitGroups(tournamentId, stage.id, debouncedSize)
      .then((response) => {
        if (!current) return;
        setPreview(response.data.data);
        setError(null);
      })
      .catch((exc: AxiosError) => {
        if (!current) return;
        setPreview(null);
        setError(requestErrorMessage(exc) ?? t('error_occurred_title'));
      });
    return () => {
      current = false;
    };
  }, [tournamentId, stage.id, debouncedSize]);

  async function apply() {
    setSaving(true);
    const response = await fitGroups(tournamentId, stage.id, groupSize);
    setSaving(false);
    if (requestSucceeded(response)) {
      await onFitted();
      onClose();
    }
  }

  const upToDate = preview != null && debouncedSize === groupSize;
  return (
    <Modal opened onClose={onClose} title={t('fit_groups_title', { name: className })} size="lg">
      <Stack>
        <Text size="sm">{t('fit_groups_description')}</Text>
        <NumberInput
          label={t('fit_groups_size_label')}
          description={t('fit_groups_size_description')}
          value={groupSize}
          min={2}
          max={MAX_GROUP_SIZE}
          onChange={(value) =>
            setGroupSize(Math.min(MAX_GROUP_SIZE, Math.max(2, Number(value) || 2)))
          }
          w="16rem"
        />

        {error != null ? <Alert color="red">{error}</Alert> : null}
        {preview != null ? (
          <Stack gap="xs" style={{ opacity: upToDate ? 1 : 0.5 }}>
            <Text fw={600}>{t('fit_groups_team_count', { count: preview.team_count })}</Text>
            <Group gap="sm" wrap="wrap">
              <Text size="sm" c="dimmed" w="4rem">
                {t('fit_groups_now')}
              </Text>
              <GroupSizes sizes={preview.current_group_sizes} />
              <IconArrowRight size={18} />
              <GroupSizes sizes={preview.group_sizes} />
            </Group>
            <Text size="sm">
              {t('fit_groups_group_count', { count: preview.group_sizes.length })}
              {' · '}
              {preview.matches_per_team_min === preview.matches_per_team_max
                ? t('fit_groups_matches_per_team', { count: preview.matches_per_team_min })
                : t('fit_groups_matches_per_team_range', {
                    min: preview.matches_per_team_min,
                    max: preview.matches_per_team_max,
                  })}
              {' · '}
              {t('fit_groups_match_count', { count: preview.match_count })}
            </Text>
            {preview.playoffs.length > 0 ? (
              <List size="sm" spacing={2}>
                {preview.playoffs.map((playoff) => (
                  <List.Item key={playoff.name}>
                    {t('fit_groups_playoff', { name: playoff.name, count: playoff.team_count })}
                  </List.Item>
                ))}
              </List>
            ) : null}
            {preview.matches_per_team_min < MIN_MATCHES_PER_TEAM ? (
              <Alert color="yellow" icon={<IconAlertTriangle />}>
                {t('fit_groups_few_matches_alert', { count: preview.matches_per_team_min })}
              </Alert>
            ) : null}
            {preview.removed_playoffs.length > 0 ? (
              <Alert color="orange" icon={<IconAlertTriangle />}>
                {t('fit_groups_removed_playoffs_alert', {
                  names: preview.removed_playoffs.join(', '),
                })}
              </Alert>
            ) : null}
            {preview.planned_match_count > 0 ? (
              <Alert color="orange" icon={<IconAlertTriangle />}>
                {t('fit_groups_planned_alert', { count: preview.planned_match_count })}
              </Alert>
            ) : null}
          </Stack>
        ) : null}

        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {t('cancel_button')}
          </Button>
          <Button color="indigo" loading={saving} disabled={!upToDate} onClick={apply}>
            {t('fit_groups_button')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
