# CIMA Task Support User Manual

How to set up and run each supported CIMA task type on the Air Sports Live Tracking platform.

Which tasks exist and how they behave is defined in `CIMA_task_implementation_requirements.md` (repo root);
the CIMA task catalogue itself is `cima_task_catalog.md` in this folder. Tasks not listed here (for example 2.B1
Split Square) are not implemented.

---

## 1. The workflow at a glance

Every CIMA task goes through the same steps:

1. **Draw the route** in the Route Editor, using the **Task Route Guide** for the task type (section 2).
2. **Create the navigation task** from the route and pick the CIMA task type. The task gets the matching
   *task subtype* and a scorecard with the catalogue's starting score already applied (section 4).
3. **Add contestants** as usual.
4. **Declare, for the task types that need it** (2.A1, 2.A2, 2.A3, 2.A4, 2.A6, 2.B2): fill in each contestant's
   declaration (section 3). The contestant's route, gate times and scoring are compiled from it.
5. **Generate the flight order / navigation map** and fly. The live map shows the contestant's own declared
   route when the contestant is selected.

Tasks that need no declaration (2.A5, 2.A7, 2.A8, 2.B3) go straight from step 3 to step 5.

> **Visibility.** Whether CIMA task types appear for a given user depends on the deployment's access settings
> (`GATE_CIMA_TASK_VISIBILITY`, grants; see `CIMA_ROLLOUT_RUNBOOK.md`). If a CIMA template is missing from the
> Route Editor, it is an access question, not a bug.

> **All CIMA waypoints are drawn as circles** on the maps.

---

## 2. Route Editor: the Task Route Guide

In the Route Editor, open the **Task Route Guide** panel and choose the task type. Most templates are step-by-step
checklists that show how many of each marker you have placed and what is still missing. A few are *guide only*: they
describe what to build with the normal route tools.

Two conventions apply everywhere:

- **Hidden gates are secret points.** Convert an intermediate route point to a secret point in the point editor
  (or click the route line in view mode to insert one). There is no separate "hidden gate" point type.
- **Free-map markers** (catalogue turnpoints, timed turnpoints, circle markers) are placed anywhere on the map and
  are not part of a route line. **Route-insert markers** are inserted on the route.

### 2.A1 Curve navigation with time estimation

*Guide only.* Build a normal precision route (SP, turnpoints, FP). **At least one leg must be curved**: use the curve
tool while placing a point, or convert a leg in the point editor. Hidden gates are optional but recommended for
spatial-precision scoring.

### 2.A2 Precision navigation

*Guide only.* A normal precision route with visible turnpoints. Hidden gates along the corridor are optional but
recommended.

### 2.A3 Contract navigation with time controls

- **Route:** exactly three route waypoints: **SP, MP (middle point) and FP**.
- **Catalogue turnpoints:** any number of free-map markers the pilot may choose from.
- **Observation photos:** optional, and can be tied to specific catalogue turnpoints.

The general navigation map shows only the three backbone points (no lines between them) and the catalogue
turnpoints. The pilot's own order is applied through the declaration (section 3).

### 2.A4 Navigation over a known circuit

*Guide only.* Build the known circuit. Hidden gates and observation photos are both optional; the task normally uses
at least one kind of evidence.

### 2.A5 Navigation with unknown legs

The route is a true backbone plus decoy branches:

1. Build the **backbone route**: the route actually flown.
2. Click a backbone waypoint to make it an **unknown-leg trigger**. The wizard then goes straight to placing that
   trigger's **dummy waypoints** on the map.
3. Optionally add hidden gates on the backbone and observation photo markers.

Contestants see only disjoint route segments that run through each unknown-leg trigger and its dummy waypoints.
The flight order includes a section with the unknown-leg photos (course printed on each) in arbitrary order. On the
live map, hiding secrets shows the contestant's view; showing secrets shows the editor's full view.

**False (decoy) photos.** To make identification harder, add photos that match no real feature:

1. In the navigation task's management menu, open **Flight orders & documents → Manage photos**.
2. In the **False photos** section (shown for unknown-legs tasks only), click **Add false photo**.
3. Click the map where the decoy should be taken, then give it a **name** and, optionally, a **course** in degrees
   (0-359) to print on it. The name must not match a real route feature or an existing photo.
4. Repeat for as many decoys as you want. Decoys can be deleted from the same list.

When flight orders are generated, the decoys are mixed in with the real unknown-leg photos in random order. The
order is re-randomised for each contestant's flight order. Decoys belong to the route, so every navigation task made
from the same route shares them.

### 2.A6 Turnpoint hunt

No route backbone. Place:

- **Exactly three timed turnpoints** (CP1, CP2, CP3). Their crossing times are declared per contestant.
- Any number of **catalogue turnpoints** (untimed).
- Optionally, observation photo markers tied to catalogue turnpoints as evidence targets.

### 2.A7 Circle

Four free-map markers, each exactly once:

| Marker | Meaning |
|---|---|
| Circle start (SP) | Where the task starts |
| Circle center (CM) | Centre of the circle |
| Circle entry (X) | Entry point; the straight line from SP to CM is validated before the orbit |
| Circle exit (WP) | Next waypoint after leaving the circle |

The centre is drawn with an inner and an outer circle for the smallest and largest allowed radius.

### 2.A8 Precision navigation ANR

*Guide only.* Build the ANR route with a start and a finish. Route-to-SP and route-from-FP auxiliary paths are
handled separately.

### 2.B2 Limited fuel turnpoint hunt

No route backbone. Same markers as 2.A6: **exactly three timed turnpoints**, plus any number of catalogue turnpoints
and optional observation photos. This is not a precision task: every gate crossing scores.

### 2.B3 Duration

- **Take-off gate** and **landing gate**: optional, but give the most precise measured duration. Without them,
  take-off is inferred from a sustained near-zero speed followed by a rise, and landing from a sustained drop to
  near-zero speed.
- **Landing area:** draw the duration landing area polygon (required).

---

## 3. Contestant declarations

Open the navigation task in the administration section, find the contestant in the list, and use
**Actions → Edit declaration**. The entry only appears for task types that take a declaration (2.A1, 2.A2, 2.A3,
2.A4, 2.A6, 2.B2). Fill in the form and click **Save declaration**.

The page also shows a **declaration preview** (gate predictions, turnpoint overrides, or the declared route) so the
result can be checked before flying.

### 2.A1 and 2.A2: known time gate predictions

Enter the **predicted time** for each gate (date and time).

- **2.A2:** every gate needs a prediction; Save stays disabled until all are filled.
- **2.A1:** at least one gate prediction is required. Only the FP is checked against Tmax; the page shows the task's
  Tmax in minutes from the starting point.

### 2.A3: declared sequence and T

- **Declared T:** time from SP to MP and from MP to FP, in seconds. Required.
- **Declared sequence:** place each catalogue turnpoint in the lane **before MP** or **after MP**, and order them
  with the arrow buttons (move up/down, move to the other lane, remove). SP is always first and FP always last.
  At least one turnpoint is required.

Once saved, the contestant flies a normal precision task over the declared route. Scoring, waypoint lists and the
live map follow the declared route.

### 2.A4: optional time overrides

For any turnpoint you may declare a specific time, overriding the time implied by the declared groundspeed for that
point only. Leave a turnpoint blank to fly it at the constant declared speed. The declaration is always saveable;
with no overrides, the task is flown at the declared speed.

Speed-keeping is scored per leg against the declared speed. Legs next to an overridden turnpoint are skipped, since
the pilot is expected to deviate there.

### 2.A6 and 2.B2: timed points, order and fuel

- **Predicted time** for each of the three timed turnpoints (required). The three are ordered automatically by
  predicted time.
- **Declared order:** arrange the free (catalogue) targets with the **Available targets** and **Declared order**
  lists. Free targets may be placed before, between or after the timed ones. The compulsory points are locked in
  place.
- **2.B2 only:** enter the **declared fuel endurance (minutes)**.

### Locked declarations

Some declarations hold absolute times (2.A1, 2.A2, 2.A4 overrides, 2.A6, 2.B2). While such a declaration exists,
the contestant's take-off/finish time can only be changed if every declared time still falls inside the new
window. Otherwise use **Clear declaration** first. The page shows a warning when this applies.

For adaptive-start contestants, times are relative to passing the starting point instead of absolute.

---

## 4. Scoring

CIMA scoring starts every contestant at the catalogue's maximum and subtracts penalties, with results sorted
**descending**. When you create a task of a CIMA type, the scorecard copy is initialised to this baseline:

| Task | Starting score | Notes |
|---|---|---|
| 2.A1, 2.A2, 2.A3, 2.A4, 2.A5 | 1000 | Normalised so P = 1000 · Q / Qmax |
| 2.A7 Circle | 250 | Maximum from the catalogue |
| 2.A8 ANR | 1000 | Catalogue formula scaled by one half |
| 2.A6, 2.B2 | 0 | Additive: the score climbs from zero as targets are achieved |
| 2.B3 Duration | not preset | Check the scorecard before flying |

Scorecard values (for example the circle performance factor, the speed-keeping tolerance and penalty, and the
turnpoint-hunt target values) are edited in the task's scorecard. Backtracking and other penalties apply as
configured there.

### Task-specific notes

- **2.A1, 2.A2:** visible time gates and hidden gates; backtracking is penalised.
- **2.A3:** points for the declared sequence and mandatory time points.
- **2.A4:** hidden gates, observation evidence and speed-keeping.
- **2.A5:** unknown-leg sequence plus observation evidence and hidden gates.
- **2.A6:** predicted sequence, compulsory timing gates and observation evidence.
- **2.A7:** circle entry, radius, direction and altitude spread.
- **2.A8:** route-to-SP, route-from-FP, take-off timing and quarantine rules.
- **2.B2:** all gate crossings score, the three timed gates are checked, plus fuel compliance.
- **2.B3:** the duration between take-off and landing, with a penalty for landing outside the specified area.

---

## 5. Known gaps

- 2.B3 Duration has no preset scoring baseline; verify its scorecard values yourself.
- The route-editor guides for 2.A1, 2.A2, 2.A4 and 2.A8 are guidance only: the editor does not check that the route
  has what the task needs, so confirm the route yourself.
