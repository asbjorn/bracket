import { Alert, List, Text } from '@mantine/core';
import { IconAlertTriangle } from '@tabler/icons-react';
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { SWRResponse } from 'swr';

import { formatMatchInput1, formatMatchInput2 } from '@components/utils/match';
import { PlanIssueOut, StagesWithStageItemsResponse } from '@openapi';
import { getPlanIssues } from '@services/adapter';

const MAX_ISSUES_SHOWN = 10;

/**
 * Problems in the current plan, e.g. after moving matches by hand or delaying them.
 */
export function PlanIssues({
  tournamentId,
  swrStagesResponse,
  matchesLookup,
  stageItemsLookup,
}: {
  tournamentId: number;
  swrStagesResponse: SWRResponse<StagesWithStageItemsResponse>;
  matchesLookup: any;
  stageItemsLookup: any;
}) {
  const { t } = useTranslation();
  const swrIssuesResponse = getPlanIssues(tournamentId);
  // Check again whenever the matches change
  useEffect(() => {
    swrIssuesResponse.mutate();
  }, [swrStagesResponse.data]);

  const issues: PlanIssueOut[] = swrIssuesResponse.data?.data ?? [];
  if (issues.length < 1) return null;

  const label = (matchId: number) => {
    const data = matchesLookup[matchId];
    if (data == null) return `#${matchId}`;
    return `${formatMatchInput1(t, stageItemsLookup, matchesLookup, data.match)} – ${formatMatchInput2(t, stageItemsLookup, matchesLookup, data.match)}`;
  };

  return (
    <Alert color="orange" icon={<IconAlertTriangle />} title={t('plan_issues_title')} mb="md">
      <List size="sm">
        {issues.slice(0, MAX_ISSUES_SHOWN).map((issue) => (
          <List.Item key={`${issue.match_id}-${issue.kind}-${issue.other_match_id}`}>
            {t(`plan_issue_${issue.kind.toLowerCase()}`, {
              match: label(issue.match_id),
              other: issue.other_match_id != null ? label(issue.other_match_id) : '',
            })}
          </List.Item>
        ))}
      </List>
      {issues.length > MAX_ISSUES_SHOWN ? (
        <Text size="sm" mt="xs">
          {t('and_more_label', { count: issues.length - MAX_ISSUES_SHOWN })}
        </Text>
      ) : null}
    </Alert>
  );
}
