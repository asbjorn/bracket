import {
  Accordion,
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Center,
  Chip,
  Container,
  Drawer,
  Group,
  Loader,
  SegmentedControl,
  Stack,
  Text,
  Textarea,
  Title,
  UnstyledButton,
} from '@mantine/core';
import { showNotification } from '@mantine/notifications';
import {
  IconAlertTriangle,
  IconCheck,
  IconClockPause,
  IconMinus,
  IconPlayerPlay,
  IconPlus,
  IconUser,
  IconUserCheck,
  IconUserShield,
  IconWifiOff,
} from '@tabler/icons-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router';

import { CardsEditor, SuspendedAlert } from '@components/discipline/cards_editor';
import { Time } from '@components/utils/datetime';
import { capitalize } from '@components/utils/util';
import { MatchResultType, ScoreEntryMatch } from '@openapi';
import { requestSucceeded } from '@services/adapter';
import { createCardAtPitch, deleteCardAtPitch } from '@services/discipline';
import {
  checkInAtPitch,
  enterResult,
  enterWalkover,
  getScoreEntry,
  setStartedAtPitch,
  isLinkRefused,
  reportFromPitch,
} from '@services/score_links';

const RESULT_TYPES: MatchResultType[] = ['NORMAL', 'EXTRA_TIME', 'PENALTIES', 'WALKOVER'];
const DELAY_CHOICES = [5, 10, 15, 30];

function teamsOf(match: ScoreEntryMatch) {
  return [
    { id: match.team1_id as number, name: match.team1_name ?? '?' },
    { id: match.team2_id as number, name: match.team2_name ?? '?' },
  ];
}

function canBeEntered(match: ScoreEntryMatch) {
  return match.team1_id != null && match.team2_id != null;
}

/** A large +/- stepper, easy to use with a thumb on a phone at the side of the pitch. */
function ScoreStepper({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
}) {
  const { t } = useTranslation();
  return (
    <Group justify="space-between" wrap="nowrap">
      <Text size="lg" fw={600} style={{ flex: 1, minWidth: 0 }} truncate>
        {label}
      </Text>
      <Group gap="sm" wrap="nowrap">
        <ActionIcon
          size={56}
          radius="xl"
          variant="light"
          aria-label={t('score_decrease_label', { team: label })}
          disabled={value < 1}
          onClick={() => onChange(value - 1)}
        >
          <IconMinus size={28} />
        </ActionIcon>
        <Text fz={40} fw={700} w="3rem" ta="center" aria-live="polite">
          {value}
        </Text>
        <ActionIcon
          size={56}
          radius="xl"
          variant="filled"
          aria-label={t('score_increase_label', { team: label })}
          onClick={() => onChange(Math.min(99, value + 1))}
        >
          <IconPlus size={28} />
        </ActionIcon>
      </Group>
    </Group>
  );
}

function MatchHeader({ match }: { match: ScoreEntryMatch }) {
  return (
    <Group gap="xs">
      {match.start_time != null ? (
        <Badge size="lg" variant="filled" color="indigo">
          <Time datetime={match.start_time} />
        </Badge>
      ) : null}
      {match.court_name != null ? <Badge variant="light">{match.court_name}</Badge> : null}
      {match.category_name != null ? (
        <Badge variant="light" color="grape">
          {match.category_name}
        </Badge>
      ) : null}
      <Badge variant="outline" color="gray">
        {match.stage_item_name}
      </Badge>
      {match.referee_name != null ? (
        <Badge variant="light" color="yellow" leftSection={<IconUserShield size={12} />}>
          {match.referee_name}
          {match.assistant_names.length > 0 ? ` + ${match.assistant_names.join(', ')}` : ''}
        </Badge>
      ) : null}
    </Group>
  );
}

/** Who has arrived: tap to check a team in (or out again). */
function CheckInRow({
  token,
  match,
  onChanged,
}: {
  token: string;
  match: ScoreEntryMatch;
  onChanged: () => Promise<void>;
}) {
  const { t } = useTranslation();
  const teams = [
    { id: match.team1_id, name: match.team1_name, checkedIn: match.team1_checked_in },
    { id: match.team2_id, name: match.team2_name, checkedIn: match.team2_checked_in },
  ];
  // The team name is the button: grey = not here yet, green with a check = checked in
  return (
    <Stack gap={4}>
      <Text size="xs" c="dimmed">
        {t('check_in_question')}
      </Text>
      <Group grow>
        {teams.map((team) =>
          team.id != null ? (
            <Button
              key={team.id}
              variant={team.checkedIn ? 'light' : 'default'}
              color={team.checkedIn ? 'green' : 'gray'}
              leftSection={team.checkedIn ? <IconUserCheck size={18} /> : <IconUser size={18} />}
              aria-pressed={team.checkedIn}
              title={
                team.checkedIn ? t('checked_in_label') : t('check_in_button', { team: team.name })
              }
              onClick={async () => {
                const teamId = team.id as number;
                await checkInAtPitch(token, teamId, !team.checkedIn);
                await onChanged();
              }}
            >
              <Text size="sm" truncate>
                {team.name}
              </Text>
            </Button>
          ) : null,
        )}
      </Group>
    </Stack>
  );
}

function ResultForm({
  token,
  match,
  walkoverGoals,
  onSaved,
}: {
  token: string;
  match: ScoreEntryMatch;
  walkoverGoals: number;
  onSaved: () => Promise<void>;
}) {
  const { t } = useTranslation();
  const [score1, setScore1] = useState(match.score1);
  const [score2, setScore2] = useState(match.score2);
  const [resultType, setResultType] = useState<MatchResultType>(match.result_type);
  const [penalties1, setPenalties1] = useState(match.penalties1 ?? 0);
  const [penalties2, setPenalties2] = useState(match.penalties2 ?? 0);
  const [saving, setSaving] = useState(false);
  // A walkover needs a second tap, naming the winner: it can't be saved by accident
  const [walkoverWinner, setWalkoverWinner] = useState<number | null>(null);
  const team1 = match.team1_name ?? '?';
  const team2 = match.team2_name ?? '?';

  // Another match was chosen, or the result was changed elsewhere
  useEffect(() => {
    setScore1(match.score1);
    setScore2(match.score2);
    setResultType(match.result_type);
    setPenalties1(match.penalties1 ?? 0);
    setPenalties2(match.penalties2 ?? 0);
    setWalkoverWinner(null);
  }, [match.id, match.score1, match.score2, match.result_type]);

  async function markPlayed(played: boolean) {
    setSaving(true);
    const response = await enterResult(token, match.id, {
      score1: 0,
      score2: 0,
      result_type: 'NORMAL',
      penalties1: null,
      penalties2: null,
      played,
    });
    setSaving(false);
    if (requestSucceeded(response)) {
      showNotification({
        color: 'green',
        icon: <IconCheck />,
        title: t('score_saved_title'),
        message: played ? t('score_marked_played') : t('score_marked_not_played'),
      });
      await onSaved();
    }
  }

  let problem: string | null = null;
  if (resultType === 'PENALTIES' && score1 !== score2) problem = t('score_problem_penalties_equal');
  if (resultType === 'PENALTIES' && score1 === score2 && penalties1 === penalties2)
    problem = t('score_problem_penalties_winner');

  const resultTypeControl = (
    <SegmentedControl
      fullWidth
      size="md"
      data={RESULT_TYPES.map((type) => ({
        value: type,
        label: t(`result_type_short_${type.toLowerCase()}`),
      }))}
      value={resultType}
      onChange={(value) => setResultType(value as MatchResultType)}
    />
  );

  // Children's football: no score is kept for the public, the pitch only marks the match played
  if (!match.results_public && resultType !== 'WALKOVER') {
    return (
      <Stack>
        <Text size="sm" c="dimmed">
          {t('score_hidden_results_description')}
        </Text>
        {match.played ? (
          <>
            <Alert color="green" icon={<IconCheck />}>
              {t('score_marked_played')}
            </Alert>
            <Button variant="default" loading={saving} onClick={() => markPlayed(false)}>
              {t('score_not_played_button')}
            </Button>
          </>
        ) : (
          <Button
            size="xl"
            color="green"
            fullWidth
            loading={saving}
            leftSection={<IconCheck size={26} />}
            onClick={() => markPlayed(true)}
          >
            {t('score_played_button')}
          </Button>
        )}
        <Button variant="subtle" color="gray" onClick={() => setResultType('WALKOVER')}>
          {t('score_walkover_link')}
        </Button>
      </Stack>
    );
  }

  if (resultType === 'WALKOVER') {
    // The team that showed up wins by the tournament's walkover score
    return (
      <Stack>
        {resultTypeControl}
        <Text size="sm" c="dimmed">
          {t('score_walkover_description', { goals: walkoverGoals })}
        </Text>
        {[
          { id: match.team1_id, name: team1 },
          { id: match.team2_id, name: team2 },
        ].map((winner) => (
          <Button
            key={winner.id}
            size="lg"
            color="green"
            variant={walkoverWinner === winner.id ? 'filled' : 'light'}
            fullWidth
            loading={saving}
            onClick={async () => {
              if (walkoverWinner !== winner.id) {
                setWalkoverWinner(winner.id);
                return;
              }
              setSaving(true);
              const response = await enterWalkover(token, match.id, winner.id as number);
              setSaving(false);
              if (requestSucceeded(response)) {
                showNotification({
                  color: 'green',
                  icon: <IconCheck />,
                  title: t('score_saved_title'),
                  message: t('score_walkover_saved', { team: winner.name }),
                });
                await onSaved();
              }
            }}
          >
            {walkoverWinner === winner.id
              ? t('score_walkover_confirm_button', { team: winner.name })
              : t('score_walkover_winner_button', { team: winner.name })}
          </Button>
        ))}
        {!match.results_public ? (
          <Button variant="subtle" color="gray" onClick={() => setResultType('NORMAL')}>
            {t('cancel_button')}
          </Button>
        ) : null}
      </Stack>
    );
  }

  return (
    <Stack>
      <ScoreStepper label={team1} value={score1} onChange={setScore1} />
      <ScoreStepper label={team2} value={score2} onChange={setScore2} />
      {resultTypeControl}
      {resultType === 'PENALTIES' ? (
        <Card withBorder>
          <Text size="sm" c="dimmed" mb="xs">
            {t('score_penalties_title')}
          </Text>
          <Stack>
            <ScoreStepper label={team1} value={penalties1} onChange={setPenalties1} />
            <ScoreStepper label={team2} value={penalties2} onChange={setPenalties2} />
          </Stack>
        </Card>
      ) : null}
      {problem != null ? (
        <Alert color="orange" icon={<IconAlertTriangle />}>
          {problem}
        </Alert>
      ) : null}
      <Button
        size="xl"
        color="green"
        fullWidth
        loading={saving}
        disabled={problem != null}
        leftSection={<IconCheck size={26} />}
        onClick={async () => {
          setSaving(true);
          const response = await enterResult(token, match.id, {
            score1,
            score2,
            result_type: resultType,
            penalties1: resultType === 'PENALTIES' ? penalties1 : null,
            penalties2: resultType === 'PENALTIES' ? penalties2 : null,
            played: true,
          });
          setSaving(false);
          if (requestSucceeded(response)) {
            showNotification({
              color: 'green',
              icon: <IconCheck />,
              title: t('score_saved_title'),
              message: `${team1} ${score1} – ${score2} ${team2}`,
            });
            await onSaved();
          }
        }}
      >
        {match.played ? t('score_update_button') : t('score_save_button')}
      </Button>
    </Stack>
  );
}

function MatchRow({
  match,
  selected,
  onClick,
}: {
  match: ScoreEntryMatch;
  selected: boolean;
  onClick: () => void;
}) {
  const { t } = useTranslation();
  return (
    <UnstyledButton onClick={onClick} w="100%">
      <Card withBorder padding="sm" bg={selected ? 'var(--mantine-color-indigo-light)' : undefined}>
        <Group justify="space-between" wrap="nowrap">
          <Stack gap={0} style={{ minWidth: 0 }}>
            <Text size="sm" c="dimmed">
              {match.start_time != null ? <Time datetime={match.start_time} /> : null}
              {match.court_name != null ? ` · ${match.court_name}` : ''}
              {match.category_name != null ? ` · ${match.category_name}` : ''}
            </Text>
            <Text fw={500} truncate c={canBeEntered(match) ? undefined : 'dimmed'}>
              {match.team1_name == null && match.team2_name == null
                ? capitalize(t('score_no_team_yet'))
                : `${match.team1_name ?? '?'} – ${match.team2_name ?? '?'}`}
            </Text>
          </Stack>
          {match.played ? (
            <Badge size="lg" color="green" variant="light">
              {match.score1}–{match.score2}
            </Badge>
          ) : null}
        </Group>
      </Card>
    </UnstyledButton>
  );
}

function DelayDrawer({
  token,
  opened,
  onClose,
}: {
  token: string;
  opened: boolean;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [minutes, setMinutes] = useState<string | null>(null);
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);
  return (
    <Drawer
      opened={opened}
      onClose={onClose}
      position="bottom"
      size="auto"
      title={t('report_delay_title')}
    >
      <Stack pb="md">
        <Text size="sm" c="dimmed">
          {t('report_delay_description')}
        </Text>
        <Chip.Group multiple={false} value={minutes} onChange={setMinutes}>
          <Group>
            {DELAY_CHOICES.map((choice) => (
              <Chip key={choice} value={`${choice}`} size="lg">
                {t('minutes_short', { minutes: choice })}
              </Chip>
            ))}
          </Group>
        </Chip.Group>
        <Textarea
          label={t('report_message_label')}
          value={message}
          maxLength={300}
          autosize
          minRows={2}
          onChange={(event) => setMessage(event.currentTarget.value)}
        />
        <Button
          size="lg"
          loading={sending}
          disabled={minutes == null && message.trim() === ''}
          onClick={async () => {
            setSending(true);
            const response = await reportFromPitch(token, {
              delay_minutes: minutes != null ? +minutes : null,
              message: message.trim(),
            });
            setSending(false);
            if (requestSucceeded(response)) {
              showNotification({ color: 'green', message: t('report_sent_message') });
              setMinutes(null);
              setMessage('');
              onClose();
            }
          }}
        >
          {t('report_send_button')}
        </Button>
      </Stack>
    </Drawer>
  );
}

export default function ScoreEntryPage() {
  const { t } = useTranslation();
  const { token = '' } = useParams();
  const swrView = getScoreEntry(token);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [delayOpened, setDelayOpened] = useState(false);
  const [showPlayed, setShowPlayed] = useState(false);

  // Only a link the server refuses ends the page. A failed refresh keeps the last data on
  // screen, so a score being typed isn't lost when the connection drops for a moment.
  if (swrView.data == null && swrView.error != null && isLinkRefused(swrView.error)) {
    return (
      <Container size="xs" py="xl">
        <Alert color="red" icon={<IconAlertTriangle />} title={t('score_link_invalid_title')}>
          {swrView.error?.response?.data?.detail ?? t('score_link_invalid_description')}
        </Alert>
      </Container>
    );
  }
  if (swrView.data == null) {
    return (
      <Center h="60vh">
        <Stack align="center">
          <Loader />
          {swrView.error != null ? <Text c="dimmed">{t('score_connection_retrying')}</Text> : null}
        </Stack>
      </Center>
    );
  }

  const view = swrView.data.data;
  const unplayed = view.matches.filter((m) => !m.played);
  const played = view.matches.filter((m) => m.played).reverse();
  // The current match: the first one still to be played whose teams are known
  const current = unplayed.find(canBeEntered) ?? null;
  const selected = view.matches.find((m) => m.id === selectedId) ?? current;

  return (
    <Container size="xs" py="md" px="sm">
      <Stack>
        {swrView.error != null ? (
          <Alert color="orange" icon={<IconWifiOff size={18} />} py="xs">
            {isLinkRefused(swrView.error)
              ? t('score_link_refused_now')
              : t('score_connection_retrying')}
          </Alert>
        ) : null}
        <Group justify="space-between" wrap="nowrap">
          <Stack gap={0} style={{ minWidth: 0 }}>
            <Title order={3} lh={1.2}>
              {view.court_name ?? view.link_name}
            </Title>
            <Text size="sm" c="dimmed" truncate>
              {view.tournament_name}
            </Text>
          </Stack>
          {/* A full button on wider screens, a large icon on phones (no clipped text) */}
          <Button
            visibleFrom="xs"
            variant="light"
            color="orange"
            leftSection={<IconClockPause size={20} />}
            onClick={() => setDelayOpened(true)}
          >
            {t('report_delay_button')}
          </Button>
          <ActionIcon
            hiddenFrom="xs"
            size="xl"
            variant="light"
            color="orange"
            aria-label={t('report_delay_button')}
            onClick={() => setDelayOpened(true)}
          >
            <IconClockPause size={24} />
          </ActionIcon>
        </Group>

        {selected != null ? (
          <Card withBorder shadow="sm" radius="md" padding="md">
            <Stack>
              <Group justify="space-between">
                <MatchHeader match={selected} />
                {selected.id === current?.id ? (
                  selected.started_at == null &&
                  selected.start_time != null &&
                  new Date(selected.start_time) > new Date() ? (
                    <Badge color="blue">{t('score_next_badge')}</Badge>
                  ) : (
                    <Badge color="green">{t('score_now_badge')}</Badge>
                  )
                ) : null}
              </Group>
              {canBeEntered(selected) ? (
                <SuspendedAlert suspended={selected.suspended_players} teams={teamsOf(selected)} />
              ) : null}
              {canBeEntered(selected) ? (
                <CheckInRow
                  token={token}
                  match={selected}
                  onChanged={async () => {
                    await swrView.mutate();
                  }}
                />
              ) : null}
              {canBeEntered(selected) && !selected.played ? (
                selected.started_at == null ? (
                  <Button
                    size="lg"
                    variant="light"
                    color="green"
                    leftSection={<IconPlayerPlay size={22} />}
                    onClick={async () => {
                      const result = await setStartedAtPitch(token, selected.id, true);
                      if (requestSucceeded(result)) await swrView.mutate();
                    }}
                  >
                    {t('score_start_match_button')}
                  </Button>
                ) : (
                  <Group justify="space-between">
                    <Badge color="green" size="lg" variant="light">
                      {t('score_started_at')} <Time datetime={selected.started_at} />
                    </Badge>
                    <Button
                      size="xs"
                      variant="subtle"
                      color="gray"
                      onClick={async () => {
                        const result = await setStartedAtPitch(token, selected.id, false);
                        if (requestSucceeded(result)) await swrView.mutate();
                      }}
                    >
                      {t('score_undo_start_button')}
                    </Button>
                  </Group>
                )
              ) : null}
              {canBeEntered(selected) ? (
                <ResultForm
                  token={token}
                  match={selected}
                  walkoverGoals={view.walkover_goals}
                  onSaved={async () => {
                    setSelectedId(null);
                    await swrView.mutate();
                  }}
                />
              ) : (
                <Alert color="gray">{t('score_teams_unknown')}</Alert>
              )}
              {canBeEntered(selected) && selected.discipline_allowed ? (
                <Accordion variant="contained">
                  <Accordion.Item value="cards">
                    <Accordion.Control>
                      {t('cards_title')}
                      {selected.cards.length > 0 ? ` (${selected.cards.length})` : ''}
                    </Accordion.Control>
                    <Accordion.Panel>
                      <CardsEditor
                        cards={selected.cards}
                        teams={teamsOf(selected)}
                        onAdd={async (body) => {
                          const response = await createCardAtPitch(token, selected.id, body);
                          await swrView.mutate();
                          return response;
                        }}
                        onDelete={async (cardId) => {
                          await deleteCardAtPitch(token, cardId);
                          await swrView.mutate();
                        }}
                      />
                    </Accordion.Panel>
                  </Accordion.Item>
                </Accordion>
              ) : null}
            </Stack>
          </Card>
        ) : (
          <Alert color="green" icon={<IconCheck />}>
            {t('score_all_played')}
          </Alert>
        )}

        {unplayed.length > 0 ? (
          <Stack gap="xs">
            <Title order={5}>{t('score_upcoming_title')}</Title>
            {unplayed.map((match) => (
              <MatchRow
                key={match.id}
                match={match}
                selected={match.id === selected?.id}
                onClick={() => setSelectedId(match.id)}
              />
            ))}
          </Stack>
        ) : null}

        {played.length > 0 ? (
          <Stack gap="xs">
            <Button variant="subtle" onClick={() => setShowPlayed(!showPlayed)}>
              {showPlayed
                ? t('score_hide_played')
                : t('score_show_played', { count: played.length })}
            </Button>
            {showPlayed
              ? played.map((match) => (
                  <MatchRow
                    key={match.id}
                    match={match}
                    selected={match.id === selected?.id}
                    onClick={() => {
                      setSelectedId(match.id);
                      window.scrollTo({ top: 0, behavior: 'smooth' });
                    }}
                  />
                ))
              : null}
          </Stack>
        ) : null}
      </Stack>
      <DelayDrawer token={token} opened={delayOpened} onClose={() => setDelayOpened(false)} />
    </Container>
  );
}
