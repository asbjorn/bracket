import {
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
  IconPlus,
} from '@tabler/icons-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router';

import { Time } from '@components/utils/datetime';
import { MatchResultType, ScoreEntryMatch } from '@openapi';
import { requestSucceeded } from '@services/adapter';
import { enterResult, getScoreEntry, reportFromPitch } from '@services/score_links';

const RESULT_TYPES: MatchResultType[] = ['NORMAL', 'EXTRA_TIME', 'PENALTIES', 'WALKOVER'];
const DELAY_CHOICES = [5, 10, 15, 30];

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
    </Group>
  );
}

function ResultForm({
  token,
  match,
  onSaved,
}: {
  token: string;
  match: ScoreEntryMatch;
  onSaved: () => Promise<void>;
}) {
  const { t } = useTranslation();
  const [score1, setScore1] = useState(match.score1);
  const [score2, setScore2] = useState(match.score2);
  const [resultType, setResultType] = useState<MatchResultType>(match.result_type);
  const [penalties1, setPenalties1] = useState(match.penalties1 ?? 0);
  const [penalties2, setPenalties2] = useState(match.penalties2 ?? 0);
  const [saving, setSaving] = useState(false);
  const team1 = match.team1_name ?? '?';
  const team2 = match.team2_name ?? '?';

  // Another match was chosen, or the result was changed elsewhere
  useEffect(() => {
    setScore1(match.score1);
    setScore2(match.score2);
    setResultType(match.result_type);
    setPenalties1(match.penalties1 ?? 0);
    setPenalties2(match.penalties2 ?? 0);
  }, [match.id, match.score1, match.score2, match.result_type]);

  let problem: string | null = null;
  if (resultType === 'PENALTIES' && score1 !== score2) problem = t('score_problem_penalties_equal');
  if (resultType === 'PENALTIES' && score1 === score2 && penalties1 === penalties2)
    problem = t('score_problem_penalties_winner');
  if (resultType === 'WALKOVER' && score1 === score2) problem = t('score_problem_walkover_winner');

  return (
    <Stack>
      <ScoreStepper label={team1} value={score1} onChange={setScore1} />
      <ScoreStepper label={team2} value={score2} onChange={setScore2} />
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
            <Text fw={500} truncate>
              {match.team1_name ?? '?'} – {match.team2_name ?? '?'}
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

  if (swrView.error != null) {
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
        <Loader />
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
        <Group justify="space-between" wrap="nowrap">
          <Stack gap={0} style={{ minWidth: 0 }}>
            <Title order={3} lh={1.2}>
              {view.court_name ?? view.link_name}
            </Title>
            <Text size="sm" c="dimmed" truncate>
              {view.tournament_name}
            </Text>
          </Stack>
          <Button
            variant="light"
            color="orange"
            leftSection={<IconClockPause size={20} />}
            onClick={() => setDelayOpened(true)}
          >
            {t('report_delay_button')}
          </Button>
        </Group>

        {selected != null ? (
          <Card withBorder shadow="sm" radius="md" padding="md">
            <Stack>
              <Group justify="space-between">
                <MatchHeader match={selected} />
                {selected.id === current?.id ? (
                  <Badge color="green">{t('score_now_badge')}</Badge>
                ) : null}
              </Group>
              {canBeEntered(selected) ? (
                <ResultForm
                  token={token}
                  match={selected}
                  onSaved={async () => {
                    setSelectedId(null);
                    await swrView.mutate();
                  }}
                />
              ) : (
                <Alert color="gray">{t('score_teams_unknown')}</Alert>
              )}
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
