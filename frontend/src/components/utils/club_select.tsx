import { Select } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { getParticipatingClubs, requestSucceeded } from '@services/adapter';
import { createParticipatingClub } from '@services/participating_clubs';

const NEW_CLUB = '__new__';

/**
 * Chooses the participating club of a team. Typing a name that doesn't exist yet offers
 * "+ Ny klubb «name»", which creates the club right away. `value` is the club id as a string.
 */
export function ClubSelect({
  tournamentId,
  value,
  onChange,
}: {
  tournamentId: number;
  value: string | null;
  onChange: (value: string | null) => void;
}) {
  const { t } = useTranslation();
  const swrClubsResponse = getParticipatingClubs(tournamentId);
  const clubs = swrClubsResponse.data?.data ?? [];
  const [search, setSearch] = useState('');

  const typed = search.trim();
  const exists = clubs.some((club) => club.name.toLowerCase() === typed.toLowerCase());
  const data = [
    ...clubs.map((club) => ({ value: `${club.id}`, label: club.name })),
    ...(typed !== '' && !exists
      ? [{ value: NEW_CLUB, label: t('club_select_create', { name: typed }) }]
      : []),
  ];

  return (
    <Select
      mt="md"
      label={t('club_name_input_label')}
      description={t('club_name_input_description')}
      placeholder={t('participating_club_select_placeholder')}
      data={data}
      value={value}
      searchable
      clearable
      searchValue={search}
      onSearchChange={setSearch}
      nothingFoundMessage={t('club_select_nothing_found')}
      onChange={async (selected) => {
        if (selected !== NEW_CLUB) {
          onChange(selected);
          return;
        }
        const response = await createParticipatingClub(tournamentId, {
          name: typed,
          new_teams: [],
          team_ids: [],
        });
        if (requestSucceeded(response) && 'data' in response) {
          await swrClubsResponse.mutate();
          onChange(`${response.data.data}`);
        }
      }}
    />
  );
}
