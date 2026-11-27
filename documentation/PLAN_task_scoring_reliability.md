# Plan: reliable, catalogue-conformant task scoring

Status: **approved 2026-11-26**, D1, D2 and D9 decided (see the table). Implementation runs slice by slice on the branch
`task-scoring-reliability`.

**Progress, 2026-11-27:** Phases 1 to 5 (S1 to S24, with S20b and S22b) are implemented and committed on the branch; the
app part (S23) is on the branch `pilot-declaration-status` of `airsports-mobile`. Nothing is pushed. Phase 6 (S25 to
S28) is not started. Decided during implementation: several backtracks add up (the catalogue gives no cap); no
disqualification concept; existing CIMA tasks and scorecards are not migrated (none were used for real); stored positions
are metres and knots from every source. Not yet done by anyone: a click-through in a browser and on a phone. What the
implementation does not cover is listed under "Known limits" in `airsports_static/src/pages/docs/11_CIMA_Task_Guide.md`.

Goal: the route editor → navigation task → pilot declaration → calculators → scores chain produces predictable,
deterministic results that match the official rules, and pilots and organisers can complete the flow themselves.

Sources reviewed: FAI Sporting Code Section 10 (2026 V2), Annex 3 (model local regulations), Annex 4 (task catalogue,
2026 V2, tasks 2.A1–2.B3), Annex 9 (Air Sport Race, 2025). The rules that matter are quoted in the appendix so that an
implementer does not need the PDFs.

## Already done (uncommitted on `main`)

- "Air Sports Race 2025 (Annex 9)" scorecard, default for the Air Sports Race family, with tests (not yet run).

## Decisions needed before the affected slice starts

| # | Decision | Recommendation | Blocks |
|---|---|---|---|
| D1 | "Best score for the task" needs a class. Contestants have no class today. | **Decided:** all contestants of a task are one class | S9 |
| D2 | Follow the catalogue formulas literally (2.A1 `Qh = 1000·H/Nh`, 2.A3 `V = N − Ep`), replacing the current per-gate 180 model | **Decided:** yes | S12, S14 |
| D3 | 2.A7 geometry: X is crossed twice (start and end of the scored 360°), WP is the exit, radius limits checked during the whole scored circle | Yes | S17 |
| D4 | 2.B2: targets may be flown in any order | Yes, order-free gate matching for 2.B2 only | S16 |
| D5 | Unit of `position.altitude` (metres or feet) | Verify in S17 before using the 200 ft band | S17 |
| D6 | Declaration cut-off for pilots | Editable until take-off time; organiser can always edit | S21 |
| D7 | Air Sport Challenge: move to the Annex 9 scorecard as well? | Only after S3 shows identical calculator behaviour | S26 |
| D8 | Backward crossing of SP in Annex 9 scorecard (old card: 200, annex: none) | Keep 0 | – |
| D9 | How the test suite is run (Docker is not reachable from the WSL shell agents use) | **Decided:** Docker is reachable; agents run pytest in `tracker_daphne`, one run at a time | all |

## How the work is executed

- One sub-agent per slice, model **Sonnet 5.5**, run **one at a time** (never two pytest runs against `tracker_daphne`
  at once; never restart `tracker_daphne`).
- Work on a branch `task-scoring-reliability`; one commit per slice, no PR until asked.
- Each agent gets: this plan, its slice, the files listed, and the acceptance criteria. It must not reformat whole
  shared modules (ruff only on lines it touches / new files).
- After each slice the main session reviews the diff and the test output before the next slice starts.
- A slice is done when its acceptance tests pass and the full CIMA/calculator test folders still pass.
- Any change that affects the mobile apps gets a line in `documentation/mobile_changelog.md`.

## Phase 1 — Flight simulator and catalogue oracle (safety net)

**S1. Synthetic track simulator.** New module `src/display/calculators/tests/flight_simulator.py`.
- Input: a contestant's effective waypoints and gate times. Output: 1 Hz positions (lat, lon, time, altitude, speed,
  course) following the legs, timed to hit each expected gate time.
- Composable deviations: time offset at gate N; lateral offset that misses gate N; skip gate N; 360° orbit on a leg;
  reverse along a leg for T seconds; cross gate N twice; cross gate N in the wrong direction; visit gates in another
  order; altitude profile; leave/re-enter a corridor for T seconds; parametrised circle (radius as a function of angle,
  direction, entry geometry).
- Runner: builds the task the way the wizard does (EditableRoute GeoJSON → `create_route` → `NavigationTask.create` →
  `Contestant` → `ContestantTaskCompiler.compile`), feeds positions through `calculator_factory(live_processing=False)`
  and through the real score-application step (`update_score_from_thread` with side effects suppressed), and returns
  messages plus the final score.
- Acceptance: unit tests of the simulator itself (generated track crosses each gate line within 1 s of the requested
  time; each deviation does what it says).

**S2. Baseline tests on legacy types.** Perfect flight, late gate, missed gate, backtrack, procedure turn, corridor
excursion, prohibited and penalty zone for legacy Precision, ANR and the Annex 9 scorecard. These must pass on current
code (they validate the simulator against behaviour we already trust); any failure is reported, not "fixed" in the test.
Includes determinism: same track twice → identical messages; positions fed one by one or in batches → identical result.

**S3. Catalogue oracle and CIMA scenario tests.** `catalogue_oracle.py`: a small, independent implementation of each
catalogue formula (appendix). One or two route fixtures per task 2.A1–2.B3 and scenarios: perfect, each timing error,
missed/hidden gate, repeated crossing, backtrack, wrong order, declaration variants. Tests that fail because of a known
finding are marked `xfail(strict=True)` with the slice number that will fix them.
- Acceptance: every finding F1–F20 below has at least one xfail test that reproduces it.

## Phase 2 — One task-type registry

**S4. Registry, no behaviour change.** Replace the scattered tables in `cima_task_type_definitions.py`
(`TASK_SUBTYPE_DEFINITIONS`, `NO_BACKBONE_TASK_SUBTYPES`, `ABSOLUTE_TIME_DECLARATION_SUBTYPES`,
`DECLARATION_REQUIRED_SUBTYPES`, `CIMA_SCORING_BASELINE`, `CIMA_FIXED_SCALE_FACTORS`, `LEGACY_DEFAULT_SUBTYPE_BY_FAMILY`)
and `task_type_registry.py` with one registry: rule set (Legacy, CIMA Annex 4, Air Sport Race Annex 9) → task type →
one definition (key, catalogue code, display name, calculator pipeline, scoring model, default scorecard, declaration
schema, route requirements). Legacy types become ordinary entries, not `legacy_*` shims. Stored values
(`NavigationTask.task_subtype`, `Scorecard.calculator`) keep their current strings; old import names stay as thin
aliases until S5.
- Acceptance: existing tests pass unchanged; a test asserts every stored subtype/family string resolves.

**S5. Remove string branching.** `gate_calculator.py`, `task_type_registry.py`, `contestant_task_compiler.py`,
`task_templates.py` (`startswith("legacy_")`) read behaviour from the registry instead of comparing subtype strings.
Remove the aliases from S4.

**S6. Structured route requirements.** Each task type declares requirements as data (feature kind, min, max, order,
names). `route_compatibility.get_blocking_reasons`, `TaskCompiler._validate_primitives` and the structural checks are
generated from it, so "compatible in the editor" and "valid at compile" cannot differ. Fixes: 2.A1 requires a curved
leg; 2.A2 and 2.A5 structure checked at compatibility time; 2.A7 exactly one of each marker; 2.B3 requires a landing
area. Bump `ROUTE_COMPATIBILITY_RULESET_VERSION`.

**S7. Wizard from the registry.** The route editor's Task Route Guide (`taskTemplates.ts`) takes its steps and
min/max counts from the API instead of its own copy. Vitest for the mapping.

## Phase 3 — Scoring engine

**S8. Typed score messages and raw Q.** `UpdateScoreMessage` gets an explicit kind: penalty, achievement, or percentage
penalty. Calculators state the kind; `contestant_processor.update_score_from_thread` no longer flips signs from a
hard-coded exemption list. The contestant track stores raw Q by component. Remove per-contestant Qmax normalisation
(`cima_score_normalization.py`) and the ANR ×0.5 scaling from the processor.

**S9. Task-level normalisation.** New service computing task scores for all contestants of a task:
`P = task_value × Q / Qmax` with a per-task policy (best in task [default for CIMA], theoretical maximum, absolute) and
task value (default 1000, allowed 500–1500); then percentage penalties on P; floor at 0; round half up to a whole
number. Recomputed whenever any contestant's Q changes; scores are "provisional" until all flights are finished.
Legacy and Annex 9 tasks keep cumulative penalties unchanged. Scorecard gains `scoring_model`, `qmax_policy`,
`task_value` (config fields, scorecard editor "General" group).

**S10. Display.** Live map, task results, contest results and flight summaries show P (and "provisional"), sorted
descending for quality-score tasks. DNF and DSQ score zero and are labelled.

## Phase 4 — Per-task corrections (each turns its xfail tests green)

| Slice | Finding | Change |
|---|---|---|
| S11 | F1 hidden gate crossed twice or backwards is never invalidated (dead code, 2.A1 only) | Detect later crossings of already-passed hidden gates; apply to 2.A1, 2.A2, 2.A4, 2.A5; time taken from first crossing |
| S12 | F2 2.A1 weighting | `Qh = 1000·H/Nh`, `Qt = Emax·Nt − Et`; SP/FP not counted as gates |
| S13 | F3 2.A2 asks the pilot to predict hidden gates and SP | Predictions only for visible turn points and FP; organisation interpolates hidden-gate times |
| S14 | F4 2.A3 invalid post-MP point costs nothing; F5 score does not reward declaring more; F6 MP time read from the wrong source | `V = N − Ep`, `Qp = 1000·V/Vmax`, `Qt = Emax·3 − Et`; invalid post-MP counts in Ep; MP time from the gate's expected time |
| S15 | F7 2.A4 speed term penalises deviation, uncapped | `Qv = Vs·S/Smax`; keep speed-keeping as an optional scorecard rule, off by default |
| S16 | F8 compulsory gate penalised twice; F9 time gates earn nothing; F10 over-duration flat; F11 2.B2 needs free order and scores nothing without a declared sequence | Tolerance 10 s then 10 pt/s; 200 per time gate; over-duration 10 pt/s; order-free matching for 2.B2 |
| S17 | F12 circle needs 540° around CM, a correct circle scores zero; F13 radius, direction and centre checks are weak | Scored arc from first to second crossing of X; Rmin/Rmax over that arc; radius limits over the whole arc; direction from signed progress; 20% altitude penalty as percentage |
| S18 | F14 duration: longer flight ranks worse; no CIMA scorecard | Duration as achievement, normalised best-in-task; landing-area penalty configurable |
| S19 | F15 backtracking flat 200 | 50% percentage penalty for 2.A1–2.A5; verify the calculator against S10 4.24.5 (corridor width, turnpoint exception, rejoin rule) |
| S20 | F16 2.A8 not verified | Check every value against the catalogue; `P = 1000·Q/2000` as an absolute score |

### Results of Phase 1 (2026-11-26)

S1–S3 are done: 231 tests pass and 64 are strict expected failures, each naming the finding and the slice that fixes it
(`pytest display/calculators/tests/ -k "simulat or oracle or flight_simulator" -rxX`). A slice is finished when its
expected failures pass and their markers are removed.

- **F6 was not reproduced.** The 2.A3 check of the MP time follows the declaration, also with an adaptive start. No
  change needed; the passing test stays.
- New findings from the scenarios:

| # | Finding | Fixed in |
|---|---|---|
| N1 | 2.A8: missing SP sideways costs nothing, and a crossing outside the 0.6 NM time gate counts (`gate_calculator.py`, the infinite starting line is accepted as a crossing); gate width follows the corridor, not 0.6 NM; SP/FP grace is 2 s, catalogue 1 s | S20 |
| N2 | 2.B2 without a declared sequence: `GateCalculator.create_gates` raises `KeyError` for the free targets, nothing is scored | S16 |
| N3 | 2.B3: an authored landing gate is never recognised (`takeoff_and_landing_gate_calculator.py` only looks for it after a finish point); the speed-inferred landing is recognised about a minute late | S18 |
| N4 | 2.A2: a missed hidden gate costs 180 once; the catalogue takes both the gate value and Emax as time error | S12 |
| N5 | Turnpoint hunts get backtracking penalties the catalogue does not have | S16 |
| N6 | Backtracking is not limited to the corridor of S10 4.24.5 | S19 |

- Not covered by scenarios yet: photo and marker evidence, quarantine breaches, 2.A8 take-off timing and route to SP,
  the 2.B2 fuel deadline, 2.A3 "turn points visited once".

## Phase 5 — Pilot and organiser flow

**S21. Backend.** The flight's own pilot may read and write their declaration until the cut-off (D6); organisers always.
Declaration status (required / missing / complete, errors) in the contestant and app flight data. Times entered relative
to SP are converted server-side; adaptive start supported (F17).

**S22. Web booking flow.** In `ScheduleFlightForm`, tasks that need a declaration continue to a pilot-facing,
phone-sized declaration step before the `airsportsapp://registered` signal is sent. Reuse the logic of
`ContestantDeclarationPage`, not its layout. "Edit declaration" on the pilot's own flight (F18).

**S22b. Flight order status for the pilot** (added 2026-11-27 at the user's request, with S22). Saving the declaration
starts the flight order generation (already gated: a task that needs a declaration does not generate one before it is
saved). The pilot must not have to wait for an e-mail: the own-flight data carries a flight order status (waiting for
the declaration / being made / ready / failed, with the reason) and the download link (`flight_order_path` exists);
the booking flow and "my flights" show it, refresh it until it is ready and then offer the download directly. S23
shows the same in the apps.

**S23. Apps** (`airsports-mobile`, separate repository). Show "Declaration needed" on the flight card and an
"Edit declaration" action that opens the web page; needs an app release (F19).

**S20b. Scoring explained to the organiser** (added 2026-11-27 at the user's request, runs after S20). An organiser
who starts a default CIMA task must not be surprised that scores are scaled against the best pilot and move until all
have flown, even without opening the scorecard. One plain-language summary per task type, generated in one place from
the registry and the task's scorecard (formula in words, task value, Qmax policy, which terms are relative to the best
pilot, percentage penalties, "provisional until all flights are finished") and served by the API, shown in:
- the scorecard editor (top of the page, above the fields);
- task creation, when a CIMA task type is chosen (short form, with the choice of Qmax policy explained);
- the navigation task page for organisers (a "How this task is scored" card with a link to the scorecard);
- the live map and results, as an explanation behind the "Provisional" badge, for pilots and spectators.
Also gives the measure entries of 2.A3 (V) and 2.A4 (S) their own wording in the score log.

**S24. Documentation.** Rewrite `11_CIMA_Task_Guide.md` for the new scorecards, scoring and declaration flow (F20).

## Phase 6 — Annex 9 leftovers and rule alignment (decided 2026-11-27)

- S25: dropped. Landing strips are judged at the field with judges and cameras; the system cannot detect them.
- S26: Air Sport Challenge on the Annex 9 scorecard (D7).
- S27: dropped. No route-to-SP / route-from-FP check for Air Sports Race, and the route editor will not draw those paths.
- S28: overall result by standings points (25/20/16/…) as a contest option.
- S29: rule alignment left to the implementer's judgment: 2.A4/2.A5 hidden gate value 100 (the catalogue's typical Vh),
  2.A7 "CM outside the circle" scores 100%, 2.A1 Tmax can be set in the web pages.

## Order and dependencies

S1 → S2 → S3 → S4 → S5 → S6 → S7 → S8 → S9 → S10 → S11…S20 (any order, one at a time) → S21 → S22 → S23 → S24.
S21–S22 can start after S13. Phase 6 is independent.

## Appendix — rules quoted

- **Qmax** (Annex 3, 3.4.1): "P = Q/Qmax x 1000. Where: Q = pilot scores, Q max = best score for the task". Absolute
  scores may be used alone or combined.
- **Task value** (Annex 3, 2.3.4): maximum score between 500 and 1500 points per task, announced beforehand.
- **Penalties** (S10 4.34.17, 4.34.19, 4.34.14): deducted after scoring; negative score becomes zero; whole numbers,
  0.5 rounded up. DNF and DSQ score zero.
- **Backtracking** (S10 4.24.5): more than 90° from the intended direction for more than 5 s in sequence, inside the
  corridor defined by the gate width; not within the turnpoint radius where the two corridors intersect; for microlights
  also rejoining the track before the point where it was left.
- **2.A1**: `Qh = 1000·H/Nh` (H = hidden gates crossed once, in order, right direction); `Qt = Emax·Nt − Et`, Emax 180,
  Emax per gate not flown; time from first crossing; `Q = Qh + Qt`; 50% for backtracking.
- **2.A2**: each hidden gate crossed scores Emax (180); twice or backwards invalidates; one point per second of error,
  at most Emax, Emax if not crossed; 50% for backtracking.
- **2.A3**: `V = N − Ep`; `Qp = 1000·V/Vmax`; `Qt = Emax·3 − Et` over SP, MP, FP; MP at T, FP at 2T; points declared
  after MP are invalid if flown before the MP time; turn points visited once.
- **2.A4 / 2.A5**: `Qh = Vh·Nh` (e.g. 100); `Qt = Σ(Vt − Ei)` for gates crossed (Vt e.g. 180); `Qv = Vs·S/Smax`;
  hidden gate crossed twice is invalid; quarantine breach 100%; 50% for backtracking.
- **2.A6 / 2.B2**: 100 per photo, 200 per time gate, bonus for the full correct sequence (2.A6 only); wrong photo −50%
  of its value; timing gate beyond 10 s: 10 pt/s; over maximum duration: 10 pt/s; quarantine breach 100%.
- **2.A7**: over SP and CM in a straight line, bank left, first 180° unscored, scoring from crossing X for 360° until X
  is crossed again, leave to WP. `P = (Rmin/Rmax − 0.5)·500`, Pmax 250. 20% for the altitude band; 100% if clockwise,
  CM outside the circle, SP/CM not overflown, radius limits (200–750 m) left, or ratio ≤ 0.5.
- **2.A8**: start with 2000; corridor 3 pt/s after 5 s; SP/FP 3 pt/s after 1 s, max 200, missed 200; take-off outside
  0–60 s: 100; route to SP / from FP not followed: 200 each; backtracking/circling 200 each; gate width 0.6 NM.
- **2.B3**: longest flight on limited fuel; quarantine breach 100%; prohibited area 100%; landing outside the area as
  briefed.
- **Annex 9, 6.7.5**: implemented in the "Air Sports Race 2025 (Annex 9)" scorecard.
