# Roadmap: Bracket for Norwegian children's and youth football cups

Status (2026-11-12): all phases done on branch `phase-0-norwegian` (not pushed), followed by a full review and a final browser test. See "Final status" below.

## Goal

Make Bracket the easiest way for a Norwegian club to plan and run a children's or youth football cup (barnefotball 6–12 and ungdomsfotball 13+). It should:

- follow NFF Breddereglement, and
- support the way Norwegian cups are actually run: several age classes sharing split pitches, group play followed by A/B playoffs, tight time slots with buffers, volunteers entering results on site, and parents following along on their phones.

## Guiding principles

1. **One tournament is one cup.** Age classes live inside the tournament, so all classes share the same pitches and one schedule.
2. **NFF rules are built-in defaults.** For example, children's classes hide results and tables and require at least 3 matches per team. The organiser can see these rules but not accidentally break them.
3. **Extend the existing layers.** Logic goes in `logic/*`, queries in `sql/*`, endpoints in `routes/*`, plus Alembic migrations and regenerated OpenAPI client types. No parallel architecture.
4. **Send generic improvements upstream.** Tiebreakers, bronze match, byes, the conflict-detection fix and the `nb` locale go to evroon/bracket to keep the fork small. Norway-specific features stay in the fork.
5. **Test against the reference examples.** Worked examples from AreaCopa and Cup Manager (see "Reference scenarios") become integration tests.

## Ideas borrowed from other projects

| Source | Idea |
|---|---|
| Ultiorganizer | Divisions sharing field reservations (time windows per pitch); bracket templates with explicit crossings and placement mapping (incl. 3/5/6/7/9 teams); conflict checks (overrun past reservation end, playoff scheduled before its feeder match); tie-break order with head-to-head; QR links for score entry without an account; per-reservation result-entry role; printable PDFs (schedule, scoresheets); iCal feeds |
| turnierplan.NET | Results "after extra time" / "after penalties" / special ruling (walkover); live vs final result (live score not counted in tables yet); Reporter role; registration with public invite link, applications list, entry-fee-paid flag, CSV export; referee cards (PDF); fixed final-round templates chosen by number of groups |
| kennethaasan/tournament | Placeholders such as "Winner A1" / "2nd Group B"; big-screen mode that rotates views; schedule-change notifications (concepts only — no license, no code reuse) |
| EvanOman/tournament-scheduler | Constraint-based scheduling (OR-Tools CP-SAT): field availability windows, field sizes, changeover buffers, minimum rest, independent validator re-checking the solution (concepts only — no license) |
| Cup Manager | Capacity calculator: matches = teams × matches per team / 2; playoff matches = teams − 1; slot = length + changeover; pitches = total time / window |
| AreaCopa | Four buffer types (micro, block, lunch, final reserve); never back-to-back; alternate groups on a pitch; three-step delay protocol; parent-facing schedule without results for ≤12; rules sheet; registration status tracking; check-in |

## Phases and features (in priority order)

Each item is tagged **[Fix]**, **[Core]**, **[Feature]** or **[Nice]**, and **⬆** marks items that are candidates for upstream PRs.

### Phase 0 — Foundation and quick wins

**Status (2026-11-11, branch `phase-0-norwegian`, uncommitted):**

- Items 1, 2, 3, 5 and 6 are implemented. Backend: 97 tests pass and all CI linters pass. Frontend: `tsc`, `oxfmt` and `vite build` pass.
- Item 4 is deferred to Phase 3, where the new scheduler will read `auto_assign_courts`.
- Done beyond the plan:
  - About 15 hard-coded English UI strings now go through i18n, including the public dashboard's "Matches"/"Standings" tabs. Other languages fall back to English for these until Crowdin translates them.
  - Dates are formatted with the browser's `Intl` API instead of bundling date-fns locales.
  - The dashboard sort comparator, which returned a boolean, is fixed.
- Not yet verified in a real browser: automated browser control was unavailable in this environment.

1. **[Feature] Norwegian Bokmål translation (`nb`), Bokmål only** ⬆
   - Add `frontend/public/locales/nb/common.json` (274 keys) and add `nb` to the language picker (`components/forms/user.tsx`).
   - Map browser languages `no`, `nb-NO` and `nn-NO` to `nb` in `i18n.ts` (`fallbackLng: { no: ['nb'], nn: ['nb'], default: ['en'] }`).
   - Load the dayjs `nb` locale so Mantine date pickers show Norwegian.
   - Crowdin already maps `%two_letters_code%`; confirm it produces `nb` (not `no`).
   - Write a football glossary and use it consistently: court → *bane*, match → *kamp*, group → *pulje*, stage → *fase*, playoff → *sluttspill*, team → *lag*, class → *klasse*, referee → *dommer*, match host → *kampvert*, standings → *tabell*.
   - Backend error messages (≈33 `HTTPException(detail=...)` strings) are English only. Later, give them stable error codes that the frontend translates.
2. **[Fix] Conflict detection** ⬆ — `matches_overlap` in `logic/planning/conflicts.py` misses partial overlaps and containment. Replace it with the standard interval test `s1 < e2 and s2 < e1`, and add tests.
3. **[Fix] Production code imports test mocks** ⬆ — `logic/scheduling/builder.py` uses `MOCK_NOW` from `tests/`. Use the real current time.
4. **[Fix] Unused setting** ⬆ — `auto_assign_courts` is stored but never read. Either wire it into the scheduler (Phase 3) or remove it.
5. **[Fix] Show dates, not only times** ⬆ — the schedule shows only `HH:mm`. Show day separators and dates, needed for multi-day cups.
6. **[Core] Make limits configurable** — the per-tournament limits (128 teams, 32 courts, 64 stage items) are hard-coded in `logic/subscriptions.py`. Make them configurable via env so large cups fit.

### Phase 1 — Core domain model: age classes and children's mode

**Status (2026-11-11): items 7–9 done** (commits 1a–1d on branch `phase-0-norwegian`).

- **Classes are optional.** A tournament without classes works as before.
- **Hidden results.** Classes with hidden results:
  - only allow round robin groups
  - don't allow advancing by placing, so the bracket can't reveal results
  - are hidden server-side for anonymous visitors, and in the dashboard UI for everyone
- **Rankings** only count played matches.
- **Deferred:**
  - Match duration and margin per class moves to Phase 3, where the new scheduler owns all timing.
  - Item 10 (team metadata): club and contact fields are deferred to Phase 6 (registration), since contact details must stay out of the public teams API.

7. **[Core] Age classes (`categories` table under tournament)**
   - Fields: name ("G10", "J12"), birth year or age, game format (3v3/5v5/7v7/9v9/11v11), default match duration and margin, results visibility, minimum matches per team, ranking config.
   - Teams belong to one class.
   - Stages belong to one class. **The active stage becomes per class instead of per tournament**, so G10 can be in playoffs while J12 is still in groups.
   - Stage activation and the "all inputs assigned" check apply per class.
   - Courts stay per tournament (shared by all classes).
8. **[Core] Results visibility (NFF § 6-5)**
   - Per-class boolean `results_public`. It defaults to false for classes aged 12 and under and true for 13+, and the organiser can change it.
   - Add a `played` flag on matches. Entering a score sets it; the organiser can also set it without a score.
   - When `results_public` is false:
     - Public endpoints return no scores and no standings — enforce this **server-side**, not only in the UI.
     - Dashboards show the schedule, with "Spilt" (played) on finished matches.
     - Playoff, ranking and winner features are disabled for the class.
   - Logged-in organisers still see everything they entered.
9. **[Core] NFF validation rules**
   - Warn or block when a class ≤13 gives any team fewer than 3 matches (§ 6-4).
   - Warn about pure knockout for ≤13.
   - Warn about publishing tables for ≤12.
10. **[Core] Team metadata**
    - Club (needed for draw constraints and listings), contact person, phone and email, squad size, and a check-in status for match day.

### Phase 2 — Competition formats and rankings

**Status (2026-11-11): items 11–17 done** (commits 2a–2f on branch `phase-0-norwegian`).

- Teams are ordered by points, then tiebreakers. Positions and goals are stored per group placing.
- Knockouts work for 2–64 teams, with standard-seeded byes and an optional bronze final.
- Extra time, penalties and walkovers are supported.
- The playoff wizard:
  - creates A/B/C playoffs with crossed seeding (Hungarian assignment, about 1 ms)
  - can add the best placed teams across groups
- Live scores are separate from final results.
- **Deferred to Phase 5 (rules sheet):** per-class rules text for extra time and the number of penalty takers. The result type already records how each match was decided.

11. **[Feature] Configurable tiebreakers** ⬆
    - An ordered list per ranking: points, goal difference, goals scored, head-to-head (mini-table), fair play, drawing lots.
    - Default 3/1/0 points for football.
    - Current state: teams are sorted by points only, and ties keep insertion order.
12. **[Feature] Knockout for any size (byes)** ⬆ — support 2–64 teams, not only 2/4/8/16/32, with byes that give top seeds a free first round.
13. **[Feature] Bronze match and placement matches** ⬆ — optional third-place match; optional full placement bracket (rank 1..N). Uses Ultiorganizer-style templates with explicit crossings and placement mapping.
14. **[Feature] Extra time and penalties** ⬆
    - Match result type: normal / after extra time / after penalties / walkover / special ruling, with penalty scores.
    - `get_winner()` uses them. Today a draw in knockout leaves the next match without a team.
    - Per-class settings for extra time (yes/no, length) and number of penalty takers (3 or 5, then sudden death).
15. **[Feature] Playoff templates: A/B/C playoffs and cross semis**
    - A wizard that, from a group stage, creates A, B (and optionally C) playoffs.
    - Typical pairing: "top 2 from each group → A, the rest → B". Cross seeding (WA–2B, WB–2A; quarter-final patterns for 4 groups).
    - Builds on the existing tentative inputs (`winner_from_stage_item_id` + `winner_position`).
16. **[Feature] Best-placed across groups** — rank e.g. all third-placed teams across groups (normalised when group sizes differ) to fill a playoff whose size is a power of two.
17. **[Feature] Live vs final result** — a live score shows on the dashboard but does not count in tables until confirmed (turnierplan.NET).

### Phase 3 — Scheduling engine

**Status (2026-11-11): core done** (commits 3a–3d on branch `phase-0-norwegian`).

- **Playing hours:** time windows per day; a lunch break is a gap between windows; multi-day cups work.
- **Courts:** courts can be created in bulk, and courts and classes have a game format. Classes have their own match duration, margin and rest.
- **Buffer between stages:** this is the "block buffer".
- **Greedy scheduler:**
  - respects time windows, formats, rest and knockout order, and keeps played and live matches in place
  - is checked against AreaCopa's timeline and Cup Manager's math
- **Feasibility report:** gives exact extra courts per format or extra minutes, found by binary search over simulations.
- **Independent checker:** includes a property test.
- **Delay tool:** moves the remaining matches.
- **Not done yet:**
  - item 18: split pitches (a full pitch split into 2×7v7) blocking the full pitch
  - item 22: "shorten remaining matches"
  - final reserve before awards (can be modelled by ending the last window earlier)
  - item 20 step 2: OR-Tools optimisation, not needed so far (300 matches are planned in 0.07 s)

The target workflow:
- **Input:** start and stop date/time, daily playing hours, number of courts, and the classes with their structure.
- **Output:** the proposed match plan with all time slots, plus a feasibility report.

17b. **[Core] Cup time frame**
   - The tournament gets a start and end (date + time) plus daily playing hours (e.g. 09:00–18:00). Hours can differ per day, for example a Friday-evening start.
   - The organiser can enter "number of courts" and get courts named "Bane 1…N" created automatically, then rename or split them.
18. **[Core] Pitch model**
    - Pitches have a format/size (3v3…11v11) and an optional parent pitch, so a full-size pitch can be split into 2×7v7 or 4×5v5 — and while it is split, the full pitch is blocked.
    - Availability windows per pitch per day, like Ultiorganizer reservations.
    - Classes are only scheduled on pitches of matching format.
19. **[Core] Buffers and breaks**
    - Micro buffer (existing margin), block buffer between group stage and playoffs, lunch break, final reserve before awards, and manual pauses inserted on a pitch.
20. **[Feature] New automatic scheduler**
    - Replaces the "one court per stage item" logic, which today puts every group beyond the number of courts on the last court.
    - Hard constraints: pitch format and windows, no team in two places, **minimum rest per team** (configurable; default: never back-to-back), playoff matches after their feeder matches (+ block buffer).
    - Soft goals: alternate groups on a pitch, balance load across pitches, finish early, keep a class on nearby pitches.
    - Step 1: a greedy list scheduler (deterministic, fast, easy to explain).
    - Step 2 (optional): OR-Tools CP-SAT when the greedy scheduler fails or packs badly.
    - Always run an independent validator afterwards (overlaps, rest, windows, dependencies) and show violations in the UI.
    - **Generate a proposal, then commit it.** The result is a draft plan the organiser can review, adjust by drag-and-drop, regenerate, or accept. Matches that are locked or already played are never moved.
20b. **[Feature] Feasibility report**
    - Shown before and after generating. It lists:
      - required court-hours vs available court-hours, per court format and per day
      - utilisation
      - the matches that did not fit
    - When the plan does not fit, it states the shortfall concretely:
      - "Need at least N more courts of format X", or
      - "Need H more hours (e.g. end at 19:30 instead of 18:00, or add a day)".
    - It also offers what-if levers with their effect: match length −2 min, smaller buffers, group size 5 → 4, drop the bronze match or B-playoff.
    - The calculation reuses the capacity formulas (item 24), so the planner and the wizard always agree.
21. **[Feature] Multi-day cups** — day boundaries, a window per day, which phases are played on which day.
22. **[Feature] Delay tools (AreaCopa protocol)** — "shift all remaining matches on pitch X / class Y / everything by N minutes"; "shorten all remaining matches by N minutes"; drop the bronze match. Show the knock-on effects before applying.
23. **[Fix] Extend conflict checks** — add minimum-rest violations, match beyond the pitch window, playoff before its feeder, and the same referee in two places (Phase 6).

### Phase 4 — Cup setup wizard and planning

**Status (2026-11-11): items 24–26 done** (commits 4a–4c on branch `phase-0-norwegian`).

- **Capacity calculator** (`/capacity`): classes described by numbers are planned with the real scheduler, so the answer includes rest, formats and stage order. Reports fit, extra courts or time, matches per team and NFF warnings. Input limits: 600 teams, 100 courts, playoffs of at most 64 teams.
- **Scheduler speed-up:** court bookings as merged intervals searched with bisect; the worst case (3300 matches, 100 courts) went from 34 s to 5 s with identical plans.
- **Setup wizard** (`/tournaments/{id}/setup`): classes → courts → playing days → overview with the calculated plan → creates classes, group stages, A/B/C playoffs, courts and time windows in one transaction, and can plan all matches at once. Only for an empty tournament.
- **Group draw** (`/tournaments/{id}/draw`): pots (one team per pot per group), clubs apart where possible (Hungarian per round), random otherwise; revealed team by team with a full-screen view. Teams have an optional club; empty means the name without a trailing number.
- **Not done yet:** manual adjustment happens on the stages page (no drag and drop on the draw view); pots are not stored.

24. **[Feature] Capacity calculator** (Cup Manager formulas)
    - Inputs: teams per class, group size, playoff type (A / A+B / …), match length + changeover, pitches per format, time windows.
    - Outputs: number of matches, hours, minimum pitches, utilisation, and warnings (e.g. ≥5 matches/day for 10–13-year-olds, fewer than 3 matches per team).
    - Runs live before teams are registered, so it can answer "how many teams can we accept?".
25. **[Feature] Cup setup wizard** — one flow: cup info → classes (with NFF presets by age: format, pitch size, typical cup match length) → pitches → structure per class (groups, playoffs) → generate stages, stage items, inputs and the schedule.
26. **[Feature] Group draw** — seeding pots (one team per pot per group), a random draw that keeps teams from the same club apart where possible, manual adjustment, and a draw view the organiser can show on screen.

### Phase 5 — Match-day operations and public experience

**Status (2026-11-11): items 27–31 done** (commits 5a–5e on branch `phase-0-norwegian`).

- **Roles:** only club owners can rename or delete a club and delete a tournament; collaborators run everything else, including match day. Matches and rounds are now looked up within their tournament (this closed a cross-tournament hole).
- **Result links:** per court or for the whole cup, with a QR code. They expire (8 h to 7 days) and can be revoked; only a hash of the token is stored. Rate-limited, and no changes are possible through a link once the cup is archived.
- **Pitch page `/score/:token`:** mobile-first: current match, big score buttons, result type, walkover, cards, check-in, and delay reports that show up on the planning page.
- **Walkover, withdraw, check-in:** the walkover score is a tournament setting. A withdrawn team's remaining matches become walkovers and the schedule stays as it is.
- **Public pages:** schedules per class, team, court and day (team search), a big-screen rotation, an announcement banner, a rules page, an iCal feed per team, QR posters. Classes with hidden results show only "Spilt".
- **Printing:** print CSS for all schedules, tables and rules, plus match cards with score boxes. No server-side PDF.
- **Not done yet:** delays reported from a pitch don't move the schedule (the organiser uses the delay tool). Rate limits are per process.

27. **[Feature] Roles and score entry**
    - Enforce OWNER vs COLLABORATOR (the relation exists but is not checked today).
    - Add a **score-keeper** role.
    - Add **QR / signed links** that allow result entry for one pitch or one match without an account (Ultiorganizer). Links expire and can be revoked.
28. **[Feature] Mobile secretariat view** — a "my pitch" page: next match, enter result, mark walkover or no-show, flag a delay.
29. **[Feature] Walkover and no-show** — walkover result (0–3 by default, configurable), withdraw a team (the remaining schedule stays as it is), check-in status.
30. **[Feature] Public pages for parents**
    - Per-class and per-team schedule (QR code on posters), "next match on pitch X", big-screen rotation, announcements banner for delays and weather.
    - All of them respect results visibility.
    - iCal feed per team.
31. **[Feature] Print and PDF**
    - Schedules per class, per team and per pitch.
    - Referee and match cards.
    - The rules sheet.
    - Group tables (13+ only).
    - Start with print CSS; add server-side PDF only if needed.

### Phase 6 — Administration

**Status (2026-11-11): items 32–37 done** (commits 6a–6e on branch `phase-0-norwegian`, plus security fixes).

- **Registration:** classes can be opened with a deadline, a team limit, a waitlist and an entry fee. Public sign-up form with a honeypot, a rate limit, the owner's subscription limit, and serialised count-and-insert. Contact details are organiser only. The "Påmeldinger" page shows status, paid, squad reported, one-click "move up" from the waitlist, and a CSV export that is safe against formula injection. Waitlisted and rejected teams are left out everywhere.
- **Entry-fee calculator:** (fixed + per team × teams) × (1 + margin) ÷ teams, rounded up to 50 kr, and applied to chosen classes.
- **Officials:** referees, assistants and match hosts per court block. Conflicts: double booking, own club, unavailable. Fee summary with CSV; only names are shown publicly.
- **Discipline (13+ with public results):** cards, automatic suspensions (tournament settings) and a jury log that can change suspensions. Cards can be entered from the match form and the pitch page, with warnings about suspended players.
- **Application to the district:** a page with the cup facts (organiser, contact, jury chair, venue, rules) and a live text for FIKS built from the cup, with copy and print buttons.
- **Email:** an SMTP sender configured by environment variables. Without it, the UI offers to copy the addresses or open the email program with everyone in BCC. Emails are queued with a dedupe key, so nothing is sent twice, sent in the background and retried.
  - Kinds: sign-up confirmation (a fixed text, so it can't be used to relay spam), a place from the waitlist, announcements (opt-in) and "email the new times" (only to teams whose times changed).
- **Not done yet:** officials aren't linked to players, so a referee playing in another match at the same time isn't detected. Rules are plain text.

32. **[Feature] Registration**
    - Public sign-up form per class, with a registration deadline.
    - Waitlist.
    - Status per team: invited / registered / paid / squad reported.
    - Approve or reject.
    - CSV export. Expect 10–20% dropouts and move teams up from the waitlist easily.
33. **[Feature] Referees and match hosts**
    - Officials: name, age, level, club.
    - Assign them per match or per pitch block.
    - Check that no official is double-booked or plays for a team in the same slot.
    - Fee summary per official (fixed amount per match or per day).
    - Match hosts (*kampvert*) assigned per pitch.
34. **[Feature] Discipline (13+)** — cards per match, automatic suspension for the next match after a red card, jury decisions and notes.
35. **[Nice] Entry-fee calculator** — (fixed + variable costs + 15 %) / teams; tracks paid status (links to 32).
36. **[Nice] Krets application export** — summary of the cup (time, rules, fee, jury chair, classes) to paste into the district application (FIKS).
37. **[Nice] Notifications** — email to team contacts when the schedule changes or an announcement is posted.

## Final status (2026-11-12)

After Phase 6, a three-way review (requirements fit for Norwegian cups, an end-to-end browser test, and a code review) led to three more rounds of work:

- **Bug fixes:** a "best placed" playoff slot could break a whole cup; deleting a cup with clubs failed; the pitch page lost a typed score on a bad connection; failed schedule emails were never retried; proposing a plan wrote to the database.
- **Planning:** split pitches (an 11er as 2–4 parts), hours per pitch and per class (days and times), max matches per team per day, re-planning from a chosen time and a delay tool with preview, "started" matches that never move, the wizard ordered days → classes → pitches with per-day match counts.
- **Match day and administration:** a single "Spilt" button for children's classes, club sign-up with several teams (one confirmation email), teams that must never play at the same time (per team or per club), final placings and prize ceremony with medal counts, a jury of at least three (NFF check), fair-play and drawing-of-lots tiebreakers, referee age warnings, class kind (G/J/Mix), level-split rounds for children's classes, error codes translated for the public, participating clubs linked to teams.
- **Norwegian terms:** pulje/puljespill/puljetrekning, spilleopplegg, poeng og tabellregler, cup instead of turnering, offentlig cupside, arrangørklubber, kampskjema, W.O., foreløpig stilling. Swiss system is no longer offered.
- **Final browser test (Playwright, 1400 px and 390 px):** a fresh cup through wizard (split pitch, class on one day), clubs wizard, club sign-up on a phone with waitlist, draw with pots, plan and re-plan previews, result links (start, "Spilt", score, card, W.O. with confirmation), playoffs, level-split round, jury, lots, referees, prize ceremony, public pages, big screen and print. 25 pages without console errors or sideways scrolling. Bugs found and fixed in that run: the registrations page had been overwritten by the draw page; playoffs could not start when a group had an empty place; "more time doesn't help" for classes with their own hours; English weekdays; raw keys for referee age warnings; cups created without a public address.

**Out of scope:** online payment (Vipps/KID), accommodation, meal tickets and cup passes; server-side PDF (print uses the browser); upstream contribution of the generic fixes.

**Known limitations:**
- Rate limits are per server process, and behind a proxy all clients share the proxy's IP.
- Result-link tokens are in the URL path, so they appear in access logs.
- Officials aren't linked to players, so a referee playing at the same time isn't detected.
- Split pitches are one level deep; there is no "shorten the remaining matches" option.
- The wizard's capacity estimate doesn't know club "never at the same time" rules added later; the real plan shows the exact shortfall.
- Rules text is plain text (no Markdown).

## Reference scenarios (integration tests)

- **AreaCopa indoor:** 8 teams, 2 groups of 4, 1 pitch, 8+3 min, 14:00 start → 12 group matches + 2 semis + final; no team plays twice in a row; 5 min block buffer before semis; SF1 16:17, final 16:39, awards 16:50.
- **AreaCopa outdoor:** 12 teams, 3 groups of 4, 2 pitches, 12+3 min, 45 min lunch, QF/SF/bronze/final; awards at 13:25.
- **Cup Manager:** 200 teams, groups of 4, 6 classes with A+B playoffs → 300 + 188 = 488 matches; 32-min slots; 08–20 window → at least 14 pitches for the group day.
- **Children's mini-tournament:** 14 teams 3v3, 7 pitches, ≥3 matches per team, public API returns no scores.

## Suggested order of work

1. Phase 0, items 1–5 — a working Norwegian UI plus bug fixes; send the generic items upstream.
2. Phase 1 — the age-class model is the base for everything after it.
3. Phase 2, items 11–14 and Phase 3, items 18–20 — together these make a real cup possible.
4. Phase 4 — the wizard and calculator make it *easy*.
5. Phases 5–6 — match-day operations and administration.

## Decisions (2026-11-11)

- **Bokmål only.** No Nynorsk. Browser codes `no`/`nn` fall back to `nb`.
- **Results visibility is a simple boolean** (`results_public`) per age class.
  - When false: the public views show each match only as **"Spilt" (played)** — no score, no table, no winner.
  - Organisers can still enter scores for internal use. A match counts as played once a result or a played mark is saved.
- **Generate a proposed match plan from a time frame and courts.** The organiser enters the cup's start and stop date and time, the daily playing hours, and the number of available courts. The system generates a complete proposal with time slots.
  - If it does not fit, the system says so and quantifies the shortfall:
    - how many more courts are needed with the current time frame, or
    - how much more time is needed with the current courts.
  - It also suggests concrete levers: shorter matches, smaller buffers, a different group size or playoff format.

## Open questions

- How many teams and pitches are expected for the first real cup? This sets how much the scheduler needs to handle.
- Self-hosted for one club, or hosted for several clubs?

## Production requirements

Before a real cup, the deployment must meet the requirements in
`docs/content/deployment/index.mdx` ("Production requirements"). In short:
- HTTPS everywhere.
- `TRUSTED_PROXIES` set when running behind a reverse proxy, so rate limits see real clients.
- SMTP configured (`SMTP_HOST`, `SMTP_FROM`, credentials) and tested; without it no email reaches
  team contacts.
- Migrations run on every upgrade, after a backup.
- Daily backups, hourly during the cup weekend, with a tested restore.
- A random `JWT_SECRET` and a changed admin password.
- The proxy must not log full `/score/<token>` URLs.

