import {
  Alert,
  Badge,
  Button,
  Card,
  Group,
  NumberInput,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core';
import { IconDownload, IconInfoCircle, IconMedal, IconPresentation } from '@tabler/icons-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import PodiumReveal from '@components/ceremony/podium_reveal';
import { PageTitle } from '@components/help/help_button';
import { PrintButton } from '@components/print/print_button';
import { DayAndTime } from '@components/utils/datetime';
import { contentLanguage } from '@components/utils/language';
import { getTournamentIdFromRouter } from '@components/utils/util';
import { ClassFinalResults, Podium } from '@openapi';
import TournamentLayout from '@pages/tournaments/_tournament_layout';
import { getFinalResults, getTournamentById, requestSucceeded } from '@services/adapter';
import { downloadFinalResultsCsv, saveCeremonySettings } from '@services/registration';

const PLACE_COLORS: Record<number, string> = { 1: 'yellow', 2: 'gray', 3: 'orange' };

function PodiumCard({ podium, className }: { podium: Podium; className: string }) {
  const { t } = useTranslation();
  const shown = podium.placings;
  const [presenting, setPresenting] = useState(false);
  return (
    <Card withBorder padding="sm" radius="md">
      <Group justify="space-between" mb="xs">
        <Text fw={700}>{podium.title}</Text>
        <Group gap="xs">
          {podium.complete ? null : (
            <Badge color="gray" variant="light">
              {t('ceremony_not_finished_badge')}
            </Badge>
          )}
          {shown.some((placing) => placing.place <= 3) ? (
            <Button
              size="xs"
              variant="light"
              color="indigo"
              className="no-print"
              leftSection={<IconPresentation size={16} />}
              onClick={() => setPresenting(true)}
            >
              {t('podium_present_button')}
            </Button>
          ) : null}
        </Group>
      </Group>
      {presenting ? (
        <PodiumReveal className={className} podium={podium} onClose={() => setPresenting(false)} />
      ) : null}
      {shown.length < 1 ? (
        <Text size="sm" c="dimmed">
          {t('ceremony_no_placings_yet')}
        </Text>
      ) : (
        <Table>
          <Table.Tbody>
            {shown.map((placing) => (
              <Table.Tr key={`${placing.place}:${placing.team_id}`}>
                <Table.Td w="3.5rem">
                  <Badge
                    color={PLACE_COLORS[placing.place] ?? 'blue'}
                    variant={placing.place <= 3 ? 'filled' : 'light'}
                    size="lg"
                    circle
                  >
                    {placing.place}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Text fw={placing.place <= 3 ? 600 : 400}>{placing.team_name}</Text>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Card>
  );
}

function ClassCard({ result }: { result: ClassFinalResults }) {
  const { t } = useTranslation();
  return (
    <Card withBorder shadow="sm" radius="md" padding="lg" className="print-keep-together">
      <Stack>
        <Group justify="space-between" align="start">
          <Stack gap={0}>
            <Title order={3}>{result.name}</Title>
            {result.ceremony_time != null ? (
              <Text size="sm">
                {t('ceremony_time_label')} <DayAndTime datetime={result.ceremony_time} />
              </Text>
            ) : (
              <Text size="sm" c="dimmed">
                {t('ceremony_no_schedule')}
              </Text>
            )}
          </Stack>
          <Badge color={result.complete ? 'green' : 'gray'} size="lg">
            {result.complete ? t('ceremony_complete_badge') : t('ceremony_ongoing_badge')}
          </Badge>
        </Group>
        {result.results_public ? (
          <SimpleGrid cols={{ base: 1, sm: 2 }}>
            {result.podiums.map((podium) => (
              <PodiumCard key={podium.stage_item_id} podium={podium} className={result.name} />
            ))}
          </SimpleGrid>
        ) : (
          <Alert color="blue" icon={<IconMedal />} p="sm">
            {t('ceremony_everyone_gets_medal')}
          </Alert>
        )}
        <Group gap="xs">
          <IconMedal size={20} />
          <Text fw={600}>{t('ceremony_medals', { count: result.medal_count })}</Text>
          {result.teams_without_squad_size > 0 ? (
            <Text size="sm" c="orange">
              {t('ceremony_teams_without_squad_size', {
                count: result.teams_without_squad_size,
              })}
            </Text>
          ) : null}
        </Group>
        {!result.results_public ? (
          <Text size="sm" c="dimmed">
            {result.teams.map((team) => team.team_name).join(' · ')}
          </Text>
        ) : null}
      </Stack>
    </Card>
  );
}

export default function CeremonyPage() {
  const { t, i18n } = useTranslation();
  const { tournamentData } = getTournamentIdFromRouter();
  const swrResults = getFinalResults(tournamentData.id);
  const tournament = getTournamentById(tournamentData.id).data?.data;
  const [offset, setOffset] = useState<number | string>(15);
  useEffect(() => {
    if (tournament != null) setOffset(tournament.ceremony_offset_minutes);
  }, [tournament?.ceremony_offset_minutes]);
  const results = swrResults.data?.data ?? [];

  return (
    <TournamentLayout tournament_id={tournamentData.id}>
      <Stack>
        <Group justify="space-between" className="no-print">
          <PageTitle help="ceremony">{t('ceremony_title')}</PageTitle>
          <Group>
            <Button
              variant="default"
              leftSection={<IconDownload size={18} />}
              onClick={() => downloadFinalResultsCsv(tournamentData.id, contentLanguage(i18n))}
            >
              {t('ceremony_export_button')}
            </Button>
            <PrintButton />
          </Group>
        </Group>
        <Alert color="gray" icon={<IconInfoCircle />} className="no-print">
          {t('ceremony_description')}
        </Alert>
        <Group align="end" className="no-print">
          <NumberInput
            label={t('ceremony_offset_label')}
            value={offset}
            min={0}
            max={240}
            w="16rem"
            onChange={setOffset}
          />
          <Button
            variant="light"
            onClick={async () => {
              const response = await saveCeremonySettings(tournamentData.id, Number(offset) || 0);
              if (requestSucceeded(response)) await swrResults.mutate();
            }}
          >
            {t('save_button')}
          </Button>
        </Group>
        {results.length < 1 ? (
          <Text c="dimmed">{t('ceremony_no_classes')}</Text>
        ) : (
          results
            .slice()
            .sort((a, b) => (a.ceremony_time ?? '9999').localeCompare(b.ceremony_time ?? '9999'))
            .map((result) => <ClassCard key={result.category_id} result={result} />)
        )}
      </Stack>
    </TournamentLayout>
  );
}
