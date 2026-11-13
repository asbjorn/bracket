import { Card, Group, SimpleGrid, Text } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import { ProgressRing } from '@components/builder/group_board';
import { Category, StageWithStageItems } from '@openapi';

/** Per class: how many of its matches are played, as rings that fill up during the cup. */
export default function ClassProgress({
  stages,
  categories,
}: {
  stages: StageWithStageItems[];
  categories: Category[];
}) {
  const { t } = useTranslation();
  const rows = [...categories]
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((category) => {
      const matches = stages
        .filter((stage) => stage.category_id === category.id)
        .flatMap((stage) =>
          stage.stage_items.flatMap((item) => item.rounds.flatMap((round) => round.matches)),
        );
      return {
        category,
        played: matches.filter((match) => match.played).length,
        total: matches.length,
      };
    })
    .filter((row) => row.total > 0);
  if (rows.length < 1) return null;

  return (
    <SimpleGrid cols={{ base: 2, sm: 3, md: 5 }} spacing="sm" mb="md">
      {rows.map(({ category, played, total }) => (
        <Card key={category.id} withBorder padding="sm" radius="md">
          <Group gap="sm" wrap="nowrap">
            <ProgressRing played={played} total={total} />
            <div style={{ minWidth: 0 }}>
              <Text fw={700} truncate>
                {category.name}
              </Text>
              <Text size="xs" c="dimmed">
                {t('class_progress_played', { played, total })}
              </Text>
            </div>
          </Group>
        </Card>
      ))}
    </SimpleGrid>
  );
}
