import {
  ActionIcon,
  Button,
  Group,
  List,
  Modal,
  Stack,
  Table,
  Text,
  Title,
  Tooltip,
} from '@mantine/core';
import { useMediaQuery } from '@mantine/hooks';
import { IconHelp } from '@tabler/icons-react';
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router';

import { HELP, HelpPageId } from './help_content';

/** The help of one page: intro, steps, fields, actions, tips and related pages. */
function HelpContent({ page, onNavigate }: { page: HelpPageId; onNavigate: (to: string) => void }) {
  const { t } = useTranslation();
  const help = HELP[page];
  const key = (suffix: string) => `help_${page}_${suffix}`;
  const steps = Array.from({ length: help.steps }, (_, i) => key(`step_${i + 1}`));
  const tips = Array.from({ length: help.tips }, (_, i) => key(`tip_${i + 1}`));

  const definitions = (kind: 'field' | 'action', ids: string[]) => (
    <Table variant="vertical" layout="fixed" withTableBorder>
      <Table.Tbody>
        {ids.map((id) => (
          <Table.Tr key={id}>
            <Table.Th w="35%" style={{ verticalAlign: 'top' }}>
              {t(key(`${kind}_${id}`))}
            </Table.Th>
            <Table.Td>{t(key(`${kind}_${id}_text`))}</Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );

  return (
    <Stack gap="md">
      <Stack gap={4}>
        <Title order={4}>{t('help_section_intro')}</Title>
        <Text size="sm">{t(key('intro'))}</Text>
      </Stack>
      {steps.length > 0 ? (
        <Stack gap={4}>
          <Title order={4}>{t('help_section_steps')}</Title>
          <List type="ordered" size="sm" spacing={4}>
            {steps.map((step) => (
              <List.Item key={step}>{t(step)}</List.Item>
            ))}
          </List>
        </Stack>
      ) : null}
      {help.fields.length > 0 ? (
        <Stack gap={4}>
          <Title order={4}>{t('help_section_fields')}</Title>
          {definitions('field', help.fields)}
        </Stack>
      ) : null}
      {help.actions.length > 0 ? (
        <Stack gap={4}>
          <Title order={4}>{t('help_section_actions')}</Title>
          {definitions('action', help.actions)}
        </Stack>
      ) : null}
      {tips.length > 0 ? (
        <Stack gap={4}>
          <Title order={4}>{t('help_section_tips')}</Title>
          <List size="sm" spacing={4}>
            {tips.map((tip) => (
              <List.Item key={tip}>{t(tip)}</List.Item>
            ))}
          </List>
        </Stack>
      ) : null}
      {help.links.length > 0 ? (
        <Stack gap={4}>
          <Title order={4}>{t('help_section_links')}</Title>
          <Group gap="xs">
            {help.links.map((link) => (
              <Button key={link.page} variant="light" size="xs" onClick={() => onNavigate(link.to)}>
                {t(`help_${link.page}_title`)}
              </Button>
            ))}
          </Group>
        </Stack>
      ) : null}
    </Stack>
  );
}

/**
 * "Hjelp" next to a page title: opens a modal that explains the page, its fields and actions.
 * Hidden on paper (no-print).
 */
export function HelpButton({ page }: { page: HelpPageId }) {
  const { t } = useTranslation();
  const [opened, setOpened] = useState(false);
  const navigate = useNavigate();
  const params = useParams();
  const isPhone = useMediaQuery('(max-width: 36em)');
  const title = t(`help_${page}_title`);

  return (
    <>
      <Modal
        opened={opened}
        onClose={() => setOpened(false)}
        title={<Text fw={700}>{t('help_modal_title', { page: title })}</Text>}
        size="lg"
        fullScreen={isPhone}
        className="no-print"
      >
        <HelpContent
          page={page}
          onNavigate={(to) => {
            setOpened(false);
            navigate(to.replace(':id', params.id ?? ''));
          }}
        />
      </Modal>
      <Tooltip label={t('help_button_tooltip')} withArrow>
        {isPhone ? (
          <ActionIcon
            className="no-print"
            variant="light"
            size="lg"
            radius="xl"
            aria-label={t('help_modal_title', { page: title })}
            onClick={() => setOpened(true)}
          >
            <IconHelp size={20} />
          </ActionIcon>
        ) : (
          <Button
            className="no-print"
            variant="light"
            size="xs"
            radius="xl"
            leftSection={<IconHelp size={16} />}
            aria-label={t('help_modal_title', { page: title })}
            onClick={() => setOpened(true)}
          >
            {t('help_button')}
          </Button>
        )}
      </Tooltip>
    </>
  );
}

/** A page title with its help button right next to it. */
export function PageTitle({
  help,
  children,
  order = 1,
  mb,
}: {
  help: HelpPageId;
  children: React.ReactNode;
  order?: 1 | 2 | 3;
  mb?: string;
}) {
  return (
    <Group gap="sm" wrap="nowrap" align="center" mb={mb}>
      <Title order={order} style={{ minWidth: 0 }}>
        {children}
      </Title>
      <HelpButton page={help} />
    </Group>
  );
}

/** Help for an anchor element in a modal header (Mantine modal titles accept nodes). */
export function TitleWithHelp({ help, children }: { help: HelpPageId; children: React.ReactNode }) {
  return (
    <Group gap="sm" wrap="nowrap">
      <Text fw={600}>{children}</Text>
      <HelpButton page={help} />
    </Group>
  );
}
