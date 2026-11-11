import { Alert, Button, Modal, NumberInput, Switch, TextInput } from '@mantine/core';
import { useForm } from '@mantine/form';
import { IconInfoCircle } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { SWRResponse } from 'swr';

import { CategoriesResponse, Category } from '@openapi';
import { requestSucceeded } from '@services/adapter';
import { CategoryValues, createCategory, updateCategory } from '@services/category';

// NFF: results and tables may only be published from the 13-year class (youth football)
const YOUTH_FOOTBALL_MIN_AGE = 13;

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
  opened,
  setOpened,
}: {
  tournamentId: number;
  category: Category | null;
  swrCategoriesResponse: SWRResponse<CategoriesResponse>;
  opened: boolean;
  setOpened: (opened: boolean) => void;
}) {
  const { t } = useTranslation();
  const form = useForm<{ name: string; age: number | string; results_public: boolean }>({
    initialValues: {
      name: category?.name ?? '',
      age: category?.age ?? '',
      results_public: category?.results_public ?? true,
    },
    validate: {
      name: (value) => (value.trim().length > 0 ? null : t('too_short_name_validation')),
    },
  });

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
          };
          const result =
            category == null
              ? await createCategory(tournamentId, body)
              : await updateCategory(tournamentId, category.id, body);
          if (requestSucceeded(result)) {
            await swrCategoriesResponse.mutate();
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
        <Button fullWidth mt="lg" color="green" type="submit">
          {t('save_button')}
        </Button>
      </form>
    </Modal>
  );
}
