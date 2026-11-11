import { Badge, Center, Group, Pagination, Switch, Table } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { SWRResponse } from 'swr';

import DeleteButton from '@components/buttons/delete';
import PlayerList from '@components/info/player_list';
import TeamUpdateModal from '@components/modals/team_update_modal';
import { NoContent } from '@components/no_content/empty_table_info';
import { DateTime } from '@components/utils/datetime';
import RequestErrorAlert from '@components/utils/error_alert';
import { TableSkeletonSingleColumn } from '@components/utils/skeletons';
import { TournamentMinimal } from '@components/utils/tournament';
import { Category, FullTeamWithPlayers, TeamsWithPlayersResponse } from '@openapi';
import { deleteTeam, setTeamCheckedIn } from '@services/team';
import WithdrawButton from '@components/buttons/withdraw_team';
import TableLayout, { TableState, ThNotSortable, ThSortable, sortTableEntries } from './table';

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
      <Table.Tr key={team.id}>
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
            {team.withdrawn ? (
              <Badge color="red" variant="outline">
                {t('withdrawn_badge')}
              </Badge>
            ) : null}
          </Group>
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
          <TeamUpdateModal
            tournament_id={tournamentData.id}
            team={team}
            swrTeamsResponse={swrTeamsResponse}
          />
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

  if (rows.length < 1) return <NoContent title={t('no_teams_title')} />;

  return (
    <>
      <TableLayout miw={850}>
        <Table.Thead>
          <Table.Tr>
            <ThSortable state={tableState} field="active">
              {t('status')}
            </ThSortable>
            <ThSortable state={tableState} field="name">
              {t('name_table_header')}
            </ThSortable>
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
