import { ActionIcon, Button, Text, Tooltip, UnstyledButton } from '@mantine/core';
import { IconStar, IconStarFilled, IconX } from '@tabler/icons-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import PreloadLink from '@components/utils/link';
import { Time } from '@components/utils/datetime';
import { formatMatchInput1, formatMatchInput2 } from '@components/utils/match';
import { Category, MatchWithDetails, StageWithStageItems } from '@openapi';
import { getPublicTeams, nextMatchOf, teamIdsOfMatch } from './public_teams';
import classes from './public.module.css';

const CHANGED_EVENT = 'bracket-followed-team';

function storageKey(tournamentId: number) {
  return `bracket.follow.${tournamentId}`;
}

function readFollowed(tournamentId: number | null): number | null {
  if (tournamentId == null) return null;
  try {
    const value = localStorage.getItem(storageKey(tournamentId));
    return value != null && /^\d+$/.test(value) ? Number(value) : null;
  } catch {
    return null;
  }
}

/**
 * The team a visitor follows in this cup (remembered on this device only), kept in sync between
 * the parts of the page and other tabs.
 */
export function useFollowedTeam(
  tournamentId: number | null,
): [number | null, (teamId: number | null) => void] {
  const [teamId, setTeamId] = useState<number | null>(() => readFollowed(tournamentId));
  useEffect(() => {
    const refresh = () => setTeamId(readFollowed(tournamentId));
    refresh();
    window.addEventListener('storage', refresh);
    window.addEventListener(CHANGED_EVENT, refresh);
    return () => {
      window.removeEventListener('storage', refresh);
      window.removeEventListener(CHANGED_EVENT, refresh);
    };
  }, [tournamentId]);

  const follow = (id: number | null) => {
    if (tournamentId == null) return;
    try {
      if (id == null) localStorage.removeItem(storageKey(tournamentId));
      else localStorage.setItem(storageKey(tournamentId), `${id}`);
    } catch {
      // Not remembered (e.g. a private window), but followed for now
    }
    setTeamId(id);
    window.dispatchEvent(new Event(CHANGED_EVENT));
  };
  return [teamId, follow];
}

export function FollowButton({ tournamentId, teamId }: { tournamentId: number; teamId: number }) {
  const { t } = useTranslation();
  const [followed, follow] = useFollowedTeam(tournamentId);
  const following = followed === teamId;
  return (
    <Button
      variant={following ? 'light' : 'default'}
      color="yellow"
      leftSection={
        following ? (
          <IconStarFilled size={18} className={`${classes.followStar} ${classes.pop}`} />
        ) : (
          <IconStar size={18} />
        )
      }
      onClick={() => follow(following ? null : teamId)}
      aria-pressed={following}
    >
      {following ? t('follow_team_following') : t('follow_team_button')}
    </Button>
  );
}

/**
 * The followed team with its next match (time, pitch, opponent), on top of the public pages.
 * Nothing when no team is followed.
 */
export function FollowedTeamCard({
  tournamentId,
  endpoint,
  stages,
  categories,
  matchesLookup,
  stageItemsLookup,
}: {
  tournamentId: number;
  endpoint: string | null;
  stages: StageWithStageItems[];
  categories: Category[];
  matchesLookup: any;
  stageItemsLookup: any;
}) {
  const { t } = useTranslation();
  const [teamId, follow] = useFollowedTeam(tournamentId);
  const team = getPublicTeams(stages, categories).find((item) => item.team.id === teamId);
  if (teamId == null || team == null) return null;

  const matches: MatchWithDetails[] = Object.values(matchesLookup)
    .map((data: any) => data.match)
    .filter((match: MatchWithDetails) => teamIdsOfMatch(match).includes(teamId));
  const next = nextMatchOf(matches);
  const input1 = next?.stage_item_input1;
  const teamIsFirst = input1 != null && 'team' in input1 && input1.team?.id === teamId;
  const opponent =
    next == null
      ? null
      : teamIsFirst
        ? formatMatchInput2(t, stageItemsLookup, matchesLookup, next)
        : formatMatchInput1(t, stageItemsLookup, matchesLookup, next);

  return (
    <div className={`${classes.followCard} no-print`}>
      <IconStarFilled size={22} className={classes.followStar} />
      <UnstyledButton
        component={PreloadLink}
        href={`/tournaments/${endpoint}/dashboard/teams/${teamId}`}
        style={{ flex: 1, minWidth: 0 }}
      >
        <Text size="xs" c="dimmed" fw={700} tt="uppercase">
          {t('follow_team_card_label')}
        </Text>
        <Text fw={800} truncate>
          {team.team.name}
        </Text>
        <Text size="sm" truncate>
          {next != null && next.start_time != null ? (
            <>
              {t('next_match_badge')}: <Time datetime={next.start_time} />
              {next.court != null ? ` · ${next.court.name}` : ''}
              {opponent != null ? ` · ${t('follow_team_against', { team: opponent })}` : ''}
            </>
          ) : (
            t('follow_team_no_next_match')
          )}
        </Text>
      </UnstyledButton>
      <Tooltip label={t('follow_team_stop')}>
        <ActionIcon
          variant="subtle"
          color="gray"
          onClick={() => follow(null)}
          aria-label={t('follow_team_stop')}
        >
          <IconX size={18} />
        </ActionIcon>
      </Tooltip>
    </div>
  );
}
