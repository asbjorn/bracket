import { Badge, Button, Center, Group, Pagination, Switch, Table, Text } from '@mantine/core';
import { BiEditAlt } from '@react-icons/all-files/bi/BiEditAlt';
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { SWRResponse } from 'swr';

import DeleteButton from '@components/buttons/delete';
import PlayerList from '@components/info/player_list';
import TeamUpdateModal from '@components/modals/team_update_modal';
import { NoContent, NoContentLink } from '@components/no_content/empty_table_info';
import { DateTime } from '@components/utils/datetime';
import RequestErrorAlert from '@components/utils/error_alert';
import { TableSkeletonSingleColumn } from '@components/utils/skeletons';
import { TournamentMinimal } from '@components/utils/tournament';
import { Category, FullTeamWithPlayers, TeamsWithPlayersResponse } from '@openapi';
import { getParticipatingClubs } from '@services/adapter';
import { deleteTeam, setTeamCheckedIn } from '@services/team';
import WithdrawButton from '@components/buttons/withdraw_team';
import TableLayout, { TableState, ThNotSortable, ThSortable, sortTableEntries } from './table';

/** Whether a click was on a button, switch, link or input inside the row (or in a modal). */
function isInsideControl(event: React.MouseEvent) {
  const target = event.target as HTMLElement;
  return (
    target.closest('button, a, input, label, [role="switch"], [role="dialog"]') != null ||
    !event.currentTarget.contains(target)
  );
}

export default function TeamsTable({
  tournamentData,
  swrTeamsResponse,
  teams,
  categories,
  tableState,
  teamCount,
}: {
  tournamentData: TournamentMinimal;
  swrTeamsResponse: SWRResponse<TeamsWithPlayersResponse>;
  teams: FullTeamWithPlayers[];
  categories: Category[];
  tableState: TableState;
  teamCount: number;
}) {
  const { t } = useTranslation();
  const [editedTeamId, setEditedTeamId] = useState<number | null>(null);
  const clubNames = Object.fromEntries(
    (getParticipatingClubs(tournamentData.id).data?.data ?? []).map((club) => [club.id, club.name]),
  );
  if (swrTeamsResponse.error) return <RequestErrorAlert error={swrTeamsResponse.error} />;

  if (swrTeamsResponse.isLoading) {
    return <TableSkeletonSingleColumn />;
  }

  const showCategories = categories.length > 0;
  const categoryNames = Object.fromEntries(categories.map((c) => [c.id, c.name]));

  const rows = teams
    .sort((p1: FullTeamWithPlayers, p2: FullTeamWithPlayers) =>
      sortTableEntries(p1, p2, tableState),
    )
    .map((team) => (
      <Table.Tr
        key={team.id}
        style={{ cursor: 'pointer' }}
        tabIndex={0}
        aria-label={t('edit_team_title')}
        onClick={(event) => {
          // The switch and the buttons in the row do their own thing
          if (!isInsideControl(event)) setEditedTeamId(team.id);
        }}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && event.target === event.currentTarget) {
            setEditedTeamId(team.id);
          }
        }}
      >
        <Table.Td>
          {team.active ? (
            <Badge color="green">{t('active')}</Badge>
          ) : (
            <Badge color="red">{t('inactive')}</Badge>
          )}
        </Table.Td>
        <Table.Td>
          <Group gap="xs">
            {team.name}
            {team.pot != null ? (
              <Badge color="gray" variant="light" title={t('team_pot_label')}>
                {t('draw_pot_badge', { pot: team.pot })}
              </Badge>
            ) : null}
            {team.withdrawn ? (
              <Badge color="red" variant="outline">
                {t('withdrawn_badge')}
              </Badge>
            ) : null}
          </Group>
        </Table.Td>
        <Table.Td>
          {team.club_id != null ? (
            clubNames[team.club_id]
          ) : (
            <Text size="sm" c="dimmed">
              –
            </Text>
          )}
        </Table.Td>
        <Table.Td>
          <Switch
            checked={team.checked_in}
            color="green"
            aria-label={t('checked_in_label')}
            onChange={async (event) => {
              await setTeamCheckedIn(tournamentData.id, team.id, event.currentTarget.checked);
              await swrTeamsResponse.mutate();
            }}
          />
        </Table.Td>
        {showCategories ? (
          <Table.Td>
            {team.category_id == null ? (
              <Badge color="gray" variant="light">
                {t('no_category_label')}
              </Badge>
            ) : (
              <Badge variant="light">{categoryNames[team.category_id]}</Badge>
            )}
          </Table.Td>
        ) : null}
        <Table.Td>
          <PlayerList team={team} />
        </Table.Td>
        <Table.Td>
          <DateTime datetime={team.created} />
        </Table.Td>
        <Table.Td>
          <Button
            color="green"
            size="xs"
            style={{ marginRight: 10 }}
            onClick={() => setEditedTeamId(team.id)}
            leftSection={<BiEditAlt size={20} />}
          >
            {t('edit_team_title')}
          </Button>
          <WithdrawButton
            tournamentId={tournamentData.id}
            team={team}
            onChanged={async () => {
              await swrTeamsResponse.mutate();
            }}
          />
          <DeleteButton
            onClick={async () => {
              await deleteTeam(tournamentData.id, team.id);
              await swrTeamsResponse.mutate();
            }}
            title={t('delete_team_button')}
          />
        </Table.Td>
      </Table.Tr>
    ));

  if (rows.length < 1) {
    return (
      <NoContent
        title={t('no_teams_title')}
        description={t('no_teams_description')}
        actions={
          <>
            <NoContentLink
              href={`/tournaments/${tournamentData.id}/registrations`}
              label={t('registrations_title')}
              primary
            />
            <NoContentLink
              href={`/tournaments/${tournamentData.id}/clubs`}
              label={t('participating_clubs_title')}
            />
          </>
        }
      />
    );
  }

  const editedTeam = teams.find((team) => team.id === editedTeamId) ?? null;
  return (
    <>
      {editedTeam != null ? (
        <TeamUpdateModal
          key={editedTeam.id}
          tournament_id={tournamentData.id}
          team={editedTeam}
          swrTeamsResponse={swrTeamsResponse}
          onClose={() => setEditedTeamId(null)}
        />
      ) : null}
      <TableLayout miw={850}>
        <Table.Thead>
          <Table.Tr>
            <ThSortable state={tableState} field="active">
              {t('status')}
            </ThSortable>
            <ThSortable state={tableState} field="name">
              {t('name_table_header')}
            </ThSortable>
            <ThNotSortable>{t('club_name_input_label')}</ThNotSortable>
            <ThNotSortable>{t('checked_in_label')}</ThNotSortable>
            {showCategories ? <ThNotSortable>{t('category_select_label')}</ThNotSortable> : null}
            <ThNotSortable>{t('members_table_header')}</ThNotSortable>
            <ThSortable state={tableState} field="created">
              {t('created')}
            </ThSortable>
            <ThNotSortable>{null}</ThNotSortable>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>{rows}</Table.Tbody>
      </TableLayout>

      <Center mt="1rem">
        <Pagination
          value={tableState.page}
          onChange={tableState.setPage}
          total={1 + teamCount / tableState.pageSize}
          size="lg"
        />
      </Center>
    </>
  );
}
