import {
  Alert,
  Button,
  Fieldset,
  Grid,
  Group,
  Modal,
  NumberInput,
  Select,
  Switch,
  TextInput,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { IconInfoCircle } from '@tabler/icons-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { SWRResponse } from 'swr';

import {
  ALL_DAYS,
  DaysHours,
  DaysHoursFields,
  fromWindows,
  toWindows,
} from '@components/scheduling/days_hours_editor';
import { GAME_FORMATS } from '@components/scheduling/match_plan_panel';
import { defaultMaxMatchesPerDay } from '@components/utils/nff_presets';
import { CategoriesResponse, Category, CategoryKind, GameFormat } from '@openapi';
import { getPlanningHours, getTimeWindows, requestSucceeded } from '@services/adapter';
import { CategoryValues, createCategory, updateCategory } from '@services/category';
import { saveCategoryHours } from '@services/planning';

// NFF: results and tables may only be published from the 13-year class (youth football)
const YOUTH_FOOTBALL_MIN_AGE = 13;

function optionalNumber(value: number | string): number | null {
  return value === '' ? null : Number(value);
}

export function defaultResultsPublic(age: number | null) {
  return age == null || age >= YOUTH_FOOTBALL_MIN_AGE;
}

/**
 * Modal to create a new age class (`category == null`) or edit an existing one.
 */
export default function CategoryModal({
  tournamentId,
  category,
  swrCategoriesResponse,
  onSaved,
  opened,
  setOpened,
}: {
  tournamentId: number;
  category: Category | null;
  swrCategoriesResponse: SWRResponse<CategoriesResponse>;
  onSaved: () => void;
  opened: boolean;
  setOpened: (opened: boolean) => void;
}) {
  const { t } = useTranslation();
  const form = useForm<{
    name: string;
    age: number | string;
    results_public: boolean;
    duration_minutes: number | string;
    margin_minutes: number | string;
    min_rest_minutes: number | string;
    game_format: string | null;
    max_matches_per_day: number | string;
    kind: string | null;
    kind_note: string;
  }>({
    initialValues: {
      name: category?.name ?? '',
      age: category?.age ?? '',
      results_public: category?.results_public ?? true,
      duration_minutes: category?.duration_minutes ?? '',
      margin_minutes: category?.margin_minutes ?? '',
      min_rest_minutes: category?.min_rest_minutes ?? '',
      game_format: category?.game_format ?? null,
      max_matches_per_day: category?.max_matches_per_day ?? '',
      kind: category?.kind ?? null,
      kind_note: category?.kind_note ?? '',
    },
    validate: {
      name: (value) => (value.trim().length > 0 ? null : t('too_short_name_validation')),
    },
  });

  const cupWindows = getTimeWindows(tournamentId).data?.data ?? [];
  const swrPlanningHours = getPlanningHours(tournamentId);
  const savedWindows =
    category != null ? (swrPlanningHours.data?.data.categories[`${category.id}`] ?? []) : [];
  const [hours, setHours] = useState<DaysHours>(ALL_DAYS);
  // Start from the saved days/hours whenever the modal opens
  useEffect(() => {
    if (opened) setHours(fromWindows(cupWindows, savedWindows));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opened, swrPlanningHours.data, cupWindows.length]);
  const ageValue = form.getValues().age === '' ? null : Number(form.getValues().age);

  return (
    <Modal
      opened={opened}
      onClose={() => setOpened(false)}
      title={category == null ? t('add_category_title') : t('edit_category_title')}
    >
      <form
        onSubmit={form.onSubmit(async (values) => {
          const body: CategoryValues = {
            name: values.name.trim(),
            age: values.age === '' ? null : Number(values.age),
            results_public: values.results_public,
            duration_minutes: optionalNumber(values.duration_minutes),
            margin_minutes: optionalNumber(values.margin_minutes),
            min_rest_minutes: optionalNumber(values.min_rest_minutes),
            game_format: values.game_format as GameFormat | null,
            max_matches_per_day: optionalNumber(values.max_matches_per_day),
            kind: values.kind as CategoryKind | null,
            kind_note: values.kind_note.trim() === '' ? null : values.kind_note.trim(),
          };
          const result =
            category == null
              ? await createCategory(tournamentId, body)
              : await updateCategory(tournamentId, category.id, body);
          if (requestSucceeded(result) && 'data' in result) {
            const categoryId = category?.id ?? result.data.data.id;
            await saveCategoryHours(tournamentId, categoryId, toWindows(cupWindows, hours));
            await swrPlanningHours.mutate();
            await swrCategoriesResponse.mutate();
            onSaved();
            form.reset();
            setOpened(false);
          }
        })}
      >
        <TextInput
          withAsterisk
          label={t('name_input_label')}
          placeholder={t('category_name_input_placeholder')}
          {...form.getInputProps('name')}
        />
        <NumberInput
          mt="md"
          label={t('category_age_input_label')}
          description={t('category_age_input_description')}
          min={4}
          max={99}
          allowDecimal={false}
          {...form.getInputProps('age')}
          onChange={(value) => {
            form.setFieldValue('age', value);
            // Follow the NFF rule until the user chooses otherwise
            if (!form.isDirty('results_public')) {
              form.setFieldValue(
                'results_public',
                defaultResultsPublic(value === '' ? null : Number(value)),
              );
              form.resetDirty({ ...form.getValues(), age: value });
            }
          }}
        />
        <Group mt="md" align="end" grow>
          <Select
            label={t('category_kind_label')}
            data={(['BOYS', 'GIRLS', 'MIXED'] as CategoryKind[]).map((kind) => ({
              value: kind,
              label: t(`category_kind_${kind.toLowerCase()}`),
            }))}
            clearable
            {...form.getInputProps('kind')}
          />
          <TextInput
            label={t('category_kind_note_label')}
            placeholder={t('category_kind_note_placeholder')}
            maxLength={200}
            {...form.getInputProps('kind_note')}
          />
        </Group>
        <Switch
          mt="lg"
          label={t('results_public_label')}
          description={t('results_public_description')}
          {...form.getInputProps('results_public', { type: 'checkbox' })}
        />
        {!form.getValues().results_public ? (
          <Alert mt="md" color="gray" icon={<IconInfoCircle />}>
            {t('results_hidden_alert')}
          </Alert>
        ) : null}
        <Fieldset legend={t('category_timing_legend')} mt="lg" radius="md">
          <Grid>
            <Grid.Col span={{ sm: 6 }}>
              <NumberInput
                label={t('match_duration_label')}
                placeholder={t('tournament_default_placeholder')}
                min={1}
                {...form.getInputProps('duration_minutes')}
              />
            </Grid.Col>
            <Grid.Col span={{ sm: 6 }}>
              <NumberInput
                label={t('time_between_matches_label')}
                placeholder={t('tournament_default_placeholder')}
                min={0}
                {...form.getInputProps('margin_minutes')}
              />
            </Grid.Col>
            <Grid.Col span={{ sm: 6 }}>
              <NumberInput
                label={t('min_rest_label')}
                placeholder={t('tournament_default_placeholder')}
                min={0}
                {...form.getInputProps('min_rest_minutes')}
              />
            </Grid.Col>
            <Grid.Col span={{ sm: 6 }}>
              <Select
                label={t('game_format_label')}
                description={t('category_game_format_description')}
                placeholder={t('game_format_any')}
                clearable
                data={GAME_FORMATS}
                {...form.getInputProps('game_format')}
              />
            </Grid.Col>
            <Grid.Col span={{ sm: 6 }}>
              <NumberInput
                label={t('max_matches_per_day_label')}
                description={t('max_matches_per_day_description')}
                placeholder={`${defaultMaxMatchesPerDay(ageValue) ?? t('max_matches_per_day_no_limit')}`}
                min={1}
                max={20}
                allowDecimal={false}
                {...form.getInputProps('max_matches_per_day')}
              />
            </Grid.Col>
          </Grid>
        </Fieldset>
        <Fieldset legend={t('class_hours_label')} mt="lg" radius="md">
          <DaysHoursFields cupWindows={cupWindows} value={hours} onChange={setHours} />
        </Fieldset>
        <Button fullWidth mt="lg" color="green" type="submit">
          {t('save_button')}
        </Button>
      </form>
    </Modal>
  );
}
