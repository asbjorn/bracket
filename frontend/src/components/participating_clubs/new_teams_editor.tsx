import { Group, NumberInput, Stack, Table, Text, TextInput } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import { Category } from '@openapi';

export const MAX_TEAM_NAME = 50;
const MAX_NEW_PER_CLASS = 20;

/**
 * New teams of a club, by number per class: the rows appear as soon as a number is chosen
 * (nothing to "add"), with suggested names that can be edited.
 */
export interface NewTeamsState {
  counts: Record<number, number>;
  // Edited names by "classId:index"
  names: Record<string, string>;
}

export const EMPTY_NEW_TEAMS: NewTeamsState = { counts: {}, names: {} };

export interface NewTeam {
  name: string;
  categoryId: number;
}

/** "Brann" and "Brann 2" belong to the club Brann; "Brannfjell" doesn't. */
export function looksLikeClubTeam(teamName: string, clubName: string) {
  const team = teamName.trim().toLowerCase();
  const club = clubName.trim().toLowerCase();
  return club !== '' && (team === club || team.startsWith(`${club} `));
}

/**
 * Names for `count` new teams of a club in a class, after the `existing` teams it has there.
 * With teams in several classes the class goes in the name ("Gneist G9", "Gneist J13 2"), so
 * teams can be told apart everywhere; one team in a class gets no number.
 */
export function suggestTeamNames(
  clubName: string,
  className: string | null,
  count: number,
  existing: number,
  withClass: boolean,
) {
  const base = withClass && className ? `${clubName.trim()} ${className}` : clubName.trim();
  if (existing === 0 && count === 1) return [base];
  return Array.from({ length: count }, (_, index) => `${base} ${existing + index + 1}`);
}

export function newTeamsOf(
  state: NewTeamsState,
  clubName: string,
  categories: Category[],
  existingPerClass: Record<number, number>,
): NewTeam[] {
  const classesUsed = categories.filter(
    (c) => (state.counts[c.id] ?? 0) > 0 || (existingPerClass[c.id] ?? 0) > 0,
  ).length;
  return categories.flatMap((category) => {
    const count = state.counts[category.id] ?? 0;
    return suggestTeamNames(
      clubName,
      category.name,
      count,
      existingPerClass[category.id] ?? 0,
      classesUsed > 1,
    ).map((suggested, index) => ({
      name: state.names[`${category.id}:${index}`] ?? suggested,
      categoryId: category.id,
    }));
  });
}

export function newTeamError(name: string): 'empty' | 'long' | null {
  if (name.trim() === '') return 'empty';
  if (name.trim().length > MAX_TEAM_NAME) return 'long';
  return null;
}

export default function NewTeamsEditor({
  value,
  onChange,
  clubName,
  categories,
  existingPerClass,
}: {
  value: NewTeamsState;
  onChange: (value: NewTeamsState) => void;
  clubName: string;
  categories: Category[];
  existingPerClass: Record<number, number>;
}) {
  const { t } = useTranslation();
  const teams = newTeamsOf(value, clubName, categories, existingPerClass);
  return (
    <Stack gap="xs">
      <Group gap="md">
        {categories.map((category) => (
          <NumberInput
            key={category.id}
            label={category.name}
            value={value.counts[category.id] ?? 0}
            min={0}
            max={MAX_NEW_PER_CLASS}
            w="7rem"
            onChange={(input) =>
              onChange({
                ...value,
                counts: { ...value.counts, [category.id]: Math.max(0, Number(input) || 0) },
              })
            }
          />
        ))}
      </Group>
      {teams.length > 0 ? (
        <Table>
          <Table.Tbody>
            {categories.flatMap((category) =>
              teams
                .filter((team) => team.categoryId === category.id)
                .map((team, index) => {
                  const error = newTeamError(team.name);
                  return (
                    <Table.Tr key={`${category.id}:${index}`}>
                      <Table.Td w="5rem">
                        <Text size="sm" fw={500}>
                          {category.name}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        <TextInput
                          value={team.name}
                          aria-label={t('name_input_label')}
                          maxLength={MAX_TEAM_NAME + 10}
                          error={
                            error === 'empty'
                              ? t('too_short_name_validation')
                              : error === 'long'
                                ? t('club_wizard_name_too_long', { max: MAX_TEAM_NAME })
                                : null
                          }
                          rightSection={
                            <Text size="xs" c="dimmed">
                              {team.name.trim().length}
                            </Text>
                          }
                          rightSectionWidth="2.5rem"
                          onChange={(event) =>
                            onChange({
                              ...value,
                              names: {
                                ...value.names,
                                [`${category.id}:${index}`]: event.currentTarget.value,
                              },
                            })
                          }
                        />
                      </Table.Td>
                    </Table.Tr>
                  );
                }),
            )}
          </Table.Tbody>
        </Table>
      ) : null}
    </Stack>
  );
}
