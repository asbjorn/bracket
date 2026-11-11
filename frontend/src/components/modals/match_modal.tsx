import {
  Alert,
  Button,
  Center,
  Checkbox,
  Divider,
  Grid,
  Modal,
  NumberInput,
  Select,
  Switch,
  Text,
} from '@mantine/core';
import { IconInfoCircle } from '@tabler/icons-react';
import { useForm } from '@mantine/form';
import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { SWRResponse } from 'swr';

import DeleteButton from '@components/buttons/delete';
import { CardsEditor, SuspendedAlert } from '@components/discipline/cards_editor';
import { formatMatchInput1, formatMatchInput2 } from '@components/utils/match';
import { TournamentMinimal } from '@components/utils/tournament';
import {
  MatchResultType,
  MatchWithDetails,
  RoundWithMatches,
  StagesWithStageItemsResponse,
} from '@openapi';
import { getCategories, requestSucceeded } from '@services/adapter';
import {
  categoryOfStageItem,
  createCard,
  deleteCard,
  disciplineAllowed,
  getDiscipline,
} from '@services/discipline';
import { getMatchLookup, getStageItemLookup } from '@services/lookups';
import { deleteMatch, giveWalkover, updateMatch } from '@services/match';
import { setMatchStarted } from '@services/planning';

const RESULT_TYPES: MatchResultType[] = ['NORMAL', 'EXTRA_TIME', 'PENALTIES', 'WALKOVER'];

function MatchDeleteButton({
  tournamentData,
  match,
  swrStagesResponse,
  swrUpcomingMatchesResponse,
}: {
  tournamentData: TournamentMinimal;
  match: MatchWithDetails;
  swrStagesResponse: SWRResponse<StagesWithStageItemsResponse>;
  swrUpcomingMatchesResponse: SWRResponse | null;
}) {
  const { t } = useTranslation();
  return (
    <DeleteButton
      fullWidth
      onClick={async () => {
        await deleteMatch(tournamentData.id, match.id);
        await swrStagesResponse.mutate();
        if (swrUpcomingMatchesResponse != null) await swrUpcomingMatchesResponse.mutate();
      }}
      style={{ marginTop: '1rem' }}
      size="sm"
      title={t('remove_match_button')}
    />
  );
}

function MatchModalForm({
  tournamentData,
  match,
  swrStagesResponse,
  swrUpcomingMatchesResponse,
  setOpened,
  round,
}: {
  tournamentData: TournamentMinimal;
  match: MatchWithDetails;
  swrStagesResponse: SWRResponse<StagesWithStageItemsResponse>;
  swrUpcomingMatchesResponse: SWRResponse | null;
  setOpened: any;
  round: RoundWithMatches | null;
}) {
  const { t } = useTranslation();
  const form = useForm({
    initialValues: {
      stage_item_input1_score: match.stage_item_input1_score,
      stage_item_input2_score: match.stage_item_input2_score,
      custom_duration_minutes: match.custom_duration_minutes,
      custom_margin_minutes: match.custom_margin_minutes,
      result_type: match.result_type,
      stage_item_input1_penalties: match.stage_item_input1_penalties ?? '',
      stage_item_input2_penalties: match.stage_item_input2_penalties ?? '',
    },

    validate: {
      stage_item_input1_score: (value) => (value >= 0 ? null : t('negative_score_validation')),
      stage_item_input2_score: (value) => (value >= 0 ? null : t('negative_score_validation')),
      custom_duration_minutes: (value) =>
        value == null || value >= 0 ? null : t('negative_match_duration_validation'),
      custom_margin_minutes: (value) =>
        value == null || value >= 0 ? null : t('negative_match_margin_validation'),
      result_type: (value, values) =>
        value === 'PENALTIES' && values.stage_item_input1_score !== values.stage_item_input2_score
          ? t('penalties_require_draw_validation')
          : null,
      stage_item_input1_penalties: (value, values) =>
        values.result_type === 'PENALTIES' && value === ''
          ? t('penalties_required_validation')
          : null,
      stage_item_input2_penalties: (value, values) =>
        values.result_type !== 'PENALTIES'
          ? null
          : value === ''
            ? t('penalties_required_validation')
            : value === values.stage_item_input1_penalties
              ? t('penalties_need_winner_validation')
              : null,
    },
  });

  // The match passed in is a snapshot: keep the kick-off state here
  const [started, setStarted] = useState(match.started_at != null);
  const [customDurationEnabled, setCustomDurationEnabled] = useState(
    match.custom_duration_minutes != null,
  );
  const [customMarginEnabled, setCustomMarginEnabled] = useState(
    match.custom_margin_minutes != null,
  );

  const stageItemsLookup = getStageItemLookup(swrStagesResponse);
  const matchesLookup = getMatchLookup(swrStagesResponse);
  const categories = getCategories(tournamentData.id).data?.data ?? [];
  const swrDiscipline = getDiscipline(tournamentData.id);

  const team1Name = formatMatchInput1(t, stageItemsLookup, matchesLookup, match);
  const team2Name = formatMatchInput2(t, stageItemsLookup, matchesLookup, match);
  const isShootout = form.getValues().result_type === 'PENALTIES';
  const teamIdOf = (input: MatchWithDetails['stage_item_input1']) =>
    input != null && 'team' in input && input.team != null ? input.team.id : null;
  const walkoverWinners = [
    { teamId: teamIdOf(match.stage_item_input1), name: team1Name },
    { teamId: teamIdOf(match.stage_item_input2), name: team2Name },
  ];
  const canGiveWalkover = walkoverWinners.every((winner) => winner.teamId != null);
  const matchTeams = walkoverWinners.map((winner) => ({
    id: winner.teamId as number,
    name: winner.name,
  }));
  // Cards only for classes from 13 years with public results (NFF)
  const stageItemId = matchesLookup[match.id]?.stageItem?.id;
  const matchCategory =
    stageItemId != null
      ? categoryOfStageItem(swrStagesResponse.data?.data ?? [], categories, stageItemId)
      : null;
  // Children's football (results hidden): the match is only marked as played
  const hiddenResults = matchCategory != null && !matchCategory.results_public;
  const allowsCards =
    stageItemId != null &&
    disciplineAllowed(
      categoryOfStageItem(swrStagesResponse.data?.data ?? [], categories, stageItemId),
    );
  const suspendedHere = (swrDiscipline.data?.data.suspensions ?? [])
    .filter((suspension) => suspension.match_ids.includes(match.id))
    .map((suspension) => ({
      team_id: suspension.team_id,
      player_name: suspension.player_name,
    }));

  async function walkover(winnerTeamId: number) {
    const result = await giveWalkover(tournamentData.id, match.id, winnerTeamId);
    if (result == null) return;
    await swrStagesResponse.mutate();
    if (swrUpcomingMatchesResponse != null) await swrUpcomingMatchesResponse.mutate();
    setOpened(false);
  }
  // Set by the button that submits the form: a live score doesn't count yet, a final result does
  const saveAsFinalResult = useRef(true);

  return (
    <>
      <form
        onSubmit={form.onSubmit(async (values) => {
          const updatedMatch = {
            id: match.id,
            round_id: match.round_id,
            stage_item_input1_score: values.stage_item_input1_score,
            stage_item_input2_score: values.stage_item_input2_score,
            court_id: match.court_id || null,
            custom_duration_minutes: customDurationEnabled ? values.custom_duration_minutes : null,
            custom_margin_minutes: customMarginEnabled ? values.custom_margin_minutes : null,
            played: saveAsFinalResult.current,
            result_type: values.result_type,
            stage_item_input1_penalties: isShootout
              ? Number(values.stage_item_input1_penalties)
              : null,
            stage_item_input2_penalties: isShootout
              ? Number(values.stage_item_input2_penalties)
              : null,
          };
          const result = await updateMatch(tournamentData.id, match.id, updatedMatch);
          // Keep the form open when the server rejected the result (an error is shown)
          if (result == null) return;
          await swrStagesResponse.mutate();
          if (swrUpcomingMatchesResponse != null) await swrUpcomingMatchesResponse.mutate();
          setOpened(false);
        })}
      >
        {hiddenResults ? (
          <Alert color="gray" icon={<IconInfoCircle />}>
            {t('match_hidden_results_description')}
          </Alert>
        ) : (
          <>
            <NumberInput
              withAsterisk
              label={`${t('score_of_label')} ${team1Name}`}
              placeholder={`${t('score_of_label')} ${team1Name}`}
              {...form.getInputProps('stage_item_input1_score')}
              onChange={(value) => form.setFieldValue('stage_item_input1_score', Number(value))}
            />
            <NumberInput
              withAsterisk
              mt="lg"
              label={`${t('score_of_label')} ${team2Name}`}
              placeholder={`${t('score_of_label')} ${team2Name}`}
              {...form.getInputProps('stage_item_input2_score')}
              onChange={(value) => form.setFieldValue('stage_item_input2_score', Number(value))}
            />
            <Select
              mt="lg"
              label={t('result_type_label')}
              data={RESULT_TYPES.map((resultType) => ({
                value: resultType,
                label: t(`result_type_${resultType.toLowerCase()}`),
              }))}
              allowDeselect={false}
              {...form.getInputProps('result_type')}
            />
            {isShootout ? (
              <Grid mt="xs">
                <Grid.Col span={6}>
                  <NumberInput
                    min={0}
                    label={`${t('penalties_of_label')} ${team1Name}`}
                    {...form.getInputProps('stage_item_input1_penalties')}
                  />
                </Grid.Col>
                <Grid.Col span={6}>
                  <NumberInput
                    min={0}
                    label={`${t('penalties_of_label')} ${team2Name}`}
                    {...form.getInputProps('stage_item_input2_penalties')}
                  />
                </Grid.Col>
              </Grid>
            ) : null}
          </>
        )}
        {!match.played ? (
          <Switch
            mt="lg"
            label={t('match_started_label')}
            description={t('match_started_description')}
            checked={started}
            onChange={async (event) => {
              const checked = event.currentTarget.checked;
              const result = await setMatchStarted(tournamentData.id, match.id, checked);
              if (requestSucceeded(result)) {
                setStarted(checked);
                await swrStagesResponse.mutate();
              }
            }}
          />
        ) : null}
        {canGiveWalkover ? (
          <>
            <Text size="sm" mt="lg">
              {t('walkover_winner_label')}
            </Text>
            <Grid mt="xs">
              {walkoverWinners.map((winner) => (
                <Grid.Col key={winner.teamId} span={{ base: 12, sm: 6 }}>
                  <Button
                    fullWidth
                    variant="default"
                    onClick={() => walkover(winner.teamId as number)}
                  >
                    {t('walkover_winner_button', { team: winner.name })}
                  </Button>
                </Grid.Col>
              ))}
            </Grid>
          </>
        ) : null}
        <Divider mt="lg" />

        <Text size="sm" mt="lg">
          {t('custom_match_duration_label')}
        </Text>
        <Grid align="center">
          <Grid.Col span={{ sm: 8 }}>
            <NumberInput
              disabled={!customDurationEnabled}
              rightSection={<Text>{t('minutes')}</Text>}
              placeholder={`${match.duration_minutes}`}
              rightSectionWidth={92}
              {...form.getInputProps('custom_duration_minutes')}
            />
          </Grid.Col>
          <Grid.Col span={{ sm: 4 }}>
            <Center>
              <Checkbox
                checked={customDurationEnabled}
                label={t('customize_checkbox_label')}
                onChange={(event) => {
                  setCustomDurationEnabled(event.currentTarget.checked);
                }}
              />
            </Center>
          </Grid.Col>
        </Grid>

        <Text size="sm" mt="lg">
          {t('custom_match_margin_label')}
        </Text>
        <Grid align="center">
          <Grid.Col span={{ sm: 8 }}>
            <NumberInput
              disabled={!customMarginEnabled}
              placeholder={`${match.margin_minutes}`}
              rightSection={<Text>{t('minutes')}</Text>}
              rightSectionWidth={92}
              {...form.getInputProps('custom_margin_minutes')}
            />
          </Grid.Col>
          <Grid.Col span={{ sm: 4 }}>
            <Center>
              <Checkbox
                checked={customMarginEnabled}
                label={t('customize_checkbox_label')}
                onChange={(event) => {
                  setCustomMarginEnabled(event.currentTarget.checked);
                }}
              />
            </Center>
          </Grid.Col>
        </Grid>

        {hiddenResults ? (
          <Grid mt="lg">
            <Grid.Col span={{ base: 12, sm: 6 }}>
              <Button
                fullWidth
                variant="default"
                type="submit"
                onClick={() => {
                  saveAsFinalResult.current = false;
                }}
              >
                {t('score_not_played_button')}
              </Button>
            </Grid.Col>
            <Grid.Col span={{ base: 12, sm: 6 }}>
              <Button
                fullWidth
                color="green"
                type="submit"
                onClick={() => {
                  saveAsFinalResult.current = true;
                }}
              >
                {t('score_played_button')}
              </Button>
            </Grid.Col>
          </Grid>
        ) : null}
        <Text size="sm" c="dimmed" mt="lg" display={hiddenResults ? 'none' : undefined}>
          {t('save_result_description')}
        </Text>
        <Grid mt="xs" display={hiddenResults ? 'none' : undefined}>
          <Grid.Col span={{ base: 12, sm: 6 }}>
            <Button
              fullWidth
              variant="light"
              color="grape"
              type="submit"
              onClick={() => {
                saveAsFinalResult.current = false;
              }}
            >
              {t('save_live_score_button')}
            </Button>
          </Grid.Col>
          <Grid.Col span={{ base: 12, sm: 6 }}>
            <Button
              fullWidth
              color="green"
              type="submit"
              onClick={() => {
                saveAsFinalResult.current = true;
              }}
            >
              {t('save_final_result_button')}
            </Button>
          </Grid.Col>
        </Grid>
      </form>
      {canGiveWalkover && allowsCards ? (
        <>
          <Divider mt="lg" />
          <Text fw={500} mt="lg" mb="xs">
            {t('cards_title')}
          </Text>
          <SuspendedAlert suspended={suspendedHere} teams={matchTeams} />
          <CardsEditor
            cards={(swrDiscipline.data?.data.cards ?? []).filter((c) => c.match_id === match.id)}
            teams={matchTeams}
            onAdd={async (body) => {
              const response = await createCard(tournamentData.id, match.id, body);
              await swrDiscipline.mutate();
              return response;
            }}
            onDelete={async (cardId) => {
              await deleteCard(tournamentData.id, cardId);
              await swrDiscipline.mutate();
            }}
          />
        </>
      ) : null}
      {round && round.is_draft && (
        <MatchDeleteButton
          swrStagesResponse={swrStagesResponse}
          swrUpcomingMatchesResponse={swrUpcomingMatchesResponse}
          tournamentData={tournamentData}
          match={match}
        />
      )}
    </>
  );
}

export default function MatchModal({
  tournamentData,
  match,
  swrStagesResponse,
  swrUpcomingMatchesResponse,
  opened,
  setOpened,
  round,
}: {
  tournamentData: TournamentMinimal;
  match: MatchWithDetails | null;
  swrStagesResponse: SWRResponse<StagesWithStageItemsResponse>;
  swrUpcomingMatchesResponse: SWRResponse | null;
  opened: boolean;
  setOpened: any;
  round: RoundWithMatches | null;
}) {
  const { t } = useTranslation();

  return (
    <>
      <Modal opened={opened} onClose={() => setOpened(false)} title={t('edit_match_modal_title')}>
        {/* Keyed by match: hooks and form state start fresh for every match */}
        {match != null ? (
          <MatchModalForm
            key={match.id}
            swrStagesResponse={swrStagesResponse}
            swrUpcomingMatchesResponse={swrUpcomingMatchesResponse}
            tournamentData={tournamentData}
            match={match}
            setOpened={setOpened}
            round={round}
          />
        ) : null}
      </Modal>
    </>
  );
}
