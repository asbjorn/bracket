# Roadmap: Bracket for Norwegian children's and youth football cups

Status: draft (2026-11-11). This is a high-level plan; each phase needs its own design and implementation plan before coding.

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

24. **[Feature] Capacity calculator** (Cup Manager formulas)
    - Inputs: teams per class, group size, playoff type (A / A+B / …), match length + changeover, pitches per format, time windows.
    - Outputs: number of matches, hours, minimum pitches, utilisation, and warnings (e.g. ≥5 matches/day for 10–13-year-olds, fewer than 3 matches per team).
    - Runs live before teams are registered, so it can answer "how many teams can we accept?".
25. **[Feature] Cup setup wizard** — one flow: cup info → classes (with NFF presets by age: format, pitch size, typical cup match length) → pitches → structure per class (groups, playoffs) → generate stages, stage items, inputs and the schedule.
26. **[Feature] Group draw** — seeding pots (one team per pot per group), a random draw that keeps teams from the same club apart where possible, manual adjustment, and a draw view the organiser can show on screen.

### Phase 5 — Match-day operations and public experience

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
