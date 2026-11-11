import { Alert, Badge, Button, Group, List, Stack, Table, Title } from '@mantine/core';
import { GoPlus } from '@react-icons/all-files/go/GoPlus';
import { IconAlertTriangle, IconInfoCircle, IconPencil } from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import DeleteButton from '@components/buttons/delete';
import { CategoryWarningMessage } from '@components/info/category_warnings';
import CategoryModal from '@components/modals/category_modal';
import { NoContent } from '@components/no_content/empty_table_info';
import TableLayout, { ThNotSortable } from '@components/tables/table';
import RequestErrorAlert from '@components/utils/error_alert';
import { TableSkeletonSingleColumn } from '@components/utils/skeletons';
import { capitalize, getTournamentIdFromRouter } from '@components/utils/util';
import { Category } from '@openapi';
import TournamentLayout from '@pages/tournaments/_tournament_layout';
import { getCategories, getCategoryWarnings } from '@services/adapter';
import { deleteCategory } from '@services/category';

export default function CategoriesPage() {
  const { t } = useTranslation();
  const { tournamentData } = getTournamentIdFromRouter();
  const swrCategoriesResponse = getCategories(tournamentData.id);
  const swrWarningsResponse = getCategoryWarnings(tournamentData.id);
  // `undefined`: modal closed, `null`: create a new class, otherwise: edit that class
  const [editedCategory, setEditedCategory] = useState<Category | null | undefined>(undefined);

  const categories = swrCategoriesResponse.data?.data ?? [];

  let content;
  if (swrCategoriesResponse.error) {
    content = <RequestErrorAlert error={swrCategoriesResponse.error} />;
  } else if (swrCategoriesResponse.isLoading) {
    content = <TableSkeletonSingleColumn />;
  } else if (categories.length < 1) {
    content = (
      <NoContent title={t('no_categories_title')} description={t('no_categories_description')} />
    );
  } else {
    const rows = categories.map((category) => (
      <Table.Tr key={category.id}>
        <Table.Td>{category.name}</Table.Td>
        <Table.Td>{category.age ?? '-'}</Table.Td>
        <Table.Td>
          {(swrWarningsResponse.data?.data[`${category.id}`] ?? []).length > 0 ? (
            <List size="sm" icon={<IconAlertTriangle size={16} color="orange" />} spacing={4}>
              {(swrWarningsResponse.data?.data[`${category.id}`] ?? []).map((warning) => (
                <List.Item key={warning.code}>
                  <CategoryWarningMessage warning={warning} />
                </List.Item>
              ))}
            </List>
          ) : (
            <Badge color="green" variant="light">
              {t('no_warnings_badge')}
            </Badge>
          )}
        </Table.Td>
        <Table.Td>
          {category.results_public ? (
            <Badge color="green">{t('results_public_badge')}</Badge>
          ) : (
            <Badge color="gray">{t('results_hidden_badge')}</Badge>
          )}
        </Table.Td>
        <Table.Td>
          <Group gap="xs" justify="flex-end">
            <Button
              color="green"
              size="xs"
              leftSection={<IconPencil size={20} />}
              onClick={() => setEditedCategory(category)}
            >
              {t('edit_category_title')}
            </Button>
            <DeleteButton
              onClick={async () => {
                await deleteCategory(tournamentData.id, category.id);
                await swrCategoriesResponse.mutate();
                await swrWarningsResponse.mutate();
              }}
              title={t('delete_button')}
            />
          </Group>
        </Table.Td>
      </Table.Tr>
    ));

    content = (
      <TableLayout miw={600}>
        <Table.Thead>
          <Table.Tr>
            <ThNotSortable>{t('name_table_header')}</ThNotSortable>
            <ThNotSortable>{t('category_age_input_label')}</ThNotSortable>
            <ThNotSortable>{t('nff_rules_table_header')}</ThNotSortable>
            <ThNotSortable>{t('results_title')}</ThNotSortable>
            <ThNotSortable>{null}</ThNotSortable>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>{rows}</Table.Tbody>
      </TableLayout>
    );
  }

  return (
    <TournamentLayout tournament_id={tournamentData.id}>
      {editedCategory !== undefined ? (
        <CategoryModal
          // Remount for every class, so the form starts with the values of that class
          key={editedCategory?.id ?? 'new'}
          tournamentId={tournamentData.id}
          category={editedCategory}
          swrCategoriesResponse={swrCategoriesResponse}
          onSaved={() => swrWarningsResponse.mutate()}
          opened
          setOpened={(opened) => {
            if (!opened) setEditedCategory(undefined);
          }}
        />
      ) : null}
      <Stack>
        <Group justify="space-between">
          <Title>{capitalize(t('categories_title'))}</Title>
          <Button
            variant="outline"
            color="green"
            leftSection={<GoPlus size={24} />}
            onClick={() => setEditedCategory(null)}
          >
            {t('add_category_title')}
          </Button>
        </Group>
        <Alert color="gray" icon={<IconInfoCircle />}>
          {t('categories_description')}
        </Alert>
        {content}
      </Stack>
    </TournamentLayout>
  );
}
