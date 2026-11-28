# Plan: route editor guidance, modes and route integrity

Written 2026-11-28. Status 2026-11-28: R1 to R7 are done on the branch `route-editor-guidance` (backend suite 3187 passed, 2 expected
failures, before the last 2.A4 correction; frontend 870+ tests). Nothing has been tried in a browser. One change from the
plan: 2.A4 needs at least one timed turn point, hidden gate or photo, because the timed turn points of a known circuit
are its known time gates. Follows `PLAN_task_scoring_reliability.md` and builds on its task-type registry.

## Goal

Building a route for a task should be as easy as possible. Today the Task Route Guide is a side panel that half of the
task types cannot act from, the editor does not show clearly which mode it is in, hidden gates are placed by an
undocumented click, and moving a waypoint can leave hidden gates and photos where the rules do not allow them.

## What the code does today (checked)

- **Guide.** `TaskWizardPanel.tsx` lists 13 templates from `taskTemplates.ts`. Seven are `guideOnly` (precision, ANR, Air
  Sport Challenge, 2.A1, 2.A2, 2.A4, 2.A8): a checklist without buttons. A step stays active until "Stop active step" /
  "Done" is pressed, and the next step is started by hand. Step texts live in the frontend, and `RouteEditor.tsx` tests
  template ids (`cima_a3`, `cima_a5`, `cima_a6`, `cima_a7`, `cima_b2`, `cima_a1`) for special behaviour.
- **Modes.** `Toolbar.tsx` has the modes `view`, `add_point`, `add_catalogue_turnpoint`, `add_observation`,
  `add_polygon` and the gate modes, with a one-line hint in the toolbar. Clicking an existing marker already selects it
  and returns to `view` in every mode, so a waypoint placed by accident comes from missing the marker, not from the click
  rule. There is no undo anywhere in the editor.
- **Hidden gates.** In `view` mode a click on the line of a straight leg inserts a hidden gate there
  (`renderers.ts`, the leg polyline handler). Nothing on the screen says so. A click on a curved leg only selects the
  leg's end point. The blue dot at the middle of a straight leg inserts a regular turn point and starts dragging it.
- **Curves in the backend.** `EditableRoute` expands a curved leg into 20 generated points of type secret
  (`on_curved_segment=True`, not timed, not checked). A real hidden gate between two curved legs is an ordinary waypoint
  to it, so no rule stands in the way; whether gate direction and scoring come out right is to be proven by test (R5).
- **Moving a waypoint.** A hidden gate is an ordinary point of the route, so when a neighbouring waypoint moves it stays
  where it is and the route bends through it. Photos (`ObservationMarker`) stay too and can end up beyond the maximum
  observation distance (0.5 NM by default).
- **Tags.** `EditableRoute.compatible_task_types` is computed on save by `services/route_compatibility.py` from the
  registry's route requirements. `intended_task_types` is the author's choice, but it is pre-filled with everything
  compatible unless a template was followed. The route list shows the intended types and filters on the compatible ones.
  A plain route (a track with waypoints) is compatible with seven types, among them 2.A4, which requires nothing more.

## Decisions (from the conversation of 2026-11-28)

| # | Decision |
|---|---|
| R-D1 | A new route opens with the choice of task, which starts the guide. It can be closed, and then the editor is as it is today. Existing routes open as today. |
| R-D2 | Steps with a fixed count move on by themselves. Open-ended steps get one "Done, next step" button. |
| R-D3 | The mode is always visible on the map, and a misplaced point can be undone. |
| R-D4 | Hidden gates get their own tool. A plain click on a leg in select mode inserts nothing. The mid-leg dot keeps inserting a regular waypoint. |
| R-D5 | Hidden gates can be placed on curved legs. |
| R-D6 | When a leg changes, the hidden gates on it are removed: a hidden gate belongs to a feature on the ground (a road crossing) and may not bend the route. Photos that are then out of range are removed. The user is told what was removed and can undo it. No confirmation dialog before the move. |

## Slices

One Sonnet sub-agent per slice, verified and committed one at a time, as in the previous plan. Frontend tests with
vitest, backend tests in `tracker_daphne`, never two pytest runs at once.

### R1 — Registry: guide steps, flags and a tighter 2.A4 (backend, small frontend)

- Each `RouteRequirement` gets what the guide needs to act on it: a help text and the tool that satisfies it (a small
  enumeration: route waypoint, hidden gate, known time gate, catalogue turn point, circle marker, photo, landing area,
  gate lines, extension waypoints). The compatibility API (`editableroutes-task-compatibility`) already returns the
  requirements; it now returns these too.
- The special behaviour that `RouteEditor.tsx` reads from template ids becomes registry flags returned with the task
  type (three-point backbone, standalone timed turn points, circle markers, curve required, extension waypoints).
- 2.A4 requires at least one of: known time gate, hidden gate, photo (a new "any of" requirement).
  `ROUTE_COMPATIBILITY_RULESET_VERSION` goes up, so stored tags are recomputed.
- Tests: registry tests for the new fields, compatibility of a plain route (no longer 2.A4), the API shape.

### R2 — The guide: task first, every step actionable, next step (frontend)

- A new route (no id in the URL) opens with the task choice over the map: the task families the user may see, one line
  each, and "Build without a guide". Choosing a task opens the guide with its first unmet step active.
- `taskTemplates.ts` shrinks to what is not in the registry (grouping, order). `guideOnly` goes: every unmet requirement
  has a button that starts its tool.
- A step with a fixed count (minimum equals maximum) ends when the last one is placed and the next unmet required step
  starts. An open-ended step shows "Done, next step". Optional steps are only started from the list.
- The guide can be closed and reopened at any time; closing never changes the route.
- Tests: `taskRequirements.test.ts`, `routeEditorWizardTransitions.test.ts`, and a rendering test of the panel.

### R3 — Modes and undo (frontend)

- One banner on the map for every placing mode, guide or toolbar: what a click does, "Esc to stop", a stop button. In
  select mode there is no banner. `WizardActionBanner` becomes this banner.
- The cursor is a crosshair while placing and an arrow otherwise.
- Esc returns to select mode.
- Larger click targets for existing points, so that a click meant for a point does not fall through to the map.
- Undo and redo for the route content (points, gates, photos, polygons): Ctrl+Z / Ctrl+Shift+Z and buttons in the
  toolbar. One history for the editor, with a drag counted as one step. This is also what R4 uses.
- Tests: the history as a pure module, the mode transitions.

### R4 — Hidden gate tool and route integrity when a leg changes (frontend)

- A toolbar tool "Hidden gate" (and the guide's hidden gate step): the banner says "Click a leg to place a hidden gate".
  The click on a leg in select mode selects nothing new and inserts nothing. The mid-leg dot gets a tooltip, "Drag to
  add a waypoint".
- A pure function decides what a change of the route removes: the hidden gates on every leg whose end points or shape
  changed (a waypoint moved, deleted or inserted, a curve reshaped, the route reversed is not a change), and the photos
  farther from the new route than the maximum observation distance. Known time gates inserted on a leg by the guide are
  checked for the same problem and treated the same way if they have it.
- After the change a notice names what was removed ("Removed hidden gates Secret 3, Secret 4 and photo P2: the leg they
  were on has changed") with Undo, which restores the route as it was before the move.
- While dragging, the hidden gates and photos that the drop would remove are shown faded, so the notice is no surprise.
- Tests: the pure function (move, delete, insert, curve reshape, photo exactly at the limit), the notice and its undo.

### R5 — Hidden gates on curved legs (frontend, backend tests)

- A click on a curved leg with the hidden gate tool splits the curve at that point into two curves that together have
  exactly the shape of the old one (de Casteljau split of the quadratic curve), with the hidden gate between them.
  Removing that gate (by hand or through R4) joins the two curves again where they still form one curve, otherwise the
  legs stay as they are.
- Backend: a test that a route with a hidden gate between two curved legs builds, that the gate's line is square to the
  curve there, and a simulated flight along the curve that scores the gate (2.A1, where curved legs are required). If
  the build or the scoring needs a change, it is reported before it is made.
- The route editor's check that a curved leg exists (2.A1) still counts the split curve as curved.

### R6 — Tags: "made for" and "also suitable for" (frontend, small backend)

- `intended_task_types` is only what the author ticked or the task chosen in the guide. It is no longer pre-filled with
  everything compatible. Existing routes whose intended list equals their compatible list are treated as "not chosen"
  (decided on read, no data migration).
- The route card shows "Made for" (intended) and, less prominent, "Also suitable for" (the other compatible families).
  The filter of the list has both: made for, or suitable for.
- The route settings show the same split, with the reason next to each type the route does not suit yet.
- Tests: the card's grouping helper, the filter, the serializer.

### R7 — Guide and help texts

- `HelpView.tsx` in the editor and the route editor pages of the docs site (`airsports_static/src/pages/docs/`): the
  task choice, the modes, the hidden gate tool, what happens when a waypoint moves, the tags.

## Order

R1 → R2 → R3 → R4 → R5 → R6 → R7. R3 must come before R4 (undo). R6 only depends on R1.

## Branch

A new branch `route-editor-guidance` from `task-scoring-reliability`, with its own pull request based on that branch
until #844 is merged. It stays well under 100 changed files, so CodeRabbit can review it.

## Not in this plan

- Drawing the route to SP and from FP (dropped, see the scoring plan).
- A redesign of the editor's layout beyond the banner, the task choice and the tools named here.
- Moving a hidden gate with its leg: decided against (R-D6), because the gate belongs to a feature on the ground.
