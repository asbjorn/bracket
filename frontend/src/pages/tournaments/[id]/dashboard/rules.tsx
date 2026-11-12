import { Container, Group, Paper, Stack, Title } from '@mantine/core';
import React from 'react';
import { useTranslation } from 'react-i18next';

import { DashboardFooter } from '@components/dashboard/footer';
import { DoubleHeader, getTournamentHeadTitle } from '@components/dashboard/layout';
import { NoContent } from '@components/no_content/empty_table_info';
import { PrintButton } from '@components/print/print_button';
import { MarkdownView } from '@components/utils/markdown';
import { TableSkeletonTwoColumns } from '@components/utils/skeletons';
import { setTitle } from '@components/utils/util';
import { getTournamentResponseByEndpointName } from '@services/dashboard';
import { getRules } from '@services/public_info';

export default function DashboardRulesPage() {
  const { t } = useTranslation();
  const tournamentDataFull = getTournamentResponseByEndpointName();
  const tournamentValid = !React.isValidElement(tournamentDataFull);
  const swrRulesResponse = getRules(tournamentValid ? tournamentDataFull.id : null);

  if (!tournamentValid) return tournamentDataFull;
  setTitle(getTournamentHeadTitle(tournamentDataFull));
  if (swrRulesResponse.data == null) return <TableSkeletonTwoColumns />;
  const text = swrRulesResponse.data.data.text;

  return (
    <>
      <DoubleHeader tournamentData={tournamentDataFull} />
      <Container size="sm" px="md">
        <Stack>
          <Group justify="space-between">
            <Title>{t('rules_title')}</Title>
            {text !== '' ? <PrintButton /> : null}
          </Group>
          {text === '' ? (
            <NoContent title={t('no_rules_title')} description="" />
          ) : (
            <Paper withBorder p="lg" radius="md" className="markdown-rules">
              <MarkdownView text={text} />
            </Paper>
          )}
        </Stack>
      </Container>
      <DashboardFooter />
    </>
  );
}
