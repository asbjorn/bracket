import {
  Alert,
  Badge,
  Button,
  Checkbox,
  Group,
  List,
  Modal,
  NumberInput,
  SegmentedControl,
  Stack,
  Text,
} from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { IconAlertTriangle, IconArrowRight, IconInfoCircle } from '@tabler/icons-react';
import { AxiosError } from 'axios';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { FitGroupsPreview, PlayoffPreset, StageWithStageItems } from '@openapi';
import { requestErrorMessage, requestSucceeded } from '@services/adapter';
import { FormatParams, fitGroups, previewFitGroups } from '@services/stage';

// Fewer matches per team than this is a poor cup day for children (NFF recommends at least 3)
const MIN_MATCHES_PER_TEAM = 3;
const MAX_GROUP_SIZE = 10;
const PRESETS: PlayoffPreset[] = ['NONE', 'A', 'AB', 'ABC'];

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

/** The playoffs of a class today, as far as the format dialog needs them. */
export interface CurrentPlayoffs {
  count: number;
  thirdPlaceMatch: boolean;
  // Classes with hidden results (children's football) have no playoffs
  allowed: boolean;
}

/**
 * The format of a class: its groups for the registered teams (before the draw) and, with
 * `playoffs`, its playoffs. Shows what changes before anything is saved. Mount it only while open.
 */
export default function FitGroupsModal({
  tournamentId,
  stage,
  className,
  playoffs,
  onClose,
  onFitted,
}: {
  tournamentId: number;
  stage: StageWithStageItems;
  className: string;
  playoffs?: CurrentPlayoffs;
  onClose: () => void;
  onFitted: () => Promise<unknown>;
}) {
  const { t } = useTranslation();
  const largestGroup = Math.max(2, ...stage.stage_items.map((item) => item.team_count));
  const drawn = stage.stage_items.some((item) =>
    item.inputs.some((input) => 'team' in input && input.team != null),
  );
  const [groupSize, setGroupSize] = useState<number>(Math.min(largestGroup, MAX_GROUP_SIZE));
  const currentPreset = PRESETS[Math.min(playoffs?.count ?? 0, PRESETS.length - 1)];
  // Only sent when changed: unchanged playoffs keep their own placings
  const [preset, setPreset] = useState<PlayoffPreset>(currentPreset);
  const [thirdPlace, setThirdPlace] = useState<boolean>(playoffs?.thirdPlaceMatch ?? false);
  const params: FormatParams = {
    group_size: groupSize,
    ...(preset !== currentPreset
      ? {
          playoffs: preset,
          playoff_stage_name: t('setup_playoff_stage_name'),
          playoff_name: t('setup_playoff_name'),
        }
      : {}),
    ...(playoffs != null && thirdPlace !== playoffs.thirdPlaceMatch
      ? { third_place_match: thirdPlace }
      : {}),
  };
  // Debounced as text: a new object every render would restart the debounce forever
  const paramsKey = JSON.stringify(params);
  const [debouncedKey] = useDebouncedValue(paramsKey, 300);
  const [preview, setPreview] = useState<FitGroupsPreview | null>(null);
  const [previewKey, setPreviewKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let current = true;
    previewFitGroups(tournamentId, stage.id, JSON.parse(debouncedKey) as FormatParams)
      .then((response) => {
        if (!current) return;
        setPreview(response.data.data);
        setPreviewKey(debouncedKey);
        setError(null);
      })
      .catch((exc: AxiosError) => {
        if (!current) return;
        setPreview(null);
        setPreviewKey(null);
        setError(requestErrorMessage(exc) ?? t('error_occurred_title'));
      });
    return () => {
      current = false;
    };
  }, [tournamentId, stage.id, debouncedKey]);

  async function apply() {
    setSaving(true);
    const response = await fitGroups(tournamentId, stage.id, params);
    setSaving(false);
    if (requestSucceeded(response)) {
      await onFitted();
      onClose();
    }
  }

  const upToDate = preview != null && previewKey === paramsKey;
  const title =
    playoffs != null
      ? t('format_title', { name: className })
      : t('fit_groups_title', { name: className });
  return (
    <Modal opened onClose={onClose} title={title} size="lg">
      <Stack>
        <Text size="sm">
          {playoffs != null ? t('format_description') : t('fit_groups_description')}
        </Text>
        <NumberInput
          label={t('fit_groups_size_label')}
          description={drawn ? t('format_groups_drawn') : t('fit_groups_size_description')}
          value={groupSize}
          min={2}
          max={MAX_GROUP_SIZE}
          disabled={drawn}
          onChange={(value) =>
            setGroupSize(Math.min(MAX_GROUP_SIZE, Math.max(2, Number(value) || 2)))
          }
          w="16rem"
        />
        {playoffs != null ? (
          <Stack gap={6}>
            <Text size="sm" fw={500}>
              {t('format_playoffs_label')}
            </Text>
            {playoffs.allowed ? (
              <>
                <SegmentedControl
                  data={PRESETS.map((value) => ({
                    value,
                    label: t(`format_playoffs_${value.toLowerCase()}`),
                  }))}
                  value={preset}
                  onChange={(value) => setPreset(value as PlayoffPreset)}
                  fullWidth
                />
                <Checkbox
                  label={t('format_third_place_label')}
                  checked={thirdPlace}
                  disabled={preset === 'NONE'}
                  onChange={(event) => setThirdPlace(event.currentTarget.checked)}
                />
              </>
            ) : (
              <Alert color="gray" icon={<IconInfoCircle />}>
                {t('format_playoffs_hidden_results')}
              </Alert>
            )}
          </Stack>
        ) : null}

        {error != null ? <Alert color="red">{error}</Alert> : null}
        {preview != null ? (
          <Stack gap="xs" style={{ opacity: upToDate ? 1 : 0.5, transition: 'opacity 150ms' }}>
            <Text fw={600}>{t('fit_groups_team_count', { count: preview.team_count })}</Text>
            <Group gap="sm" wrap="wrap">
              <Text size="sm" c="dimmed" w="4rem">
                {t('fit_groups_now')}
              </Text>
              <GroupSizes sizes={preview.current_group_sizes} />
              {preview.groups_rebuilt ? (
                <>
                  <IconArrowRight size={18} />
                  <GroupSizes sizes={preview.group_sizes} />
                </>
              ) : (
                <Text size="sm" c="dimmed">
                  {t('format_groups_kept')}
                </Text>
              )}
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
            {preview.groups_rebuilt && preview.matches_per_team_min < MIN_MATCHES_PER_TEAM ? (
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
            {playoffs != null ? t('format_save_button') : t('fit_groups_button')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
