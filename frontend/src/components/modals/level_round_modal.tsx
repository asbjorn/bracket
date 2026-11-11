import {
  Alert,
  Button,
  Group,
  Modal,
  NumberInput,
  SegmentedControl,
  Stack,
  Table,
  Text,
  TextInput,
} from '@mantine/core';
import { IconInfoCircle, IconStairs } from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { getAllTeamsOfCategory, requestSucceeded } from '@services/adapter';
import { createLevelRound } from '@services/stage';

/**
 * A new round of groups composed by hand ("nivådelt"): teams of a similar level play each other.
 * Nothing is placed from results, so it also works for children's classes with hidden results.
 */
export default function LevelRoundButton({
  tournamentId,
  categoryId,
  onCreated,
}: {
  tournamentId: number;
  categoryId: number;
  onCreated: () => Promise<void>;
}) {
  const { t } = useTranslation();
  const [opened, setOpened] = useState(false);
  const teams = (getAllTeamsOfCategory(tournamentId, opened ? categoryId : null).data ?? []).sort(
    (a, b) => a.name.localeCompare(b.name),
  );
  const [stageName, setStageName] = useState(t('level_round_default_name'));
  const [groupCount, setGroupCount] = useState<number | string>(2);
  const [groupOf, setGroupOf] = useState<Record<number, string>>({});
  const [saving, setSaving] = useState(false);

  const count = Math.max(2, Math.min(8, Number(groupCount) || 2));
  const letters = Array.from({ length: count }, (_, i) => String.fromCharCode(65 + i));
  const groupName = (letter: string) => t('level_group_name', { letter });
  const membersOf = (letter: string) =>
    teams.filter((team) => (groupOf[team.id] ?? letters[0]) === letter);
  const tooSmall = letters.some((letter) => membersOf(letter).length < 2);

  async function create() {
    setSaving(true);
    const response = await createLevelRound(tournamentId, categoryId, {
      stage_name: stageName.trim(),
      groups: letters.map((letter) => ({
        name: groupName(letter),
        team_ids: membersOf(letter).map((team) => team.id),
      })),
    });
    setSaving(false);
    if (requestSucceeded(response)) {
      await onCreated();
      setOpened(false);
    }
  }

  return (
    <>
      <Modal
        opened={opened}
        onClose={() => setOpened(false)}
        title={t('level_round_title')}
        size="lg"
      >
        <Stack>
          <Alert color="gray" icon={<IconInfoCircle />}>
            {t('level_round_description')}
          </Alert>
          <Group grow>
            <TextInput
              label={t('level_round_name_label')}
              value={stageName}
              maxLength={50}
              onChange={(event) => setStageName(event.currentTarget.value)}
            />
            <NumberInput
              label={t('level_round_group_count_label')}
              value={groupCount}
              min={2}
              max={8}
              onChange={setGroupCount}
            />
          </Group>
          <Table>
            <Table.Tbody>
              {teams.map((team) => (
                <Table.Tr key={team.id}>
                  <Table.Td>{team.name}</Table.Td>
                  <Table.Td>
                    <SegmentedControl
                      size="xs"
                      data={letters}
                      value={groupOf[team.id] ?? letters[0]}
                      onChange={(value) => setGroupOf({ ...groupOf, [team.id]: value })}
                    />
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
          <Group gap="lg">
            {letters.map((letter) => (
              <Text key={letter} size="sm" c={membersOf(letter).length < 2 ? 'red' : undefined}>
                {groupName(letter)}: {membersOf(letter).length}
              </Text>
            ))}
          </Group>
          <Button loading={saving} disabled={tooSmall || stageName.trim() === ''} onClick={create}>
            {t('level_round_create_button')}
          </Button>
        </Stack>
      </Modal>
      <Button
        variant="light"
        leftSection={<IconStairs size={20} />}
        onClick={() => setOpened(true)}
      >
        {t('level_round_button')}
      </Button>
    </>
  );
}
