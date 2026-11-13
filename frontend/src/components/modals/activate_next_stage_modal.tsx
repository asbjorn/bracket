import { Alert, Button, Container, Grid, Modal, Title } from '@mantine/core';
import { useForm } from '@mantine/form';
import { FaArrowRight } from '@react-icons/all-files/fa/FaArrowRight';
import { IconAlertCircle, IconSquareArrowRight } from '@tabler/icons-react';
import { Fragment, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { SWRResponse } from 'swr';

import RequestErrorAlert from '@components/utils/error_alert';
import { GenericSkeleton } from '@components/utils/skeletons';
import { formatStageItemInput } from '@components/utils/stage_item_input';
import { StageItemInputUpdate, StageRankingResponse, StagesWithStageItemsResponse } from '@openapi';
import { getStageItemLookup } from '@services/lookups';
import { activateNextStage } from '@services/stage';

function UpdatesToStageItemInputsTable({
  stageItemsLookup,
  updates,
}: {
  stageItemsLookup: any;
  updates: StageItemInputUpdate[];
}) {
  return updates
    .sort((si1, si2) => (si1.stage_item_input.slot > si2.stage_item_input.slot ? 1 : -1))
    .map((update) => (
      <Grid key={update.stage_item_input.id}>
        <Grid.Col span={{ sm: 6 }}>
          {formatStageItemInput(update.stage_item_input, stageItemsLookup)}
        </Grid.Col>
        <Grid.Col span={{ sm: 6 }}>
          <FaArrowRight style={{ marginRight: '0.5rem' }} />
          {update.team?.name}
        </Grid.Col>
      </Grid>
    ));
}

function UpdatesToStageItemInputsTables({
  stageItemsLookup,
  swrRankingsPerStageItemResponse,
}: {
  stageItemsLookup: any;
  swrRankingsPerStageItemResponse: SWRResponse<StageRankingResponse>;
}) {
  if (swrRankingsPerStageItemResponse.isLoading) {
    return <GenericSkeleton />;
  }
  if (swrRankingsPerStageItemResponse.error) {
    return <RequestErrorAlert error={swrRankingsPerStageItemResponse.error} />;
  }

  const items = swrRankingsPerStageItemResponse.data?.data || {};
  return Object.keys(items)
    .map((stageItemId) => ({
      updates: items[stageItemId],
      stageItem: stageItemsLookup[stageItemId],
    }))
    .filter((item) => item.stageItem != null)
    .sort((si1, si2) => (si1.stageItem.name > si2.stageItem.name ? 1 : -1))
    .map((item) => (
      <Fragment key={item.stageItem.id}>
        <Title size="h2" mt="1rem">
          {item.stageItem.name}
        </Title>
        <UpdatesToStageItemInputsTable updates={item.updates} stageItemsLookup={stageItemsLookup} />
      </Fragment>
    ));
}

export default function ActivateNextStageModal({
  tournamentId,
  categoryId,
  swrStagesResponse,
  swrRankingsPerStageItemResponse,
  opened: openedProp,
  onClose,
}: {
  tournamentId: number;
  categoryId: number | null;
  swrStagesResponse: SWRResponse<StagesWithStageItemsResponse>;
  swrRankingsPerStageItemResponse: SWRResponse<StageRankingResponse>;
  // Controlled from outside (e.g. a menu): no button of its own
  opened?: boolean;
  onClose?: () => void;
}) {
  const { t } = useTranslation();
  const [openedState, setOpenedState] = useState(false);
  const controlled = openedProp !== undefined;
  const opened = controlled ? openedProp : openedState;
  const setOpened = (value: boolean) => {
    if (controlled) {
      if (!value) onClose?.();
    } else setOpenedState(value);
  };
  const stageItemsLookup = getStageItemLookup(swrStagesResponse);
  const hasUpdates = Object.values(swrRankingsPerStageItemResponse.data?.data ?? {}).some(
    (updates) => updates.length > 0,
  );

  const form = useForm({
    initialValues: {},
  });

  return (
    <>
      <Modal
        opened={opened}
        onClose={() => setOpened(false)}
        title={t('active_next_stage_modal_title')}
        size="40rem"
      >
        <form
          onSubmit={form.onSubmit(async () => {
            await activateNextStage(tournamentId, 'next', categoryId);
            swrStagesResponse.mutate();
            setOpened(false);
          })}
        >
          <Alert icon={<IconAlertCircle size={16} />} color="gray" radius="lg">
            {/* Only promise that teams are placed when the next stage takes teams from this one */}
            {hasUpdates
              ? t('active_next_stage_modal_description')
              : t('active_next_stage_modal_description_no_updates')}
          </Alert>

          <Container mt="1rem">
            <UpdatesToStageItemInputsTables
              swrRankingsPerStageItemResponse={swrRankingsPerStageItemResponse}
              stageItemsLookup={stageItemsLookup}
            />
          </Container>

          <Button
            fullWidth
            color="indigo"
            size="md"
            mt="lg"
            type="submit"
            leftSection={<IconSquareArrowRight size={24} />}
          >
            {t('plan_next_stage_button')}
          </Button>
        </form>
      </Modal>

      {controlled ? null : (
        <Button
          size="md"
          mb="10"
          color="indigo"
          leftSection={<IconSquareArrowRight size={24} />}
          onClick={async () => {
            setOpened(true);
          }}
        >
          {t('next_stage_button')}
        </Button>
      )}
    </>
  );
}
