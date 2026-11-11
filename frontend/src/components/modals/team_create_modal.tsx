import { Button, Checkbox, Modal, MultiSelect, Tabs, TextInput } from '@mantine/core';
import { useForm } from '@mantine/form';
import { IconUser, IconUsers, IconUsersPlus } from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { SWRResponse } from 'swr';

import SaveButton from '@components/buttons/save';
import { MultiTeamsInput } from '@components/forms/player_create_csv_input';
import { CategoryInput, categoryIdToValue, valueToCategoryId } from '@components/utils/category';
import { Category, Player, TeamsWithPlayersResponse } from '@openapi';
import { getCategories, getPlayers } from '@services/adapter';
import { createTeam, createTeams } from '@services/team';

function MultiTeamTab({
  tournament_id,
  swrTeamsResponse,
  setOpened,
  categories,
  defaultCategoryId,
}: {
  tournament_id: number;
  swrTeamsResponse: SWRResponse<TeamsWithPlayersResponse>;
  setOpened: any;
  categories: Category[];
  defaultCategoryId: number | null;
}) {
  const { t } = useTranslation();
  const form = useForm({
    initialValues: {
      names: '',
      active: true,
      category: categoryIdToValue(defaultCategoryId),
    },

    validate: {
      names: (value) => (value.length > 0 ? null : t('at_least_one_team_validation')),
    },
  });
  return (
    <form
      onSubmit={form.onSubmit(async (values) => {
        await createTeams(
          tournament_id,
          values.names,
          values.active,
          valueToCategoryId(values.category),
        );
        await swrTeamsResponse.mutate();
        setOpened(false);
      })}
    >
      <MultiTeamsInput form={form} />
      <CategoryInput categories={categories} inputProps={form.getInputProps('category')} />

      <Checkbox
        mt="md"
        label={t('active_teams_checkbox_label')}
        {...form.getInputProps('active', { type: 'checkbox' })}
      />
      <Button fullWidth style={{ marginTop: 10 }} color="green" type="submit">
        {t('save_button')}
      </Button>
    </form>
  );
}

function SingleTeamTab({
  tournament_id,
  swrTeamsResponse,
  setOpened,
  categories,
  defaultCategoryId,
}: {
  tournament_id: number;
  swrTeamsResponse: SWRResponse<TeamsWithPlayersResponse>;
  setOpened: any;
  categories: Category[];
  defaultCategoryId: number | null;
}) {
  const { t } = useTranslation();
  const { data } = getPlayers(tournament_id, false);
  const players: Player[] = data != null ? data.data.players : [];
  const form = useForm({
    initialValues: {
      name: '',
      active: true,
      player_ids: [],
      category: categoryIdToValue(defaultCategoryId),
    },
    validate: {
      name: (value) => (value.length > 0 ? null : t('too_short_name_validation')),
    },
  });
  return (
    <form
      onSubmit={form.onSubmit(async (values) => {
        await createTeam(
          tournament_id,
          values.name,
          values.active,
          values.player_ids,
          valueToCategoryId(values.category),
        );
        await swrTeamsResponse.mutate();
        setOpened(false);
      })}
    >
      <TextInput
        withAsterisk
        label={t('name_input_label')}
        placeholder={t('team_name_input_placeholder')}
        {...form.getInputProps('name')}
      />

      <CategoryInput categories={categories} inputProps={form.getInputProps('category')} />

      <Checkbox
        mt="md"
        label={t('active_teams_checkbox_label')}
        {...form.getInputProps('active', { type: 'checkbox' })}
      />

      <MultiSelect
        data={players.map((p) => ({ value: `${p.id}`, label: p.name }))}
        label={t('team_member_select_title')}
        maxDropdownHeight={160}
        searchable
        mb="12rem"
        mt={12}
        limit={25}
        {...form.getInputProps('player_ids')}
      />
      <Button fullWidth style={{ marginTop: 10 }} color="green" type="submit">
        {t('save_button')}
      </Button>
    </form>
  );
}

export default function TeamCreateModal({
  tournament_id,
  swrTeamsResponse,
  defaultCategoryId,
}: {
  tournament_id: number;
  swrTeamsResponse: SWRResponse<TeamsWithPlayersResponse>;
  defaultCategoryId: number | null;
}) {
  const { t } = useTranslation();
  const [opened, setOpened] = useState(false);
  const categories = getCategories(tournament_id).data?.data ?? [];
  return (
    <>
      <Modal opened={opened} onClose={() => setOpened(false)} title={t('create_team_modal_title')}>
        <Tabs defaultValue="single">
          <Tabs.List justify="center" grow>
            <Tabs.Tab value="single" leftSection={<IconUser size="0.8rem" />}>
              {t('single_team')}
            </Tabs.Tab>
            <Tabs.Tab value="multi" leftSection={<IconUsers size="0.8rem" />}>
              {t('multiple_teams')}
            </Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="single" pt="xs">
            <SingleTeamTab
              swrTeamsResponse={swrTeamsResponse}
              tournament_id={tournament_id}
              setOpened={setOpened}
              categories={categories}
              defaultCategoryId={defaultCategoryId}
            />
          </Tabs.Panel>

          <Tabs.Panel value="multi" pt="xs">
            <MultiTeamTab
              swrTeamsResponse={swrTeamsResponse}
              tournament_id={tournament_id}
              setOpened={setOpened}
              categories={categories}
              defaultCategoryId={defaultCategoryId}
            />
          </Tabs.Panel>
        </Tabs>
      </Modal>

      <SaveButton
        onClick={() => setOpened(true)}
        leftSection={<IconUsersPlus size={24} />}
        title={t('add_team_button')}
        mb={0}
      />
    </>
  );
}
