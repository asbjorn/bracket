import { Container, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import classes from '@pages/404.module.css';

export default function GenericErrorPage() {
  const { t } = useTranslation();
  return (
    <Container className={classes.root}>
      <div className={classes.label}>500</div>
      <Title className={classes.title}>{t('unknown_error_title')}</Title>
      <Text c="dimmed" size="lg" ta="center" className={classes.description}></Text>
    </Container>
  );
}
