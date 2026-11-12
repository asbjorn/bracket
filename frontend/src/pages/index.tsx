import { Grid, Select } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { PageTitle } from '@components/help/help_button';
import TournamentsCardTable from '@components/card_tables/tournaments';
import TournamentModal from '@components/modals/tournament_modal';
import { TournamentFilter } from '@components/utils/tournament';
import { capitalize } from '@components/utils/util';
import { checkForAuthError, getTournaments } from '@services/adapter';
import Layout from './_layout';
import classes from './index.module.css';

export default function HomePage() {
  const { t } = useTranslation();
  const [filter, setFilter] = useState<TournamentFilter>('OPEN');

  const swrTournamentsResponse = getTournaments(filter);
  checkForAuthError(swrTournamentsResponse);

  return (
    <Layout>
      <Grid>
        <Grid.Col span="auto">
          <PageTitle help="tournaments">{capitalize(t('tournaments_title'))}</PageTitle>
        </Grid.Col>
        <Grid.Col span="content" className={classes.fullWithMobile}>
          <Select
            size="md"
            placeholder={t('tournament_filter_placeholder')}
            data={[
              { label: t('tournament_filter_all'), value: 'ALL' },
              { label: t('archived_label'), value: 'ARCHIVED' },
              { label: t('tournament_filter_open'), value: 'OPEN' },
            ]}
            allowDeselect={false}
            value={filter}
            // @ts-ignore
            onChange={(f: TournamentFilter) => setFilter(f)}
          />
        </Grid.Col>
        <Grid.Col span="content" className={classes.fullWithMobile}>
          <TournamentModal swrTournamentsResponse={swrTournamentsResponse} />
        </Grid.Col>
      </Grid>
      <TournamentsCardTable swrTournamentsResponse={swrTournamentsResponse} />
    </Layout>
  );
}
