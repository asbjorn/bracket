import {
  Center,
  Container,
  Group,
  Image,
  ScrollArea,
  Skeleton,
  Title,
  UnstyledButton,
} from '@mantine/core';
import QRCode from 'react-qr-code';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router';

import { PublicNoticesBanner } from '@components/dashboard/public_notices';
import { HelpButton } from '@components/help/help_button';
import { HelpPageId } from '@components/help/help_content';
import PreloadLink from '@components/utils/link';
import { getOpenClasses } from '@services/registration';
import { getBaseURL } from '@components/utils/util';
import { Tournament } from '@openapi';
import { getBaseApiUrl } from '@services/adapter';
import classes from './layout.module.css';

export function TournamentQRCode({ tournamentDataFull }: { tournamentDataFull: Tournament }) {
  if (tournamentDataFull == null) {
    return null;
  }
  return (
    <div
      style={{
        width: '100%',
        background: 'white',
        marginTop: '2rem',
        maxWidth: '400px',
        height: 'auto',
        borderRadius: '16px',
        alignSelf: 'end',
      }}
    >
      <Center>
        <QRCode
          // Scales with its container: a fixed size plus a viewBox, then width 100%
          style={{ margin: '24px', height: 'auto', maxWidth: '100%', width: '100%' }}
          size={256}
          viewBox="0 0 256 256"
          value={`${getBaseURL()}/tournaments/${tournamentDataFull.dashboard_endpoint}/dashboard`}
        />
      </Center>
    </div>
  );
}

export function TournamentLogo({ tournamentDataFull }: { tournamentDataFull: Tournament }) {
  if (tournamentDataFull == null) {
    return <Skeleton height={150} radius="xl" mb="xl" />;
  }
  return tournamentDataFull.logo_path ? (
    <>
      <Image
        radius="lg"
        mt="1rem"
        alt="Logo of the tournament"
        src={`${getBaseApiUrl()}/static/tournament-logos/${tournamentDataFull.logo_path}`}
        style={{ maxWidth: '400px' }}
      />
    </>
  ) : null;
}

export function getTournamentHeadTitle(tournamentDataFull: Tournament) {
  return tournamentDataFull !== null ? `Bracket | ${tournamentDataFull.name}` : 'Bracket';
}

export function TournamentTitle({ tournamentDataFull }: { tournamentDataFull: Tournament }) {
  return tournamentDataFull != null ? (
    <Title>{tournamentDataFull.name}</Title>
  ) : (
    <Skeleton height={50} radius="lg" mb="xl" />
  );
}

/** The help that fits the tab of the public cup page that is open. */
function safeDecode(path: string): string {
  try {
    return decodeURIComponent(path);
  } catch {
    return path;
  }
}

function publicHelpPage(pathName: string, base: string): HelpPageId {
  const rest = pathName.slice(base.length);
  if (rest.startsWith('/register')) return 'public_register';
  if (/^\/teams\/[^/]+/.test(rest)) return 'public_team';
  if (rest.startsWith('/teams')) return 'public_teams';
  if (rest.startsWith('/courts')) return 'public_courts';
  if (rest.startsWith('/standings')) return 'public_standings';
  if (rest.startsWith('/rules')) return 'public_rules';
  return 'public_matches';
}

export function DoubleHeader({ tournamentData }: { tournamentData: Tournament }) {
  const { t } = useTranslation();
  const navigate = useLocation();
  const endpoint = tournamentData.dashboard_endpoint || '';
  // The browser encodes the address (spaces, æøå, ...), the cup's address is stored decoded
  const pathName = safeDecode(navigate.pathname).replace('[id]', endpoint).replace(/\/+$/, '');

  const base = `/tournaments/${endpoint}/dashboard`;
  const openClasses = getOpenClasses(tournamentData.id);
  const mainLinks = [
    { link: base, label: t('dashboard_matches_tab') },
    { link: `${base}/teams`, label: t('dashboard_teams_tab') },
    { link: `${base}/courts`, label: t('dashboard_courts_tab') },
    { link: `${base}/standings`, label: t('dashboard_standings_tab') },
    { link: `${base}/rules`, label: t('dashboard_rules_tab') },
  ];
  // The sign-up form only while a class is open for registration
  if ((openClasses.data?.data ?? []).length > 0 || pathName === `${base}/register`) {
    mainLinks.push({ link: `${base}/register`, label: t('dashboard_register_tab') });
  }

  const mainItems = mainLinks.map((item) => (
    <PreloadLink
      href={item.link}
      key={item.label}
      className={classes.mainLink}
      data-active={
        (item.link === base ? pathName === base : pathName.startsWith(item.link)) || undefined
      }
    >
      {item.label}
    </PreloadLink>
  ));

  return (
    <>
      <header className={classes.header}>
        <Container className={classes.inner}>
          <Group gap="xs" wrap="nowrap" style={{ minWidth: 0 }}>
            <UnstyledButton component={PreloadLink} href={base} style={{ minWidth: 0 }}>
              <Title size="lg" lineClamp={1}>
                {tournamentData.name}
              </Title>
            </UnstyledButton>
            <HelpButton page={publicHelpPage(pathName, base)} />
          </Group>
          <ScrollArea type="never" className={classes.links}>
            <Group gap={0} wrap="nowrap" className={classes.mainLinks}>
              {mainItems}
            </Group>
          </ScrollArea>
        </Container>
      </header>
      <Container className="print-only">
        <Title order={2}>{tournamentData.name}</Title>
      </Container>
      <Container className="no-print">
        <PublicNoticesBanner tournamentId={tournamentData.id} />
      </Container>
    </>
  );
}
