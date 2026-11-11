import {
  Button,
  Center,
  Checkbox,
  Fieldset,
  Image,
  Modal,
  MultiSelect,
  TextInput,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useTranslation } from 'react-i18next';
import { SWRResponse } from 'swr';

import { CategoryInput, categoryIdToValue, valueToCategoryId } from '@components/utils/category';
import { DropzoneButton } from '@components/utils/file_upload';
import { FullTeamWithPlayers, Player, TeamsWithPlayersResponse } from '@openapi';
import {
  getBaseApiUrl,
  getCategories,
  getPlayers,
  removeTeamLogo,
  requestSucceeded,
} from '@services/adapter';
import { updateTeam } from '@services/team';

function TeamLogo({ team }: { team: FullTeamWithPlayers | null }) {
  if (team == null || team.logo_path == null) return null;
  return (
    <Image
      radius="md"
      alt="Logo of the team"
      src={`${getBaseApiUrl()}/static/team-logos/${team.logo_path}`}
    />
  );
}

/**
 * Edits a team. Mount it only while it's open (for the team being edited), so the form always
 * starts from the team's current data.
 */
export default function TeamUpdateModal({
  tournament_id,
  team,
  swrTeamsResponse,
  onClose,
}: {
  tournament_id: number;
  team: FullTeamWithPlayers;
  swrTeamsResponse: SWRResponse<TeamsWithPlayersResponse>;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const { data } = getPlayers(tournament_id, false);
  const players: Player[] = data != null ? data.data.players : [];
  const categories = getCategories(tournament_id).data?.data ?? [];

  const form = useForm({
    initialValues: {
      name: team.name,
      active: team.active,
      player_ids: team.players.map((player) => `${player.id}`),
      category: categoryIdToValue(team.category_id),
      club_name: team.club_name ?? '',
    },

    validate: {
      name: (value) => (value.length > 0 ? null : t('too_short_name_validation')),
    },
  });

  return (
    <>
      <Modal opened onClose={onClose} title={t('edit_team_title')}>
        <form
          onSubmit={form.onSubmit(async (values) => {
            const result = await updateTeam(
              tournament_id,
              team.id,
              values.name,
              values.active,
              values.player_ids,
              valueToCategoryId(values.category),
              values.club_name.trim() === '' ? null : values.club_name.trim(),
            );
            if (requestSucceeded(result)) {
              await swrTeamsResponse.mutate();
              onClose();
            }
          })}
        >
          <TextInput
            withAsterisk
            label={t('name_input_label')}
            placeholder={t('team_name_input_placeholder')}
            {...form.getInputProps('name')}
          />

          <CategoryInput categories={categories} inputProps={form.getInputProps('category')} />

          <TextInput
            mt="md"
            label={t('club_name_input_label')}
            description={t('club_name_input_description')}
            {...form.getInputProps('club_name')}
          />

          <Checkbox
            mt="md"
            label={t('active_team_checkbox_label')}
            {...form.getInputProps('active', { type: 'checkbox' })}
          />

          <MultiSelect
            data={players.map((p) => ({ value: `${p.id}`, label: p.name }))}
            label={t('team_member_select_title')}
            placeholder={t('team_member_select_placeholder')}
            maxDropdownHeight={160}
            searchable
            mt={12}
            limit={25}
            {...form.getInputProps('player_ids')}
          />

          <Fieldset legend={t('logo_settings_title')} mt={12} radius="md">
            <DropzoneButton
              tournamentId={tournament_id}
              teamId={team.id}
              swrResponse={swrTeamsResponse}
              variant="team"
            />
            <Center my="lg">
              <div style={{ width: '50%' }}>
                <TeamLogo team={team} />
              </div>
            </Center>
            <Button
              variant="outline"
              color="red"
              fullWidth
              onClick={async () => {
                await removeTeamLogo(tournament_id, team.id);
                await swrTeamsResponse.mutate();
              }}
            >
              {t('remove_logo')}
            </Button>
          </Fieldset>

          <Button fullWidth style={{ marginTop: 10 }} color="green" type="submit">
            {t('save_button')}
          </Button>
        </form>
      </Modal>
    </>
  );
}
