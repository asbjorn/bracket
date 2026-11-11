import { Button, Group, Modal, NumberInput, Stack, Table, Text } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { StageItemWithRounds } from '@openapi';
import { createAxios, handleRequestError, requestSucceeded } from '@services/adapter';

/**
 * Drawing of lots for a group (the last tiebreaker): the organiser draws and enters the order,
 * 1 = best. Empty: the fixed random order is used.
 */
export default function LotsModal({
  tournamentId,
  stageItem,
  onClose,
  onSaved,
}: {
  tournamentId: number;
  stageItem: StageItemWithRounds;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const { t } = useTranslation();
  const inputs = [...stageItem.inputs].sort((a, b) => a.slot - b.slot);
  const [lots, setLots] = useState<Record<number, number | string>>(
    Object.fromEntries(inputs.map((input) => [input.id, input.lot_number ?? ''])),
  );
  const [saving, setSaving] = useState(false);
  const name = (input: (typeof inputs)[number]) =>
    'team' in input && input.team != null ? input.team.name : `#${input.slot}`;

  async function save() {
    setSaving(true);
    const response = await createAxios()
      .put(`tournaments/${tournamentId}/stage_items/${stageItem.id}/lots`, {
        lots: inputs.map((input) => ({
          stage_item_input_id: input.id,
          lot_number: lots[input.id] === '' ? null : Number(lots[input.id]),
        })),
      })
      .catch((error: any) => handleRequestError(error));
    setSaving(false);
    if (response != null && requestSucceeded(response)) {
      await onSaved();
      onClose();
    }
  }

  return (
    <Modal opened onClose={onClose} title={`${t('lots_title')}: ${stageItem.name}`}>
      <Stack>
        <Text size="sm" c="dimmed">
          {t('lots_description')}
        </Text>
        <Table>
          <Table.Tbody>
            {inputs.map((input) => (
              <Table.Tr key={input.id}>
                <Table.Td>{name(input)}</Table.Td>
                <Table.Td w="8rem">
                  <NumberInput
                    aria-label={t('lots_number_label')}
                    value={lots[input.id]}
                    min={1}
                    max={999}
                    allowDecimal={false}
                    onChange={(value) => setLots({ ...lots, [input.id]: value })}
                  />
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
        <Group justify="right">
          <Button variant="default" onClick={onClose}>
            {t('cancel_button')}
          </Button>
          <Button loading={saving} onClick={save}>
            {t('save_button')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
