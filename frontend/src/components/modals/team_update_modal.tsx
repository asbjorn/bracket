import {
  Button,
  Center,
  Checkbox,
  Fieldset,
  Image,
  Modal,
  MultiSelect,
  NumberInput,
  TextInput,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { SWRResponse } from 'swr';

import { TitleWithHelp } from '@components/help/help_button';
import { CategoryInput, categoryIdToValue, valueToCategoryId } from '@components/utils/category';
import { DropzoneButton } from '@components/utils/file_upload';
import { ClubSelect } from '@components/utils/club_select';
import { FullTeamWithPlayers, Player, TeamsWithPlayersResponse } from '@openapi';
import {
  getBaseApiUrl,
  getCategories,
  getPlayers,
  removeTeamLogo,
  requestSucceeded,
  getAllTeams,
  getTeamConflicts,
} from '@services/adapter';
import { setTeamConflicts, updateTeam } from '@services/team';

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
  const allTeams = getAllTeams(tournament_id).data ?? [];
  const swrConflicts = getTeamConflicts(tournament_id);
  const conflictIds = (swrConflicts.data?.data ?? []).flatMap((pair) =>
    pair.team1_id === team.id
      ? [`${pair.team2_id}`]
      : pair.team2_id === team.id
        ? [`${pair.team1_id}`]
        : [],
  );
  // `null` until changed: the saved conflicts may still be loading
  const [conflicts, setConflicts] = useState<string[] | null>(null);
  const categoryName = (id: number | null) => categories.find((c) => c.id === id)?.name;

  const form = useForm({
    initialValues: {
      name: team.name,
      active: team.active,
      player_ids: team.players.map((player) => `${player.id}`),
      category: categoryIdToValue(team.category_id),
      club: team.club_id != null ? `${team.club_id}` : (null as string | null),
      squad_size: (team.squad_size ?? '') as number | string,
      pot: (team.pot ?? '') as number | string,
    },

    validate: {
      name: (value) => (value.length > 0 ? null : t('too_short_name_validation')),
    },
  });

  return (
    <>
      <Modal
        opened
        onClose={onClose}
        title={<TitleWithHelp help="team_edit">{t('edit_team_title')}</TitleWithHelp>}
      >
        <form
          onSubmit={form.onSubmit(async (values) => {
            const result = await updateTeam(
              tournament_id,
              team.id,
              values.name,
              values.active,
              values.player_ids,
              valueToCategoryId(values.category),
              values.club != null ? Number(values.club) : null,
              values.squad_size === '' ? null : Number(values.squad_size),
              values.pot === '' ? null : Number(values.pot),
            );
            if (requestSucceeded(result) && conflicts != null) {
              await setTeamConflicts(tournament_id, team.id, conflicts.map(Number));
              await swrConflicts.mutate();
            }
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

          <ClubSelect
            tournamentId={tournament_id}
            value={form.values.club}
            onChange={(club) => form.setFieldValue('club', club)}
          />

          <NumberInput
            mt="md"
            label={t('squad_size_label')}
            description={t('squad_size_description')}
            min={1}
            max={60}
            w="12rem"
            {...form.getInputProps('squad_size')}
          />

          <NumberInput
            mt="md"
            label={t('team_pot_label')}
            description={t('team_pot_description')}
            placeholder="1"
            min={1}
            max={10}
            w="12rem"
            {...form.getInputProps('pot')}
          />

          <MultiSelect
            mt="md"
            label={t('team_conflicts_label')}
            description={t('team_conflicts_description')}
            data={allTeams
              .filter((other) => other.id !== team.id)
              .sort((a, b) => a.name.localeCompare(b.name))
              .map((other) => ({
                value: `${other.id}`,
                label: [other.name, categoryName(other.category_id)].filter(Boolean).join(' · '),
              }))}
            value={conflicts ?? conflictIds}
            onChange={setConflicts}
            searchable
            clearable
            hidePickedOptions
            maxDropdownHeight={200}
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
