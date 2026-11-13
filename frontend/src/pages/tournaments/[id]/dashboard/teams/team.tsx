import {
  Alert,
  Badge,
  Button,
  Card,
  Center,
  Container,
  Group,
  Stack,
  Text,
  Title,
} from '@mantine/core';
import { IconCalendarPlus, IconInfoCircle, IconQrcode } from '@tabler/icons-react';
import React from 'react';
import { useTranslation } from 'react-i18next';
import QRCode from 'react-qr-code';
import { useParams } from 'react-router';

import { DashboardFooter } from '@components/dashboard/footer';
import { DoubleHeader, getTournamentHeadTitle } from '@components/dashboard/layout';
import { getPublicTeams, nextMatchOf, teamIdsOfMatch } from '@components/dashboard/public_teams';
import { PrintButton } from '@components/print/print_button';
import { StandingsTableForStageItem } from '@components/tables/standings';
import { getStageItemIdsWithHiddenResults } from '@components/utils/category';
import PreloadLink from '@components/utils/link';
import { TableSkeletonTwoColumns } from '@components/utils/skeletons';
import { getBaseURL, setTitle } from '@components/utils/util';
import { MatchWithDetails, StageItemInputFinal, StageItemWithRounds } from '@openapi';
import KnockoutBracket from '@components/brackets/knockout_bracket';
import { FollowButton } from '@components/dashboard/follow_team';
import publicClasses from '@components/dashboard/public.module.css';
import { Time } from '@components/utils/datetime';
import { formatMatchInput1, formatMatchInput2 } from '@components/utils/match';
import { Schedule } from '@pages/tournaments/[id]/dashboard';
import { getCategories, getStagesLive } from '@services/adapter';
import { getTournamentResponseByEndpointName } from '@services/dashboard';
import { getMatchLookup, getStageItemLookup } from '@services/lookups';
import { teamCalendarUrl } from '@services/public_info';
import { getMatchOfficials, refereeNamesByMatch } from '@services/officials';

/** "1–2" or "1, 3": the placings in a group that lead to a playoff. */
function formatPlacings(placings: number[]) {
  const contiguous = placings.every(
    (placing, index) => index === 0 || placing === placings[index - 1] + 1,
  );
  return contiguous && placings.length > 1
    ? `${placings[0]}–${placings[placings.length - 1]}`
    : placings.join(', ');
}

/** Where the placings of a group lead: "Nr. 1–2 → A-sluttspill". */
function routesFromGroup(group: StageItemWithRounds, items: StageItemWithRounds[]) {
  return items
    .filter((item) => item.type === 'SINGLE_ELIMINATION')
    .map((playoff) => ({
      playoff,
      placings: [
        ...new Set(
          playoff.inputs
            .filter((input) => input.winner_from_stage_item_id === group.id)
            .map((input) => input.winner_position as number),
        ),
      ].sort((a, b) => a - b),
    }))
    .filter((route) => route.placings.length > 0)
    .sort((a, b) => a.placings[0] - b.placings[0]);
}

export default function DashboardTeamPage() {
  const { t } = useTranslation();
  const teamId = Number(useParams().team_id);
  const tournamentDataFull = getTournamentResponseByEndpointName();
  const tournamentValid = !React.isValidElement(tournamentDataFull);
  const swrStagesResponse = getStagesLive(tournamentValid ? tournamentDataFull.id : null);
  const referees = refereeNamesByMatch(
    getMatchOfficials(tournamentValid ? tournamentDataFull.id : null).data?.data ?? [],
  );
  const categories = getCategories(tournamentValid ? tournamentDataFull.id : null).data?.data ?? [];

  if (!tournamentValid) return tournamentDataFull;
  setTitle(getTournamentHeadTitle(tournamentDataFull));
  if (swrStagesResponse.data == null) return <TableSkeletonTwoColumns />;

  const stages = swrStagesResponse.data.data;
  const publicTeam = getPublicTeams(stages, categories).find(({ team }) => team.id === teamId);
  if (publicTeam == null) {
    return (
      <>
        <DoubleHeader tournamentData={tournamentDataFull} />
        <Container size="sm">
          <Alert color="gray" icon={<IconInfoCircle />}>
            {t('team_not_found_alert')}
          </Alert>
        </Container>
      </>
    );
  }

  const matchesLookup = getMatchLookup(swrStagesResponse);
  const stageItemsLookup = getStageItemLookup(swrStagesResponse);
  const teamMatches: MatchWithDetails[] = Object.values(matchesLookup)
    .map((data: any) => data.match)
    .filter((match: MatchWithDetails) => teamIdsOfMatch(match).includes(teamId));
  const nextMatch = nextMatchOf(teamMatches);
  const hiddenStageItemIds = getStageItemIdsWithHiddenResults(stages, categories);
  const groupsWithTeam = stages
    .flatMap((stage) => stage.stage_items)
    .filter((item) => !hiddenStageItemIds.has(item.id))
    .filter((item) => item.type === 'ROUND_ROBIN' || item.type === 'SWISS')
    .filter((item) =>
      item.inputs.some(
        (input) => 'team' in input && input.team != null && input.team.id === teamId,
      ),
    );
  const resultsHidden = publicTeam.category != null && !publicTeam.category.results_public;
  const allItems = stages.flatMap((stage) => stage.stage_items);
  // Playoffs the team is in, or plays in
  const playoffsWithTeam = allItems.filter(
    (item) =>
      item.type === 'SINGLE_ELIMINATION' &&
      (item.inputs.some((input) => input.team_id === teamId) ||
        item.rounds.some((round) =>
          round.matches.some((match) => teamIdsOfMatch(match as MatchWithDetails).includes(teamId)),
        )),
  );
  const nextInput1 = nextMatch?.stage_item_input1;
  const nextOpponent =
    nextMatch == null
      ? null
      : nextInput1 != null && 'team' in nextInput1 && nextInput1.team?.id === teamId
        ? formatMatchInput2(t, stageItemsLookup, matchesLookup, nextMatch)
        : formatMatchInput1(t, stageItemsLookup, matchesLookup, nextMatch);

  const endpoint = tournamentDataFull.dashboard_endpoint;
  const pageUrl = `${getBaseURL()}/tournaments/${endpoint}/dashboard/teams/${teamId}`;
  const calendarUrl = teamCalendarUrl(tournamentDataFull.id, teamId);

  return (
    <>
      <DoubleHeader tournamentData={tournamentDataFull} />
      <Container size="sm" px="md">
        <Stack>
          <Group justify="space-between" align="start">
            <Stack gap={4}>
              <Title>{publicTeam.team.name}</Title>
              {publicTeam.category != null ? (
                <Group gap="xs">
                  <Badge size="lg" variant="light">
                    {publicTeam.category.name}
                  </Badge>
                </Group>
              ) : null}
            </Stack>
          </Group>

          <Group className="no-print" gap="xs">
            <FollowButton tournamentId={tournamentDataFull.id} teamId={teamId} />
            <Button
              component="a"
              href={calendarUrl.replace(/^https?:/, 'webcal:')}
              leftSection={<IconCalendarPlus size={18} />}
            >
              {t('add_to_calendar_button')}
            </Button>
            <Button component="a" href={calendarUrl} variant="default">
              {t('download_calendar_button')}
            </Button>
            <Button
              component={PreloadLink}
              href={`/tournaments/${endpoint}/dashboard/poster?team=${teamId}`}
              variant="default"
              leftSection={<IconQrcode size={18} />}
            >
              {t('poster_button')}
            </Button>
            <PrintButton />
          </Group>

          {nextMatch != null && nextMatch.start_time != null ? (
            <div className={publicClasses.nextMatch}>
              <Text size="xs" fw={700} tt="uppercase" opacity={0.85}>
                {t('next_match_badge')}
              </Text>
              <Group align="baseline" gap="md" wrap="wrap">
                <span className={publicClasses.nextTime}>
                  <Time datetime={nextMatch.start_time} />
                </span>
                {nextMatch.court != null ? (
                  <Text size="xl" fw={700}>
                    {nextMatch.court.name}
                  </Text>
                ) : null}
              </Group>
              {nextOpponent != null ? (
                <Text size="lg" mt={4}>
                  {t('follow_team_against', { team: nextOpponent })}
                </Text>
              ) : null}
            </div>
          ) : null}

          {!resultsHidden &&
          groupsWithTeam.some((group) => routesFromGroup(group, allItems).length > 0) ? (
            <Stack gap="xs">
              <Title order={4}>{t('team_path_title')}</Title>
              {groupsWithTeam.map((group) => {
                const position = group.inputs.find((input) => input.team_id === teamId)?.position;
                return (
                  <div key={group.id} className={publicClasses.path}>
                    <span className={publicClasses.pathStep} data-current>
                      {group.name}
                      {position != null ? ` · ${t('team_path_position', { position })}` : ''}
                    </span>
                    {routesFromGroup(group, allItems).map((route) => (
                      <span
                        key={route.playoff.id}
                        className={publicClasses.pathStep}
                        data-current={playoffsWithTeam.some((item) => item.id === route.playoff.id)}
                      >
                        {t('team_path_route', {
                          placings: formatPlacings(route.placings),
                          playoff: route.playoff.name,
                        })}
                      </span>
                    ))}
                  </div>
                );
              })}
            </Stack>
          ) : null}

          {playoffsWithTeam.map((item) => (
            <Stack key={item.id} gap="xs">
              <Title order={4}>{item.name}</Title>
              <KnockoutBracket
                stageItem={item}
                stageItemsLookup={stageItemsLookup}
                matchesLookup={matchesLookup}
                highlightTeamId={teamId}
              />
            </Stack>
          ))}

          {teamMatches.length < 1 ? (
            <Alert color="gray" icon={<IconInfoCircle />}>
              {t('team_no_matches_alert')}
            </Alert>
          ) : (
            <Schedule
              t={t}
              referees={referees}
              matchesLookup={matchesLookup}
              stageItemsLookup={stageItemsLookup}
              stageItemIdsWithHiddenResults={hiddenStageItemIds}
              includeStageItem={() => true}
              includeMatch={(match) => teamIdsOfMatch(match).includes(teamId)}
              highlightMatchId={nextMatch?.id ?? null}
            />
          )}

          {resultsHidden ? (
            <Alert color="gray" icon={<IconInfoCircle />}>
              {t('standings_hidden_alert')}
            </Alert>
          ) : (
            groupsWithTeam.map((item) => (
              <Stack key={item.id} gap="xs">
                <Title order={4}>{item.name}</Title>
                <StandingsTableForStageItem
                  teams_with_inputs={
                    item.inputs.filter(
                      (input) => 'team' in input && input.team != null,
                    ) as StageItemInputFinal[]
                  }
                  stageItem={item}
                  stageItemsLookup={stageItemsLookup}
                  fontSizeInPixels={16}
                  maxTeamsToDisplay={100}
                  highlightTeamId={teamId}
                />
              </Stack>
            ))
          )}

          <Card withBorder className="no-print" mt="md">
            <Center>
              <Stack align="center" gap="xs">
                <div style={{ background: 'white', padding: 12, borderRadius: 8 }}>
                  <QRCode value={pageUrl} size={140} />
                </div>
                <Text size="sm" c="dimmed" ta="center">
                  {t('team_page_qr_description')}
                </Text>
              </Stack>
            </Center>
          </Card>
        </Stack>
      </Container>
      <DashboardFooter />
    </>
  );
}
