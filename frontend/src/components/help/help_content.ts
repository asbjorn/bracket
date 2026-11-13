// The help of every page. Texts are i18n keys by convention (help_<page>_intro,
// help_<page>_step_<n>, help_<page>_field_<id> and _text, help_<page>_action_<id> and _text,
// help_<page>_tip_<n>, help_<page>_title); this registry only says which exist.

export type HelpPageId =
  | 'tournaments'
  | 'organiser_clubs'
  | 'capacity'
  | 'user'
  | 'overview'
  | 'setup'
  | 'categories'
  | 'teams'
  | 'team_edit'
  | 'players'
  | 'clubs'
  | 'club_wizard'
  | 'registrations'
  | 'draw'
  | 'stages'
  | 'stage_item'
  | 'playoffs'
  | 'schedule'
  | 'officials'
  | 'results'
  | 'match_edit'
  | 'discipline'
  | 'rankings'
  | 'ceremony'
  | 'settings'
  | 'application'
  | 'match_cards'
  | 'pitch'
  | 'public_matches'
  | 'public_teams'
  | 'public_team'
  | 'public_courts'
  | 'public_standings'
  | 'public_rules'
  | 'public_register';

export interface HelpLink {
  page: HelpPageId;
  /** In-app path; ":id" is replaced by the tournament id (or the cup address on public pages). */
  to: string;
}

export interface HelpPage {
  steps: number;
  fields: string[];
  actions: string[];
  tips: number;
  links: HelpLink[];
}

export const HELP: Record<HelpPageId, HelpPage> = {
  tournaments: {
    steps: 3,
    fields: ['filter'],
    actions: ['create', 'open'],
    tips: 1,
    links: [
      { page: 'organiser_clubs', to: '/clubs' },
      { page: 'capacity', to: '/capacity' },
    ],
  },
  organiser_clubs: {
    steps: 2,
    fields: ['name'],
    actions: ['create', 'edit', 'delete'],
    tips: 0,
    links: [{ page: 'tournaments', to: '/' }],
  },
  capacity: {
    steps: 4,
    fields: ['classes', 'courts', 'buffer'],
    actions: ['calculate'],
    tips: 2,
    links: [{ page: 'tournaments', to: '/' }],
  },
  user: {
    steps: 0,
    fields: ['name', 'email', 'language', 'password'],
    actions: ['save'],
    tips: 0,
    links: [],
  },
  overview: {
    steps: 3,
    fields: [],
    actions: ['fit'],
    tips: 2,
    links: [
      { page: 'setup', to: '/tournaments/:id/setup' },
      { page: 'teams', to: '/tournaments/:id/teams' },
      { page: 'draw', to: '/tournaments/:id/draw' },
      { page: 'schedule', to: '/tournaments/:id/schedule' },
    ],
  },
  setup: {
    steps: 4,
    fields: ['age', 'teams', 'playoffs', 'rest', 'per_day'],
    actions: ['create'],
    tips: 2,
    links: [
      { page: 'capacity', to: '/capacity' },
      { page: 'clubs', to: '/tournaments/:id/clubs' },
      { page: 'draw', to: '/tournaments/:id/draw' },
    ],
  },
  categories: {
    steps: 3,
    fields: ['name', 'age', 'kind', 'results', 'format', 'days'],
    actions: ['add', 'edit', 'delete'],
    tips: 1,
    links: [
      { page: 'setup', to: '/tournaments/:id/setup' },
      { page: 'teams', to: '/tournaments/:id/teams' },
    ],
  },
  teams: {
    steps: 3,
    fields: ['class', 'club', 'checked_in'],
    actions: ['add', 'edit', 'withdraw', 'delete'],
    tips: 1,
    links: [
      { page: 'clubs', to: '/tournaments/:id/clubs' },
      { page: 'players', to: '/tournaments/:id/players' },
      { page: 'registrations', to: '/tournaments/:id/registrations' },
    ],
  },
  team_edit: {
    steps: 0,
    fields: ['name', 'club', 'squad', 'pot', 'no_overlap', 'players'],
    actions: ['save'],
    tips: 0,
    links: [],
  },
  players: {
    steps: 3,
    fields: ['name', 'file', 'team'],
    actions: ['import', 'template'],
    tips: 1,
    links: [
      { page: 'teams', to: '/tournaments/:id/teams' },
      { page: 'discipline', to: '/tournaments/:id/discipline' },
    ],
  },
  clubs: {
    steps: 3,
    fields: ['name', 'no_overlap'],
    actions: ['add', 'edit', 'delete'],
    tips: 1,
    links: [
      { page: 'teams', to: '/tournaments/:id/teams' },
      { page: 'draw', to: '/tournaments/:id/draw' },
    ],
  },
  club_wizard: {
    steps: 3,
    fields: ['name'],
    actions: ['create'],
    tips: 0,
    links: [],
  },
  registrations: {
    steps: 3,
    fields: ['open', 'max', 'fee', 'status'],
    actions: ['move_up', 'export', 'calculator'],
    tips: 2,
    links: [
      { page: 'public_register', to: '/tournaments/:id/dashboard/register' },
      { page: 'teams', to: '/tournaments/:id/teams' },
    ],
  },
  draw: {
    steps: 3,
    fields: ['pots'],
    actions: ['fit', 'draw', 'fullscreen'],
    tips: 3,
    links: [
      { page: 'clubs', to: '/tournaments/:id/clubs' },
      { page: 'stages', to: '/tournaments/:id/stages' },
    ],
  },
  stages: {
    steps: 3,
    fields: [],
    actions: ['add_stage', 'add_item', 'playoffs', 'next', 'lots'],
    tips: 1,
    links: [
      { page: 'setup', to: '/tournaments/:id/setup' },
      { page: 'draw', to: '/tournaments/:id/draw' },
      { page: 'rankings', to: '/tournaments/:id/rankings' },
    ],
  },
  stage_item: {
    steps: 0,
    fields: ['type', 'teams', 'bronze'],
    actions: ['create'],
    tips: 0,
    links: [],
  },
  playoffs: {
    steps: 0,
    fields: ['placings', 'best', 'bronze'],
    actions: ['create'],
    tips: 1,
    links: [],
  },
  schedule: {
    steps: 4,
    fields: ['hours', 'courts', 'delay', 'links', 'announcement'],
    actions: ['plan', 'drag', 'notify', 'cards'],
    tips: 2,
    links: [
      { page: 'results', to: '/tournaments/:id/results' },
      { page: 'officials', to: '/tournaments/:id/officials' },
      { page: 'match_cards', to: '/tournaments/:id/print/match_cards' },
    ],
  },
  officials: {
    steps: 4,
    fields: ['age', 'club', 'fees', 'available'],
    actions: ['block', 'export'],
    tips: 2,
    links: [{ page: 'schedule', to: '/tournaments/:id/schedule' }],
  },
  results: {
    steps: 3,
    fields: [],
    actions: ['edit'],
    tips: 1,
    links: [
      { page: 'schedule', to: '/tournaments/:id/schedule' },
      { page: 'ceremony', to: '/tournaments/:id/ceremony' },
    ],
  },
  match_edit: {
    steps: 0,
    fields: ['score', 'started', 'cards', 'length'],
    actions: ['save', 'live', 'wo'],
    tips: 0,
    links: [],
  },
  discipline: {
    steps: 3,
    fields: ['red', 'jury', 'decision'],
    actions: ['log'],
    tips: 1,
    links: [
      { page: 'results', to: '/tournaments/:id/results' },
      { page: 'application', to: '/tournaments/:id/application' },
    ],
  },
  rankings: {
    steps: 0,
    fields: ['points', 'tiebreakers', 'fair_play'],
    actions: ['save'],
    tips: 1,
    links: [{ page: 'stages', to: '/tournaments/:id/stages' }],
  },
  ceremony: {
    steps: 0,
    fields: ['minutes'],
    actions: ['export', 'print'],
    tips: 1,
    links: [
      { page: 'results', to: '/tournaments/:id/results' },
      { page: 'teams', to: '/tournaments/:id/teams' },
    ],
  },
  settings: {
    steps: 0,
    fields: ['start', 'timing', 'buffer', 'wo', 'address', 'public', 'rules'],
    actions: ['save', 'archive', 'delete'],
    tips: 0,
    links: [
      { page: 'application', to: '/tournaments/:id/application' },
      { page: 'public_matches', to: '/tournaments/:id/dashboard' },
    ],
  },
  application: {
    steps: 3,
    fields: ['rules'],
    actions: ['copy', 'print'],
    tips: 0,
    links: [
      { page: 'discipline', to: '/tournaments/:id/discipline' },
      { page: 'settings', to: '/tournaments/:id/settings' },
    ],
  },
  match_cards: {
    steps: 0,
    fields: ['filters'],
    actions: ['print'],
    tips: 1,
    links: [{ page: 'schedule', to: '/tournaments/:id/schedule' }],
  },
  pitch: {
    steps: 4,
    fields: [],
    actions: ['wo', 'cards', 'delay', 'correct'],
    tips: 1,
    links: [],
  },
  public_matches: {
    steps: 0,
    fields: ['class'],
    actions: ['print'],
    tips: 1,
    links: [
      { page: 'public_teams', to: '/tournaments/:id/dashboard/teams' },
      { page: 'public_courts', to: '/tournaments/:id/dashboard/courts' },
    ],
  },
  public_teams: {
    steps: 0,
    fields: ['search'],
    actions: [],
    tips: 0,
    links: [{ page: 'public_team', to: '/tournaments/:id/dashboard/teams' }],
  },
  public_team: {
    steps: 0,
    fields: [],
    actions: ['calendar', 'poster', 'print'],
    tips: 1,
    links: [],
  },
  public_courts: {
    steps: 0,
    fields: [],
    actions: [],
    tips: 0,
    links: [],
  },
  public_standings: {
    steps: 0,
    fields: [],
    actions: [],
    tips: 1,
    links: [],
  },
  public_rules: {
    steps: 0,
    fields: [],
    actions: ['print'],
    tips: 0,
    links: [],
  },
  public_register: {
    steps: 3,
    fields: [],
    actions: [],
    tips: 1,
    links: [],
  },
};
