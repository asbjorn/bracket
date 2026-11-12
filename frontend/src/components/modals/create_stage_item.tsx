import {
  Button,
  Card,
  Checkbox,
  Divider,
  Grid,
  Image,
  Modal,
  NumberInput,
  Text,
  UnstyledButton,
} from '@mantine/core';
import { UseFormReturnType, useForm } from '@mantine/form';
import { GoPlus } from '@react-icons/all-files/go/GoPlus';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { SWRResponse } from 'swr';

import { TitleWithHelp } from '@components/help/help_button';
import { Translator } from '@components/utils/types';
import {
  StageItemInputOptionsResponse,
  StageWithStageItems,
  StagesWithStageItemsResponse,
  Tournament,
} from '@openapi';
import { getStageItemLookup, getTeamsLookup } from '@services/lookups';
import { createStageItem } from '@services/stage_item';
import classes from './create_stage_item.module.css';

function StageSelectCard({
  title,
  description,
  image,
  selected,
  onClick,
}: {
  title: string;
  description: string;
  image: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <UnstyledButton onClick={onClick} w="100%">
      <Card
        shadow="sm"
        padding="lg"
        radius="lg"
        h="23rem"
        withBorder
        className={classes.socialLink}
        style={{ border: selected ? '3px solid var(--mantine-color-green-7)' : '' }}
      >
        <Card.Section style={{ backgroundColor: '#dde' }}>
          <Image src={image} h={212} style={{ padding: '1.5rem' }} fit="fill"></Image>
        </Card.Section>

        <Text fw={800} size="xl" mt="md" lineClamp={1}>
          {title}
        </Text>

        <Text mt="xs" c="dimmed" size="md" lineClamp={3}>
          {description}
        </Text>
      </Card>
    </UnstyledButton>
  );
}

export function CreateStagesFromTemplateButtons({
  selectedType,
  setSelectedType,
  t,
}: {
  selectedType: 'ROUND_ROBIN' | 'SWISS' | 'SINGLE_ELIMINATION';
  setSelectedType: (type: 'ROUND_ROBIN' | 'SWISS' | 'SINGLE_ELIMINATION') => void;
  t: Translator;
}) {
  return (
    <Grid grow>
      <Grid.Col span={{ base: 12, sm: 6 }}>
        <StageSelectCard
          title={t('round_robin_label')}
          description={t('round_robin_description')}
          image="/icons/group-stage-item.svg"
          selected={selectedType === 'ROUND_ROBIN'}
          onClick={() => {
            setSelectedType('ROUND_ROBIN');
          }}
        />
      </Grid.Col>
      <Grid.Col span={{ base: 12, sm: 6 }}>
        <StageSelectCard
          title={t('single_elimination_label')}
          description={t('single_elimination_description')}
          image="/icons/single-elimination-stage-item.svg"
          selected={selectedType === 'SINGLE_ELIMINATION'}
          onClick={() => {
            setSelectedType('SINGLE_ELIMINATION');
          }}
        />
      </Grid.Col>
      {/* Swiss system is supported by the backend but not offered: football cups use groups and knockouts */}
    </Grid>
  );
}

function TeamCountSelectElimination({ form }: { form: UseFormReturnType<any> }) {
  const { t } = useTranslation();
  const teamCount = Number(form.values.team_count_elimination);
  return (
    <>
      <NumberInput
        withAsterisk
        label={t('team_count_select_elimination_label')}
        description={t('team_count_elimination_description')}
        min={2}
        max={64}
        allowDecimal={false}
        mt="1rem"
        maw="50%"
        {...form.getInputProps('team_count_elimination')}
      />
      <Checkbox
        mt="md"
        disabled={teamCount < 4}
        label={t('third_place_match_label')}
        description={t('third_place_match_description')}
        {...form.getInputProps('third_place_match', { type: 'checkbox' })}
      />
    </>
  );
}

function TeamCountInputRoundRobin({ form }: { form: UseFormReturnType<any> }) {
  const { t } = useTranslation();
  return (
    <NumberInput
      withAsterisk
      label={t('team_count_input_round_robin_label')}
      placeholder=""
      mt="1rem"
      maw="50%"
      {...form.getInputProps('team_count_round_robin')}
    />
  );
}

function TeamCountInput({ form }: { form: UseFormReturnType<any> }) {
  if (form.values.type === 'SINGLE_ELIMINATION') {
    return <TeamCountSelectElimination form={form} />;
  }

  return <TeamCountInputRoundRobin form={form} />;
}

function getTeamCount(values: any) {
  return Number(
    values.type === 'SINGLE_ELIMINATION'
      ? values.team_count_elimination
      : values.team_count_round_robin,
  );
}

interface FormValues {
  type: 'ROUND_ROBIN' | 'SWISS' | 'SINGLE_ELIMINATION';
  team_count_round_robin: number;
  team_count_elimination: number;
  third_place_match: boolean;
}
export function CreateStageItemModal({
  tournament,
  stage,
  swrStagesResponse,
  swrAvailableInputsResponse,
}: {
  tournament: Tournament;
  stage: StageWithStageItems;
  swrStagesResponse: SWRResponse<StagesWithStageItemsResponse>;
  swrAvailableInputsResponse: SWRResponse<StageItemInputOptionsResponse>;
}) {
  const { t } = useTranslation();
  const [opened, setOpened] = useState(false);

  const form = useForm<FormValues>({
    initialValues: {
      type: 'ROUND_ROBIN',
      team_count_round_robin: 4,
      team_count_elimination: 4,
      third_place_match: false,
    },
    validate: {
      team_count_round_robin: (value) => (value >= 2 ? null : t('at_least_two_team_validation')),
      team_count_elimination: (value) =>
        value >= 2 && value <= 64 ? null : t('team_count_elimination_validation'),
    },
  });

  // TODO: Refactor lookups into one request.
  const teamsMap = getTeamsLookup(tournament != null ? tournament.id : -1);
  const stageItemMap = getStageItemLookup(swrStagesResponse);

  if (teamsMap == null || stageItemMap == null) {
    return null;
  }

  return (
    <>
      <Modal
        opened={opened}
        onClose={() => setOpened(false)}
        title={<TitleWithHelp help="stage_item">{t('add_stage_item_modal_title')}</TitleWithHelp>}
        size="60rem"
      >
        <form
          onSubmit={form.onSubmit(async (values) => {
            await createStageItem(
              tournament.id,
              stage.id,
              values.type,
              getTeamCount(values),
              values.type === 'SINGLE_ELIMINATION' &&
                values.third_place_match &&
                getTeamCount(values) >= 4,
            );
            await swrStagesResponse.mutate();
            await swrAvailableInputsResponse.mutate();
            setOpened(false);
          })}
        >
          <CreateStagesFromTemplateButtons
            t={t}
            selectedType={form.values.type}
            setSelectedType={(_type) => {
              form.setFieldValue('type', _type);
            }}
          />
          <Divider mt="1rem" />
          <TeamCountInput form={form} />

          <Button fullWidth mt="1.5rem" color="green" type="submit">
            {t('create_stage_item_button')}
          </Button>
        </form>
      </Modal>

      <Button
        variant="outline"
        color="green"
        size="xs"
        onClick={() => setOpened(true)}
        leftSection={<GoPlus size={24} />}
      >
        {t('add_stage_item_modal_title')}
      </Button>
    </>
  );
}
