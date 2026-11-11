import { Select } from '@mantine/core';
import { parseAsString, useQueryState } from 'nuqs';
import { useTranslation } from 'react-i18next';

import { Category, StageWithStageItems } from '@openapi';

// Value used in selects and the URL for "no age class" (stages and teams without a class)
export const NO_CATEGORY = 'none';

export interface CategoryOption {
  value: string;
  label: string;
}

export function categoryIdToValue(categoryId: number | null | undefined): string {
  return categoryId == null ? NO_CATEGORY : `${categoryId}`;
}

export function valueToCategoryId(value: string | null): number | null {
  return value == null || value === NO_CATEGORY ? null : Number(value);
}

export function getCategoryOptions(
  categories: Category[],
  noCategoryLabel: string,
  includeNoCategory: boolean,
): CategoryOption[] {
  const options = categories.map((category) => ({
    value: categoryIdToValue(category.id),
    label: category.name,
  }));
  return includeNoCategory ? [...options, { value: NO_CATEGORY, label: noCategoryLabel }] : options;
}

/**
 * The age class selected on a page, stored in the `category` URL parameter so that reloading or
 * sharing the page keeps the selection. Defaults to the first option.
 *
 * `includeNoCategory` adds an option for items without a class; it's always included when the
 * tournament has no classes at all.
 */
export function useSelectedCategory(categories: Category[], includeNoCategory: boolean) {
  const { t } = useTranslation();
  const [value, setValue] = useQueryState('category', parseAsString);
  const options = getCategoryOptions(
    categories,
    t('no_category_label'),
    includeNoCategory || categories.length < 1,
  );
  const selectedValue =
    options.find((option) => option.value === value)?.value ?? options[0]?.value ?? NO_CATEGORY;

  return {
    categoryId: valueToCategoryId(selectedValue),
    selectedValue,
    setSelectedValue: setValue,
    options,
  };
}

export function CategorySelector({
  options,
  selectedValue,
  setSelectedValue,
}: {
  options: CategoryOption[];
  selectedValue: string;
  setSelectedValue: (value: string | null) => void;
}) {
  const { t } = useTranslation();
  if (options.length < 2) return null;

  return (
    <Select
      label={t('category_select_label')}
      data={options}
      value={selectedValue}
      onChange={(value) => setSelectedValue(value)}
      allowDeselect={false}
      maw="20rem"
    />
  );
}

/**
 * Form input to pick the age class of a team. Hidden when the tournament has no classes.
 */
export function CategoryInput({
  categories,
  inputProps,
}: {
  categories: Category[];
  inputProps: any;
}) {
  const { t } = useTranslation();
  if (categories.length < 1) return null;

  return (
    <Select
      mt="md"
      label={t('category_select_label')}
      data={getCategoryOptions(categories, t('no_category_label'), true)}
      allowDeselect={false}
      {...inputProps}
    />
  );
}

export const ALL_CATEGORIES = 'all';

/**
 * Select to filter a list by age class, with an "all classes" option. Hidden when the tournament
 * has no classes. The value is stored in the `category` URL parameter.
 */
export function useCategoryFilter(categories: Category[]) {
  const [value, setValue] = useQueryState('category', parseAsString.withDefault(ALL_CATEGORIES));
  const validValue =
    value === ALL_CATEGORIES || categories.some((c) => categoryIdToValue(c.id) === value)
      ? value
      : ALL_CATEGORIES;
  return {
    filterValue: validValue,
    setFilterValue: setValue,
    // `undefined`: show all classes
    filterCategoryId: validValue === ALL_CATEGORIES ? undefined : valueToCategoryId(validValue),
  };
}

export function CategoryFilterSelect({
  categories,
  value,
  setValue,
}: {
  categories: Category[];
  value: string;
  setValue: (value: string | null) => void;
}) {
  const { t } = useTranslation();
  if (categories.length < 1) return null;

  return (
    <Select
      data={[
        { value: ALL_CATEGORIES, label: t('all_categories_label') },
        ...getCategoryOptions(categories, t('no_category_label'), false),
      ]}
      label={t('category_select_label')}
      value={value}
      onChange={setValue}
      allowDeselect={false}
    />
  );
}

/**
 * Maps stage item ids to the age class of their stage (`null` when the stage has no class).
 */
export function getStageItemCategoryLookup(
  stages: StageWithStageItems[],
): Record<number, number | null> {
  return Object.fromEntries(
    stages.flatMap((stage) =>
      stage.stage_items.map((stageItem) => [stageItem.id, stage.category_id ?? null]),
    ),
  );
}

/**
 * Ids of stage items whose results must not be shown publicly (NFF children's football).
 */
export function getStageItemIdsWithHiddenResults(
  stages: StageWithStageItems[],
  categories: Category[],
): Set<number> {
  const hiddenCategoryIds = new Set(categories.filter((c) => !c.results_public).map((c) => c.id));
  return new Set(
    stages
      .filter((stage) => stage.category_id != null && hiddenCategoryIds.has(stage.category_id))
      .flatMap((stage) => stage.stage_items.map((stageItem) => stageItem.id)),
  );
}
