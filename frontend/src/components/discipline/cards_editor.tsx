import {
  ActionIcon,
  Alert,
  Badge,
  Box,
  Button,
  Group,
  NumberInput,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
} from '@mantine/core';
import { IconAlertTriangle, IconTrash } from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { CardType, MatchCard, MatchCardBody, SuspendedPlayer } from '@openapi';
import { requestSucceeded } from '@services/adapter';

export const CARD_COLORS: Record<CardType, string> = {
  YELLOW: 'yellow',
  YELLOW_RED: 'orange',
  RED: 'red',
};

/** A small coloured card, like the referee holds up. */
export function CardIcon({ type }: { type: CardType }) {
  return (
    <Box
      component="span"
      aria-hidden
      style={{
        display: 'inline-block',
        width: 12,
        height: 16,
        borderRadius: 2,
        background:
          type === 'YELLOW_RED'
            ? 'linear-gradient(135deg, var(--mantine-color-yellow-5) 50%, var(--mantine-color-red-7) 50%)'
            : `var(--mantine-color-${CARD_COLORS[type]}-${type === 'RED' ? 7 : 5})`,
        verticalAlign: 'middle',
      }}
    />
  );
}

interface TeamOption {
  id: number;
  name: string;
}

/** Players who may not play in this match: shown before kick-off. */
export function SuspendedAlert({
  suspended,
  teams,
}: {
  suspended: SuspendedPlayer[];
  teams: TeamOption[];
}) {
  const { t } = useTranslation();
  if (suspended.length < 1) return null;
  return (
    <Alert color="red" icon={<IconAlertTriangle />} title={t('suspended_players_title')}>
      {suspended.map((player) => (
        <Text key={`${player.team_id}-${player.player_name}`} size="sm">
          <b>{player.player_name}</b> ({teams.find((team) => team.id === player.team_id)?.name})
        </Text>
      ))}
    </Alert>
  );
}

/**
 * Quick card entry for one match: choose the team, type the player, tap the card.
 * Used by the organiser's match form and the pitch page.
 */
export function CardsEditor({
  cards,
  teams,
  onAdd,
  onDelete,
}: {
  cards: MatchCard[];
  teams: TeamOption[];
  onAdd: (body: MatchCardBody) => Promise<any>;
  onDelete: (cardId: number) => Promise<any>;
}) {
  const { t } = useTranslation();
  const [teamId, setTeamId] = useState(`${teams[0]?.id ?? ''}`);
  const [player, setPlayer] = useState('');
  const [minute, setMinute] = useState<number | string>('');
  const [saving, setSaving] = useState<CardType | null>(null);
  const teamName = (id: number) => teams.find((team) => team.id === id)?.name ?? '';

  async function add(cardType: CardType) {
    setSaving(cardType);
    const response = await onAdd({
      team_id: Number(teamId),
      player_name: player.trim(),
      player_id: null,
      card_type: cardType,
      minute: minute === '' ? null : Number(minute),
      note: null,
    });
    setSaving(null);
    if (response != null && requestSucceeded(response)) {
      setPlayer('');
      setMinute('');
    }
  }

  return (
    <Stack gap="xs">
      {cards.map((card) => (
        <Group key={card.id} justify="space-between" wrap="nowrap">
          <Group gap="xs" wrap="nowrap">
            <CardIcon type={card.card_type} />
            <Text size="sm">
              <b>{card.player_name}</b> · {teamName(card.team_id)}
              {card.minute != null ? ` · ${card.minute}'` : ''}
            </Text>
          </Group>
          <ActionIcon
            variant="subtle"
            color="red"
            aria-label={t('delete_card_label')}
            onClick={() => onDelete(card.id)}
          >
            <IconTrash size={16} />
          </ActionIcon>
        </Group>
      ))}
      <SegmentedControl
        fullWidth
        data={teams.map((team) => ({ value: `${team.id}`, label: team.name }))}
        value={teamId}
        onChange={setTeamId}
      />
      <Group grow align="end">
        <TextInput
          label={t('card_player_label')}
          placeholder={t('card_player_placeholder')}
          value={player}
          onChange={(event) => setPlayer(event.currentTarget.value)}
          style={{ flexGrow: 3 }}
        />
        <NumberInput
          label={t('card_minute_label')}
          min={0}
          max={200}
          value={minute}
          onChange={setMinute}
          style={{ flexGrow: 1 }}
        />
      </Group>
      <SimpleGrid cols={3} spacing="xs">
        {(['YELLOW', 'YELLOW_RED', 'RED'] as CardType[]).map((cardType) => (
          <Button
            key={cardType}
            size="md"
            h="auto"
            py="xs"
            px="xs"
            // Labels may wrap on a phone instead of being cut off
            styles={{ label: { whiteSpace: 'normal', textAlign: 'center', lineHeight: 1.2 } }}
            variant="light"
            color={CARD_COLORS[cardType]}
            leftSection={<CardIcon type={cardType} />}
            loading={saving === cardType}
            disabled={player.trim() === '' || teamId === ''}
            onClick={() => add(cardType)}
          >
            {t(`card_type_${cardType.toLowerCase()}`)}
          </Button>
        ))}
      </SimpleGrid>
      {cards.length < 1 ? (
        <Badge variant="light" color="gray">
          {t('no_cards_badge')}
        </Badge>
      ) : null}
    </Stack>
  );
}
