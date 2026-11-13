import { Alert, Button, Container, Group, Text, Title } from '@mantine/core';
import { IconAlertCircle, IconArrowRight } from '@tabler/icons-react';
import React from 'react';
import { useTranslation } from 'react-i18next';
import { HiMiniWrenchScrewdriver } from 'react-icons/hi2';

import PreloadLink from '@components/utils/link';

import classes from './empty_table_info.module.css';

export function EmptyTableInfo({
  entity_name,
  message = '',
}: {
  entity_name: string;
  message?: string;
}) {
  const { t } = useTranslation();
  return (
    <Alert
      icon={<IconAlertCircle size={16} />}
      title={`No ${entity_name} found`}
      color="blue"
      radius="lg"
      mt={8}
    >
      {t('could_not_find_any_alert')} {entity_name}
      {message}
    </Alert>
  );
}

/**
 * An empty page or list. `actions`: buttons for what to do about it (the first one filled), so
 * the page is never a dead end.
 */
export function NoContent({
  title,
  description,
  icon,
  actions,
}: {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <Container mt="md">
      <div className={classes.label}>{icon || <HiMiniWrenchScrewdriver />}</div>
      <Title className={classes.title}>{title}</Title>
      <Text size="lg" ta="center" className={classes.description} inherit>
        {description}
      </Text>
      {actions != null ? (
        <Group justify="center" gap="sm" mt="lg">
          {actions}
        </Group>
      ) : null}
    </Container>
  );
}

/** A button in an empty state that goes to another page. */
export function NoContentLink({
  href,
  label,
  primary = false,
}: {
  href: string;
  label: string;
  primary?: boolean;
}) {
  return (
    <Button
      component={PreloadLink}
      href={href}
      variant={primary ? 'filled' : 'default'}
      color="indigo"
      rightSection={primary ? <IconArrowRight size={16} /> : undefined}
    >
      {label}
    </Button>
  );
}
