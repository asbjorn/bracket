import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Group,
  MultiSelect,
  NumberInput,
  SegmentedControl,
  Select,
  Stack,
  Table,
  Text,
  Textarea,
  Title,
} from '@mantine/core';
import { IconInfoCircle, IconTrash } from '@tabler/icons-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { PageTitle } from '@components/help/help_button';
import { CardIcon } from '@components/discipline/cards_editor';
import { formatMatchInput1, formatMatchInput2 } from '@components/utils/match';
import { getTournamentIdFromRouter } from '@components/utils/util';
import { formatDayTime } from '@components/utils/datetime';
import JuryMembers from '@components/discipline/jury_members';
import { DisciplineOverview, MatchWithDetails, StageWithStageItems } from '@openapi';
import TournamentLayout from '@pages/tournaments/_tournament_layout';
import { getStages, requestSucceeded, getJuryMembers } from '@services/adapter';
import {
  createJuryDecision,
  deleteCard,
  deleteJuryDecision,
  getDiscipline,
  saveDisciplineSettings,
} from '@services/discipline';
import { getMatchLookup, getStageItemLookup } from '@services/lookups';

type Refresh = () => Promise<unknown>;

function teamNames(stages: StageWithStageItems[]): Record<number, string> {
  const names: Record<number, string> = {};
  stages.forEach((stage) =>
    stage.stage_items.forEach((item) =>
      item.inputs.forEach((input) => {
        if ('team' in input && input.team != null) names[input.team.id] = input.team.name;
      }),
    ),
  );
  return names;
}

function SettingsCard({
  tournamentId,
  overview,
  refresh,
}: {
  tournamentId: number;
  overview: DisciplineOverview;
  refresh: Refresh;
}) {
  const { t } = useTranslation();
  const [perRed, setPerRed] = useState<number | string>(
    overview.settings.suspension_matches_per_red,
  );
  const [yellows, setYellows] = useState<string>(
    `${overview.settings.yellow_cards_for_suspension ?? 'off'}`,
  );
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    setPerRed(overview.settings.suspension_matches_per_red);
    setYellows(`${overview.settings.yellow_cards_for_suspension ?? 'off'}`);
  }, [overview.settings]);

  return (
    <Card withBorder>
      <Group align="end">
        <NumberInput
          label={t('suspension_per_red_label')}
          description={t('suspension_per_red_description')}
          min={0}
          max={5}
          value={perRed}
          onChange={setPerRed}
          w="16rem"
        />
        <Select
          label={t('yellow_cards_for_suspension_label')}
          description={t('yellow_cards_for_suspension_description')}
          data={[
            { value: 'off', label: t('yellow_cards_off') },
            ...[2, 3, 4, 5].map((count) => ({
              value: `${count}`,
              label: t('yellow_cards_count', { count }),
            })),
          ]}
          value={yellows}
          onChange={(value) => setYellows(value ?? 'off')}
          allowDeselect={false}
          w="16rem"
        />
        <Button
          loading={saving}
          onClick={async () => {
            setSaving(true);
            const response = await saveDisciplineSettings(tournamentId, {
              suspension_matches_per_red: Number(perRed) || 0,
              yellow_cards_for_suspension: yellows === 'off' ? null : Number(yellows),
            });
            setSaving(false);
            if (requestSucceeded(response)) await refresh();
          }}
        >
          {t('save_button')}
        </Button>
      </Group>
    </Card>
  );
}

function JuryForm({
  tournamentId,
  overview,
  cardLabel,
  refresh,
}: {
  tournamentId: number;
  overview: DisciplineOverview;
  cardLabel: (cardId: number) => string;
  refresh: Refresh;
}) {
  const { t } = useTranslation();
  const [text, setText] = useState('');
  const [cardId, setCardId] = useState<string | null>(null);
  const [change, setChange] = useState('0');
  const [saving, setSaving] = useState(false);
  const jury = getJuryMembers(tournamentId).data?.data.members ?? [];
  // Unless chosen otherwise, the whole jury took the decision
  const [memberIds, setMemberIds] = useState<string[] | null>(null);
  const chosenMembers = memberIds ?? jury.map((member) => `${member.id}`);

  return (
    <Stack gap="xs">
      <Textarea
        label={t('jury_decision_label')}
        placeholder={t('jury_decision_placeholder')}
        autosize
        minRows={2}
        value={text}
        onChange={(event) => setText(event.currentTarget.value)}
      />
      {jury.length > 0 ? (
        <MultiSelect
          label={t('jury_decided_by_label')}
          data={jury.map((member) => ({ value: `${member.id}`, label: member.name }))}
          value={chosenMembers}
          onChange={setMemberIds}
          maw="32rem"
        />
      ) : null}
      <Group align="end">
        <Select
          label={t('jury_card_label')}
          placeholder={t('jury_no_card_placeholder')}
          data={overview.cards.map((card) => ({ value: `${card.id}`, label: cardLabel(card.id) }))}
          value={cardId}
          onChange={(value) => {
            setCardId(value);
            if (value == null) setChange('0');
          }}
          clearable
          searchable
          w="24rem"
        />
        {cardId != null ? (
          <Stack gap={4}>
            <Text size="sm" fw={500}>
              {t('jury_suspension_change_label')}
            </Text>
            <SegmentedControl
              data={['-2', '-1', '0', '+1', '+2'].map((value) => ({
                value: `${Number(value)}`,
                label: value,
              }))}
              value={change}
              onChange={setChange}
            />
          </Stack>
        ) : null}
        <Button
          loading={saving}
          disabled={text.trim() === ''}
          onClick={async () => {
            setSaving(true);
            const card = overview.cards.find((c) => `${c.id}` === cardId);
            const response = await createJuryDecision(tournamentId, {
              text: text.trim(),
              card_id: card?.id ?? null,
              match_id: card?.match_id ?? null,
              team_id: card?.team_id ?? null,
              suspension_change: card != null ? Number(change) : 0,
              member_ids: chosenMembers.map(Number),
            });
            setSaving(false);
            if (requestSucceeded(response)) {
              setText('');
              setCardId(null);
              setChange('0');
              setMemberIds(null);
              await refresh();
            }
          }}
        >
          {t('jury_add_button')}
        </Button>
      </Group>
    </Stack>
  );
}

export default function DisciplinePage() {
  const { t, i18n } = useTranslation();
  const { tournamentData } = getTournamentIdFromRouter();
  const tournamentId = tournamentData.id;
  const swrDiscipline = getDiscipline(tournamentId);
  const swrStagesResponse = getStages(tournamentId);
  const overview = swrDiscipline.data?.data;
  const refresh = () => swrDiscipline.mutate();
  const juryNames: Record<number, string> = Object.fromEntries(
    (getJuryMembers(tournamentId).data?.data.members ?? []).map((m) => [m.id, m.name]),
  );

  const stages = swrStagesResponse.data?.data ?? [];
  const teams = teamNames(stages);
  const matchesLookup = swrStagesResponse.data != null ? getMatchLookup(swrStagesResponse) : {};
  const stageItemsLookup =
    swrStagesResponse.data != null ? getStageItemLookup(swrStagesResponse) : {};
  const matchOf = (matchId: number): MatchWithDetails | null =>
    matchesLookup[matchId]?.match ?? null;
  const matchLabel = (matchId: number) => {
    const match = matchOf(matchId);
    if (match == null) return `#${matchId}`;
    const time =
      match.start_time != null
        ? formatDayTime(match.start_time, i18n.resolvedLanguage, 'weekday_time')
        : '';
    const team1 = formatMatchInput1(t, stageItemsLookup, matchesLookup, match);
    const team2 = formatMatchInput2(t, stageItemsLookup, matchesLookup, match);
    return `${time} ${team1} – ${team2}`.trim();
  };
  const cardLabel = (cardId: number) => {
    const card = overview?.cards.find((c) => c.id === cardId);
    if (card == null) return '';
    return `${t(`card_type_${card.card_type.toLowerCase()}`)}: ${card.player_name} (${teams[card.team_id] ?? ''}) · ${matchLabel(card.match_id)}`;
  };

  return (
    <TournamentLayout tournament_id={tournamentId}>
      <Stack>
        <PageTitle help="discipline">{t('discipline_title')}</PageTitle>
        <Alert color="gray" icon={<IconInfoCircle />}>
          {t('discipline_description')}
        </Alert>
        {overview != null ? (
          <>
            <SettingsCard tournamentId={tournamentId} overview={overview} refresh={refresh} />

            <Title order={3}>
              {t('suspensions_title')}{' '}
              <Badge color={overview.suspensions.length > 0 ? 'red' : 'gray'}>
                {overview.suspensions.length}
              </Badge>
            </Title>
            {overview.suspensions.length < 1 ? (
              <Text c="dimmed">{t('no_suspensions')}</Text>
            ) : (
              <Table.ScrollContainer minWidth={600}>
                <Table>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>{t('card_player_label')}</Table.Th>
                      <Table.Th>{t('team_label')}</Table.Th>
                      <Table.Th>{t('suspension_reason_header')}</Table.Th>
                      <Table.Th>{t('suspension_matches_header')}</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {overview.suspensions.map((suspension) => {
                      const served =
                        suspension.match_ids.length > 0 &&
                        suspension.match_ids.every((id) => matchOf(id)?.played);
                      return (
                        <Table.Tr key={`${suspension.card_id}`}>
                          <Table.Td fw={500}>{suspension.player_name}</Table.Td>
                          <Table.Td>{teams[suspension.team_id] ?? ''}</Table.Td>
                          <Table.Td>
                            {t(`suspension_reason_${suspension.reason.toLowerCase()}`)}
                          </Table.Td>
                          <Table.Td>
                            <Group gap="xs">
                              {served ? (
                                <Badge color="gray">{t('suspension_served_badge')}</Badge>
                              ) : null}
                              {suspension.match_ids.length < 1 ? (
                                <Text size="sm" c="dimmed">
                                  {t('suspension_no_matches_left')}
                                </Text>
                              ) : (
                                <Stack gap={0}>
                                  {suspension.match_ids.map((id) => (
                                    <Text key={id} size="sm">
                                      {matchLabel(id)}
                                    </Text>
                                  ))}
                                </Stack>
                              )}
                            </Group>
                          </Table.Td>
                        </Table.Tr>
                      );
                    })}
                  </Table.Tbody>
                </Table>
              </Table.ScrollContainer>
            )}

            <Title order={3}>{t('cards_title')}</Title>
            {overview.cards.length < 1 ? (
              <Text c="dimmed">{t('discipline_no_cards')}</Text>
            ) : (
              <Table.ScrollContainer minWidth={600}>
                <Table striped>
                  <Table.Tbody>
                    {[...overview.cards].reverse().map((card) => (
                      <Table.Tr key={card.id}>
                        <Table.Td w={30}>
                          <CardIcon type={card.card_type} />
                        </Table.Td>
                        <Table.Td fw={500}>
                          {card.player_name}
                          {card.minute != null ? ` (${card.minute}')` : ''}
                        </Table.Td>
                        <Table.Td>{teams[card.team_id] ?? ''}</Table.Td>
                        <Table.Td>
                          <Text size="sm">{matchLabel(card.match_id)}</Text>
                        </Table.Td>
                        <Table.Td>
                          <ActionIcon
                            variant="subtle"
                            color="red"
                            aria-label={t('delete_card_label')}
                            onClick={async () => {
                              if (!window.confirm(t('delete_card_confirm'))) return;
                              await deleteCard(tournamentId, card.id);
                              await refresh();
                            }}
                          >
                            <IconTrash size={16} />
                          </ActionIcon>
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Table.ScrollContainer>
            )}

            <Title order={3}>{t('jury_title')}</Title>
            <JuryMembers tournamentId={tournamentId} />
            <Title order={4}>{t('jury_log_title')}</Title>
            <JuryForm
              tournamentId={tournamentId}
              overview={overview}
              cardLabel={cardLabel}
              refresh={refresh}
            />
            {overview.decisions.map((decision) => (
              <Card key={decision.id} withBorder padding="sm">
                <Group justify="space-between" align="start" wrap="nowrap">
                  <Stack gap={4}>
                    <Text size="xs" c="dimmed">
                      {formatDayTime(
                        decision.decided_at,
                        i18n.resolvedLanguage,
                        'weekday_date_time',
                      )}
                      {decision.card_id != null ? ` · ${cardLabel(decision.card_id)}` : ''}
                      {decision.suspension_change !== 0
                        ? ` · ${t('jury_change_badge', {
                            change:
                              decision.suspension_change > 0
                                ? `+${decision.suspension_change}`
                                : decision.suspension_change,
                          })}`
                        : ''}
                    </Text>
                    <Text style={{ whiteSpace: 'pre-wrap' }}>{decision.text}</Text>
                    {decision.member_ids.length > 0 ? (
                      <Text size="xs" c="dimmed">
                        {t('jury_decided_by_label')}:{' '}
                        {decision.member_ids
                          .map((id) => juryNames[id])
                          .filter(Boolean)
                          .join(', ')}
                      </Text>
                    ) : null}
                  </Stack>
                  <ActionIcon
                    variant="subtle"
                    color="red"
                    onClick={async () => {
                      if (!window.confirm(t('delete_jury_decision_confirm'))) return;
                      await deleteJuryDecision(tournamentId, decision.id);
                      await refresh();
                    }}
                  >
                    <IconTrash size={16} />
                  </ActionIcon>
                </Group>
              </Card>
            ))}
          </>
        ) : null}
      </Stack>
    </TournamentLayout>
  );
}
