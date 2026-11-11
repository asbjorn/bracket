import { MantineProvider, createTheme } from '@mantine/core';
import '@mantine/core/styles.css';
import '@mantine/dates/styles.css';
import '@mantine/dropzone/styles.css';
import { Notifications } from '@mantine/notifications';
import '@mantine/notifications/styles.css';
import '@mantine/spotlight/styles.css';
import './components/print/print.css';
import { NuqsAdapter } from 'nuqs/adapters/react-router/v7';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { I18nextProvider } from 'react-i18next';
import { BrowserRouter, Route, Routes } from 'react-router';

import i18n from '../i18n';
import { BracketSpotlight } from './components/modals/spotlight';
import { LocalizedDatesProvider } from './components/utils/dates_provider';
import HomePage from './pages';
import NotFoundPage from './pages/404';
import CapacityPage from './pages/capacity';
import ScoreEntryPage from './pages/score';
import ClubsPage from './pages/clubs';
import CreateAccountPage from './pages/create_account';
import CreateDemoAccountPage from './pages/demo';
import LoginPage from './pages/login';
import PasswordResetPage from './pages/password_reset';
import DashboardSchedulePage from './pages/tournaments/[id]/dashboard';
import DashboardNotFoundPage from './pages/tournaments/[id]/dashboard/dashboard_404';
import CourtsPresentPage from './pages/tournaments/[id]/dashboard/present/courts';
import StandingsPresentPage from './pages/tournaments/[id]/dashboard/present/standings';
import DashboardStandingsPage from './pages/tournaments/[id]/dashboard/standings';
import DashboardCourtsPage from './pages/tournaments/[id]/dashboard/courts';
import DashboardPosterPage from './pages/tournaments/[id]/dashboard/poster';
import RotationPresentPage from './pages/tournaments/[id]/dashboard/present/rotation';
import DashboardRulesPage from './pages/tournaments/[id]/dashboard/rules';
import DashboardRegisterPage from './pages/tournaments/[id]/dashboard/register';
import DashboardTeamsPage from './pages/tournaments/[id]/dashboard/teams';
import DashboardTeamPage from './pages/tournaments/[id]/dashboard/teams/team';
import PlayersPage from './pages/tournaments/[id]/players';
import RankingsPage from './pages/tournaments/[id]/rankings';
import ResultsPage from './pages/tournaments/[id]/results';
import CeremonyPage from './pages/tournaments/[id]/ceremony';
import CategoriesPage from './pages/tournaments/[id]/categories';
import SchedulePage from './pages/tournaments/[id]/schedule';
import SettingsPage from './pages/tournaments/[id]/settings';
import CupSetupPage from './pages/tournaments/[id]/setup';
import DistrictApplicationPage from './pages/tournaments/[id]/application';
import DrawPage from './pages/tournaments/[id]/draw';
import RegistrationsPage from './pages/tournaments/[id]/registrations';
import OfficialsPage from './pages/tournaments/[id]/officials';
import DisciplinePage from './pages/tournaments/[id]/discipline';
import MatchCardsPage from './pages/tournaments/[id]/print/match_cards';
import StagesPage from './pages/tournaments/[id]/stages';
import SwissTournamentPage from './pages/tournaments/[id]/stages/swiss/[stage_item_id]';
import TeamsPage from './pages/tournaments/[id]/teams';
import ParticipatingClubsPage from './pages/tournaments/[id]/clubs';
import UserPage from './pages/user';

const theme = createTheme({
  colors: {
    dark: [
      '#C1C2C5',
      '#A6A7AB',
      '#909296',
      '#5c5f66',
      '#373A40',
      '#2C2E33',
      '#25262b',
      '#1A1B1E',
      '#141517',
      '#101113',
    ],
  },
});

function AnalyticsScript() {
  if (import.meta.env.VITE_ANALYTICS_SCRIPT_SRC == null) {
    return null;
  }

  var script = document.createElement('script');
  script.setAttribute('async', '');
  script.setAttribute('data-domain', import.meta.env.VITE_ANALYTICS_DATA_DOMAIN);
  script.setAttribute('data-website-id', import.meta.env.VITE_ANALYTICS_DATA_WEBSITE_ID);
  script.setAttribute('src', import.meta.env.VITE_ANALYTICS_SCRIPT_SRC);
  document.head.appendChild(script);
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <NuqsAdapter>
      <BrowserRouter>
        <I18nextProvider i18n={i18n}>
          <MantineProvider defaultColorScheme="auto" theme={theme}>
            <LocalizedDatesProvider>
              <BracketSpotlight />
              <Notifications />
              <Routes>
                <Route index element={<HomePage />} />
                <Route path="/login" element={<LoginPage />} />
                <Route path="/clubs" element={<ClubsPage />} />
                <Route path="/capacity" element={<CapacityPage />} />
                <Route path="/score/:token" element={<ScoreEntryPage />} />
                <Route path="/demo" element={<CreateDemoAccountPage />} />
                <Route path="/user" element={<UserPage />} />
                <Route path="/password-reset" element={<PasswordResetPage />} />
                <Route path="/create-account" element={<CreateAccountPage />} />

                <Route path="/tournaments">
                  <Route path=":id">
                    <Route path="players" element={<PlayersPage />} />
                    <Route path="categories" element={<CategoriesPage />} />
                    <Route path="teams" element={<TeamsPage />} />
                    <Route path="clubs" element={<ParticipatingClubsPage />} />
                    <Route path="schedule" element={<SchedulePage />} />
                    <Route path="rankings" element={<RankingsPage />} />
                    <Route path="settings" element={<SettingsPage />} />
                    <Route path="setup" element={<CupSetupPage />} />
                    <Route path="application" element={<DistrictApplicationPage />} />
                    <Route path="draw" element={<DrawPage />} />
                    <Route path="registrations" element={<RegistrationsPage />} />
                    <Route path="officials" element={<OfficialsPage />} />
                    <Route path="discipline" element={<DisciplinePage />} />
                    <Route path="print/match_cards" element={<MatchCardsPage />} />
                    <Route path="results" element={<ResultsPage />} />
                    <Route path="ceremony" element={<CeremonyPage />} />
                    <Route path="stages">
                      <Route index element={<StagesPage />} />
                      <Route path="swiss/:stage_item_id" element={<SwissTournamentPage />} />
                    </Route>
                    <Route path="dashboard">
                      <Route index element={<DashboardSchedulePage />} />
                      <Route path="standings" element={<DashboardStandingsPage />} />
                      <Route path="teams">
                        <Route index element={<DashboardTeamsPage />} />
                        <Route path=":team_id" element={<DashboardTeamPage />} />
                      </Route>
                      <Route path="courts" element={<DashboardCourtsPage />} />
                      <Route path="rules" element={<DashboardRulesPage />} />
                      <Route path="register" element={<DashboardRegisterPage />} />
                      <Route path="poster" element={<DashboardPosterPage />} />
                      <Route path="present">
                        <Route path="courts" element={<CourtsPresentPage />} />
                        <Route path="standings" element={<StandingsPresentPage />} />
                        <Route path="rotation" element={<RotationPresentPage />} />
                      </Route>
                      <Route path="*" element={<DashboardNotFoundPage />} />
                    </Route>
                  </Route>
                </Route>
                <Route path="*" element={<NotFoundPage />} />
              </Routes>
            </LocalizedDatesProvider>
          </MantineProvider>
        </I18nextProvider>
      </BrowserRouter>
    </NuqsAdapter>
  </StrictMode>,
);

AnalyticsScript();
