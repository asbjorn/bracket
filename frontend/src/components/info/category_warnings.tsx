import { Alert, Stack } from '@mantine/core';
import { IconAlertTriangle } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

import { CategoryWarning } from '@openapi';

const MAX_TEAM_NAMES = 8;

function formatTeamNames(names: string[], moreLabel: string) {
  if (names.length <= MAX_TEAM_NAMES) return names.join(', ');
  return `${names.slice(0, MAX_TEAM_NAMES).join(', ')} ${moreLabel}`;
}

export function CategoryWarningMessage({ warning }: { warning: CategoryWarning }) {
  const { t } = useTranslation();
  const more = t('and_more_label', { count: warning.team_names.length - MAX_TEAM_NAMES });
  const teams = formatTeamNames(warning.team_names, more);

  switch (warning.code) {
    case 'TOO_FEW_MATCHES':
      return t('warning_too_few_matches', {
        count: warning.team_names.length,
        minimum: warning.minimum_matches,
        teams,
      });
    case 'UNPLACED_TEAMS':
      return t('warning_unplaced_teams', { count: warning.team_names.length, teams });
    case 'CHILDREN_RESULTS_PUBLIC':
      return t('warning_children_results_public');
    default:
      return null;
  }
}

/**
 * Warnings about an age class breaking the NFF rules, e.g. teams getting fewer than 3 matches.
 */
export function CategoryWarnings({ warnings }: { warnings: CategoryWarning[] }) {
  if (warnings.length < 1) return null;

  return (
    <Stack gap="xs">
      {warnings.map((warning) => (
        <Alert key={warning.code} color="yellow" icon={<IconAlertTriangle />} radius="md">
          <CategoryWarningMessage warning={warning} />
        </Alert>
      ))}
    </Stack>
  );
}
