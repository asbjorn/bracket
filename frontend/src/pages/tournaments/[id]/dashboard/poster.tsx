import { Center, Group, Stack, Text, Title } from '@mantine/core';
import { parseAsInteger, parseAsString, useQueryState } from 'nuqs';
import React from 'react';
import { useTranslation } from 'react-i18next';
import QRCode from 'react-qr-code';

import { getPublicTeams } from '@components/dashboard/public_teams';
import { PrintButton } from '@components/print/print_button';
import { valueToCategoryId } from '@components/utils/category';
import { TableSkeletonTwoColumns } from '@components/utils/skeletons';
import { getBaseURL, setTitle } from '@components/utils/util';
import { getCategories, getStagesLive } from '@services/adapter';
import { getTournamentResponseByEndpointName } from '@services/dashboard';

/**
 * A poster to print and hang up: a large QR code to the schedule of a team (`?team=`) or a
 * class (`?category=`), or of the whole cup.
 */
export default function DashboardPosterPage() {
  const { t } = useTranslation();
  const tournamentDataFull = getTournamentResponseByEndpointName();
  const tournamentValid = !React.isValidElement(tournamentDataFull);
  const swrStagesResponse = getStagesLive(tournamentValid ? tournamentDataFull.id : null);
  const categories = getCategories(tournamentValid ? tournamentDataFull.id : null).data?.data ?? [];
  const [teamId] = useQueryState('team', parseAsInteger);
  const [category] = useQueryState('category', parseAsString);

  if (!tournamentValid) return tournamentDataFull;
  setTitle(tournamentDataFull.name);
  if (swrStagesResponse.data == null) return <TableSkeletonTwoColumns />;

  const base = `${getBaseURL()}/tournaments/${tournamentDataFull.dashboard_endpoint}/dashboard`;
  const team = getPublicTeams(swrStagesResponse.data.data, categories).find(
    (item) => item.team.id === teamId,
  );
  const categoryId = category != null ? valueToCategoryId(category) : null;
  const categoryName = categories.find((c) => c.id === categoryId)?.name;

  let title = tournamentDataFull.name;
  let url = base;
  if (team != null) {
    title = team.team.name;
    url = `${base}/teams/${team.team.id}`;
  } else if (categoryName != null && category != null) {
    title = categoryName;
    url = `${base}?category=${encodeURIComponent(category)}`;
  }

  return (
    <Center mih="100vh" p="xl" bg="white" c="black">
      <Stack align="center" gap="xl" maw="40rem">
        <Group className="no-print">
          <PrintButton />
        </Group>
        <Text size="xl" ta="center">
          {tournamentDataFull.name}
        </Text>
        <Title ta="center" style={{ fontSize: '3.5rem', lineHeight: 1.1 }}>
          {title}
        </Title>
        <QRCode value={url} size={360} style={{ width: '100%', height: 'auto', maxWidth: 360 }} />
        <Title order={2} ta="center">
          {t('poster_scan_text')}
        </Title>
        <Text ta="center" style={{ wordBreak: 'break-all' }}>
          {url}
        </Text>
      </Stack>
    </Center>
  );
}
