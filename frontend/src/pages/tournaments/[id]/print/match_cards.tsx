import { Badge, Box, Group, Select, SimpleGrid, Stack, Text, Title } from '@mantine/core';
import dayjs from 'dayjs';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { PrintButton } from '@components/print/print_button';
import {
  CategoryFilterSelect,
  getStageItemCategoryLookup,
  useCategoryFilter,
} from '@components/utils/category';
import { Time } from '@components/utils/datetime';
import { formatMatchInput1, formatMatchInput2 } from '@components/utils/match';
import { getTournamentIdFromRouter } from '@components/utils/util';
import { MatchWithDetails, StageItemWithRounds } from '@openapi';
import TournamentLayout from '@pages/tournaments/_tournament_layout';
import { getCategories, getCourts, getStages } from '@services/adapter';
import { getDiscipline } from '@services/discipline';
import { getMatchOfficials, refereeNamesByMatch } from '@services/officials';
import { getMatchLookup, getStageItemLookup } from '@services/lookups';

function ScoreBox() {
  return (
    <Box
      w="3.2rem"
      h="2.6rem"
      style={{ border: '2px solid black', borderRadius: 6, flexShrink: 0 }}
    />
  );
}

function SignatureLine({ label }: { label: string }) {
  return (
    <Stack gap={0} style={{ flex: 1 }}>
      <Box h="1.6rem" style={{ borderBottom: '1px solid black' }} />
      <Text size="xs">{label}</Text>
    </Stack>
  );
}

/** A card for the referee or the secretariat: teams, time, court and boxes for the score. */
function MatchCard({
  match,
  stageItem,
  categoryName,
  team1,
  team2,
  referee,
  suspended,
}: {
  match: MatchWithDetails;
  stageItem: StageItemWithRounds;
  categoryName: string | null;
  team1: string;
  team2: string;
  referee: string | null;
  // Players who sit out this match (suspension)
  suspended: string[];
}) {
  const { t } = useTranslation();
  return (
    <Box
      className="print-keep-together"
      p="md"
      style={{ border: '1px solid black', borderRadius: 8, background: 'white', color: 'black' }}
    >
      <Stack gap="sm">
        <Group justify="space-between">
          <Group gap="xs">
            {categoryName != null ? <Badge color="dark">{categoryName}</Badge> : null}
            <Text fw={600}>{stageItem.name}</Text>
          </Group>
          <Text fw={700}>
            {match.start_time != null ? <Time datetime={match.start_time} /> : '–'}
            {' · '}
            {match.court?.name ?? t('no_court_label')}
          </Text>
        </Group>
        {[team1, team2].map((team, index) => (
          <Group key={index} justify="space-between" wrap="nowrap">
            <Text size="xl" fw={600}>
              {team}
            </Text>
            <ScoreBox />
          </Group>
        ))}
        {referee != null ? (
          <Text size="sm" c="dark">
            {t('referee_label')}: <b>{referee}</b>
          </Text>
        ) : null}
        {suspended.length > 0 ? (
          <Text size="sm" c="dark">
            {t('suspended_players_title')}: <b>{suspended.join(', ')}</b>
          </Text>
        ) : null}
        <Text size="xs" c="dark">
          #{match.id} · {t('match_card_notes_label')}
        </Text>
        <Box h="2.4rem" style={{ borderBottom: '1px dashed black' }} />
        <Group gap="lg">
          <SignatureLine label={t('referee_signature_label')} />
          <SignatureLine label={t('team_leader_signature_label')} />
        </Group>
      </Stack>
    </Box>
  );
}

export default function MatchCardsPage() {
  const { t } = useTranslation();
  const { tournamentData } = getTournamentIdFromRouter();
  const swrStagesResponse = getStages(tournamentData.id);
  const courts = getCourts(tournamentData.id).data?.data ?? [];
  const referees = refereeNamesByMatch(getMatchOfficials(tournamentData.id).data?.data ?? []);
  const discipline = getDiscipline(tournamentData.id).data?.data;
  const categories = getCategories(tournamentData.id).data?.data ?? [];
  const { filterValue, setFilterValue, filterCategoryId } = useCategoryFilter(categories);
  const [courtId, setCourtId] = useState<string | null>(null);
  const [day, setDay] = useState<string | null>(null);

  if (swrStagesResponse.data == null) {
    return <TournamentLayout tournament_id={tournamentData.id}>{null}</TournamentLayout>;
  }

  const stages = swrStagesResponse.data.data;
  const stageItemCategories = getStageItemCategoryLookup(stages);
  const matchesLookup = getMatchLookup(swrStagesResponse);
  const stageItemsLookup = getStageItemLookup(swrStagesResponse);
  const all = Object.values(matchesLookup)
    .filter((data: any) => data.match.start_time != null)
    .sort(
      (a: any, b: any) =>
        a.match.start_time.localeCompare(b.match.start_time) ||
        (a.match.court?.name ?? '').localeCompare(b.match.court?.name ?? ''),
    );
  const days = [
    ...new Set(all.map((data: any) => dayjs(data.match.start_time).format('YYYY-MM-DD'))),
  ];
  const selected = all
    .filter(
      (data: any) =>
        filterCategoryId === undefined ||
        stageItemCategories[data.stageItem.id] === filterCategoryId,
    )
    .filter((data: any) => courtId == null || `${data.match.court_id}` === courtId)
    .filter(
      (data: any) => day == null || dayjs(data.match.start_time).format('YYYY-MM-DD') === day,
    );

  return (
    <TournamentLayout tournament_id={tournamentData.id}>
      <Stack>
        <Group justify="space-between" className="no-print">
          <Title>{t('match_cards_title')}</Title>
          <PrintButton label={t('print_match_cards_button', { count: selected.length })} />
        </Group>
        <Group className="no-print" align="end">
          <CategoryFilterSelect
            categories={categories}
            value={filterValue}
            setValue={setFilterValue}
          />
          <Select
            label={t('court_label')}
            placeholder={t('all_courts_button')}
            data={courts.map((court) => ({ value: `${court.id}`, label: court.name }))}
            value={courtId}
            onChange={setCourtId}
            clearable
          />
          {days.length > 1 ? (
            <Select
              label={t('day_label')}
              placeholder={t('all_days_label')}
              data={days.map((value) => ({
                value,
                label: dayjs(value).format('dddd D. MMMM'),
              }))}
              value={day}
              onChange={setDay}
              clearable
            />
          ) : null}
        </Group>
        <Text size="sm" c="dimmed" className="no-print">
          {t('match_cards_description')}
        </Text>
        <SimpleGrid cols={2} spacing="md" verticalSpacing="md">
          {selected.map((data: any) => {
            const categoryId = stageItemCategories[data.stageItem.id];
            return (
              <MatchCard
                key={data.match.id}
                match={data.match}
                stageItem={data.stageItem}
                categoryName={categories.find((c) => c.id === categoryId)?.name ?? null}
                team1={formatMatchInput1(t, stageItemsLookup, matchesLookup, data.match)}
                team2={formatMatchInput2(t, stageItemsLookup, matchesLookup, data.match)}
                referee={referees[data.match.id] ?? null}
                suspended={(discipline?.suspensions ?? [])
                  .filter((suspension) => suspension.match_ids.includes(data.match.id))
                  .map((suspension) => suspension.player_name)}
              />
            );
          })}
        </SimpleGrid>
      </Stack>
    </TournamentLayout>
  );
}
