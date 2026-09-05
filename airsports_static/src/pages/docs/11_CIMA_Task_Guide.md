---
layout: ../../layouts/DocsLayout.astro
title: "CIMA and Legacy Task Guide: Routes, Tasks, and Scoring"
---

# CIMA and Legacy Task Guide: Routes, Tasks, and Scoring

ASLT supports two families of navigation task: the platform's original **Legacy** task types (Precision, ANR, Air Sports Challenge, Poker Run, Landing), and the **CIMA** task catalogue — the task designs defined in FAI Sporting Code Section 10, Annex 4, Part 2 (Microlights), tasks **2.A1** through **2.B3**. This guide covers both: how to build the route for each task type in the route editor, how to create the matching navigation task, and how to configure and read its scoring.

> The route wizard (see below) walks you through the required points for each task type interactively. This guide is the reference to read alongside it — especially for the parts the wizard can't tell you: which scorecard to pick, which fields actually affect scoring, and what the contestant declaration step needs from you.

---

## 1. The three pieces of every navigation task

1. **A Route** — the points, gates, and polygons drawn in the route editor.
2. **A Navigation Task** — links a route to a scorecard and (for CIMA) a task subtype.
3. **A Scorecard** — the penalty/scoring rules. When you create a task, ASLT copies your chosen scorecard onto the task, so tuning it never affects other tasks or the shared "original" templates.

If you haven't used the platform before, read [Route Creation and Task Configuration](./04_Route_Creation_and_Tasks) and [Competition Types and Scorecards](./07_Competition_Types_and_Scorecards) first — this guide builds on both and mostly focuses on what's specific to CIMA.

---

## 2. Legacy vs. CIMA: what actually changes for you

**Legacy tasks** (Precision, ANR, Air Sports Challenge, Poker Run, Landing) are the platform's original task types — free-form routes, no contestant declaration step, and the traditional scoring model: every contestant starts at **0 points**, every infraction **adds** penalty points, and the **lowest total wins**.

**CIMA tasks** are structured according to the FAI catalogue. Each one is a specific, named task design (e.g. "2.A3 Contract navigation with time controls") with its own required route shape, its own rules for what the organizer authors versus what the contestant declares before flight, and — importantly — its own scoring formula from the catalogue, which is **not** the legacy ascending-penalty model.

### The scoring-direction difference

Read the FAI catalogue's scoring sections and you'll find contestant scores expressed as an achievement out of a maximum, where **highest wins**, not lowest. Three patterns appear, depending on the task:

- **Fixed maximum, subtract penalties.** 2.A8 (ANR): *"The competitor will start with 2,000 points"*, and penalties (corridor excursions, SP/FP timing errors, missed gates) are subtracted directly.
- **Normalized quality score.** 2.A1, 2.A2, 2.A3, 2.A4, 2.A6: raw points are earned per gate, time point, or photo (each already computed as *"gate value minus timing error"*, or *"count correct out of total"*), summed into a raw quality total **Q**, then scaled onto a fixed 0–1000 scale: **P = 1000 × Q / Qmax**. Critically, **Qmax is derived from the route and declaration** — it depends on how many hidden gates, time gates, or catalogue points you (the organizer) actually placed, and in some tasks on what the contestant declared. Two organizers running the same task design with a different number of hidden gates get a different Qmax, but both contestants' final P is on the same comparable 0–1000 scale.
- **Direct formula.** 2.A7 (Circle): the score is computed directly from the flown radius ratio, P = (Rmin/Rmax − 0.5) × 500, capped at Pmax = 250 — there's no "penalty accumulation" at all.

Scorecard already has generic fields for the first pattern: **`score_sorting_direction`** (`asc`/`desc` — is lowest or highest the winner) and **`initial_score`** (what every contestant starts from). Setting `score_sorting_direction=desc` and `initial_score` to a maximum, with penalties subtracted rather than added, reproduces the fixed-maximum pattern exactly.

> ⚠️ **Current implementation status.** For 2.A1–2.A5 and 2.A8, creating the task now automatically sets `score_sorting_direction=desc` and `initial_score` to the catalogue's fixed maximum (1000 or 2000) on that task's own scorecard copy — the shared "FAI Precision"/"FAI ANR" originals legacy tasks use are never touched. 2.A7 (Circle) got the same treatment (`initial_score=250`) plus a calculator fix: it previously added a positive "achievement" value for a good flight through the same code path used to add a 250-point value for an outright rule violation, which under a descending scorecard made a near-perfect circle rank almost as badly as a disqualifying one — it now correctly emits the deficit from 250, so a perfect circle nets the full 250 and a violation nets 0. `Initial score`/`Score sorting direction` are also now editable per task in the scorecard editor's **General** group (see [Tuning the scorecard for your CIMA task](#tuning-the-scorecard-for-your-cima-task)), so you can override any of these defaults. **Still not implemented:** the catalogue's exact `P = 1000 × Q / Qmax` normalization formula for 2.A1–2.A5 (today those subtypes reach the same *contestant ranking* via ascending-style penalty accumulation reversed in sign, not the literal formula — the displayed score is "1000 minus accumulated penalty magnitude," not a true Q/Qmax quality ratio); and for 2.A6/2.B2, whose achievable maximum is inherently route-dependent (it scales with how many photos/gates you place), there is still no calculator computing it and no safe default — `initial_score` defaults to 0 there and must be set manually if you want an "out of N" figure. Everything else in this guide (route construction, task creation, contestant declaration, and every other scoring field) reflects what's live today.

---

## 3. Building routes: the Task Wizard panel

Start here — you need a route before there's anything to attach a task to. In the route editor, click **Task Wizard** (toolbar or sidebar footer) to open the **Task Route Guide** panel. It lists every task type you have access to, grouped Legacy/CIMA. Pick your task type and the panel turns into a checklist of the points/gates/polygons that task needs, with a running count against each step's minimum (and maximum, where fixed) — a step goes green once satisfied. This is the fastest way to build a route correctly; the per-task sections below explain *what* each step means and *why*.

---

## 4. Creating the navigation task, scorecard, and declarations

With a route built, the rest follows in order: attach it to a navigation task, adjust the scorecard, then (for the task types that need it) fill in each contestant's declaration.

### Creating the task

You reach navigation task creation two ways:

- **From the route you just built:** open the route in the route library and choose to create a task from it — this skips route selection since the route is already fixed.
- **From a contest:** open the contest, click **New Navigation Task**. You'll import/select an existing route as part of the wizard.

Either way, the wizard's first step is a single **task type** dropdown with two groups, **Legacy** and **CIMA**. Legacy entries are the coarse families (Precision, ANR Corridor, Air Sports Race, Air Sport Challenge, Poker run, Landing); CIMA entries are listed by their official designation, e.g. *"2.A3 Contract navigation with time controls"*, *"2.A7 Circle"*. Picking a CIMA entry sets both the coarse family and the specific subtype for you — there's no separate subtype field to fill in at this step.

If you already picked a route, the dropdown **only offers task types the route actually supports** — the wizard checks the route's authored points against each subtype's requirements (e.g. it won't offer 2.A7 Circle unless you've placed circle start/center/entry/exit markers) and tells you what's missing if nothing matches.

The next step re-shows the task subtype (pre-filled from your choice) alongside the usual task fields (name, start/finish time, etc.) and a **scorecard** dropdown. The scorecard list is filtered by coarse family only, not by CIMA subtype — for any task in the Precision family (legacy Precision, or any of 2.A1–2.A6), you're choosing between "FAI Precision", "FAI Precision no procedure turns", or "NLF Precision 2020"; for ANR-family tasks (legacy ANR, or 2.A8), you're choosing between "FAI ANR 2022", "FAI ANR 2017", or "FAI Air Rally 2020". Pick whichever is closest to your rules — you'll refine it next.

Submitting creates the task with **its own private copy** of the scorecard you picked.

**If you don't see CIMA options at all:** your contest doesn't have CIMA task access yet — this is a separate entitlement from ordinary contest creation. Even if a CIMA entry is visible, submitting will be rejected with *"This task requires the cima task package, but the current contest only has access to other task groups"* until that access is granted. Contact whoever administers your organization's access tier.

### Tuning the scorecard for your CIMA task

Open the task, click **Scorecard**. This opens the per-task scorecard editor (your private copy — editing it never touches the shared originals or other tasks). Alongside the usual gate-timing and backtracking fields, CIMA tasks expose extra groups relevant to their subtype:

| Group | Fields | Relevant to |
|---|---|---|
| General | Score sorting direction, Initial score | every task |
| ANR route | ANR route to SP penalty, ANR route from FP penalty | 2.A8 |
| Duration | Compulsory timing tolerance (s), Maximum task duration (min), Maximum task duration penalty, Fuel deadline penalty, Duration normalization policy, Duration residual fuel required | 2.B2, 2.B3 |
| Circle | Circle radius min (m), Circle radius max (m) | 2.A7 |
| Speed keeping | Speed keeping tolerance (kt), Speed keeping penalty per kt | 2.A4 |

**General** is where the max-minus-penalties model from [§2](#2-legacy-vs-cima-what-actually-changes-for-you) actually gets set. Creating a 2.A1–2.A5 or 2.A8 task now sets it for you automatically (`Descending` + the catalogue's fixed maximum: 1000, or 2000 for 2.A8); 2.A7 gets `Descending` + `250`. You can override `Initial score` here for any task — this is also where you manually enter a computed maximum for 2.A6/2.B2 (see [§2](#2-legacy-vs-cima-what-actually-changes-for-you)'s note on their route-dependent maximum; there's no automatic calculator for it yet, so work it out from your placed photos/gates and enter it here).

If you make a mistake, use **Restore from original** on the task's score page to reset the copy back to the scorecard template you started from — this reapplies the same automatic subtype default, not just the raw original scorecard's ascending/zero settings.

### Contestant declarations

Tasks 2.A1, 2.A2, 2.A3, 2.A4, 2.A6, and 2.B2 need each contestant to declare something before flying (predicted crossing times, a chosen sequence, or a fuel endurance) — see each task's section below for what. Once contestants are registered on the task, open the task's contestant list and use **Edit declaration** next to a contestant to fill this in; a **Declaration preview** panel on the page shows exactly what will be used for scoring before you save. 2.A5, 2.A7, 2.A8, and 2.B3 need no contestant declaration — they're flown and scored purely from the route/task configuration.

---

## 5. Legacy task types (quick reference)

Covered in full in [Route Creation and Task Configuration](./04_Route_Creation_and_Tasks) and [Competition Types and Scorecards](./07_Competition_Types_and_Scorecards). Summary:

- **Precision** — SP/TP/FP route with optional secret (hidden) gates and procedure turns. Ascending penalty scoring, lowest wins.
- **ANR (Air Navigation Race)** — a route flown inside a corridor of a given width; scored on corridor excursions, timing, and backtracking.
- **Air Sports Challenge** — a hybrid of Precision and ANR: precise timing plus a variable-width corridor.
- **Pilot Poker Run** — gate polygons over target airfields; crossing one deals a card. Uses descending sort (best poker hand wins), unlike the other legacy types.
- **Landing** — scored on the deck section where the aircraft touches down.

---

## 6. CIMA task types, one by one

Each section covers: what the task tests, how to build the route, how to configure the navigation task, what the contestant declares (if anything), and how the catalogue scores it.

### 2.A1 — Curve Navigation with Time Estimation

**Tests:** flying a precisely curved course and estimating crossing times at known gates, validated against hidden gates along the way.

**Build the route:**
1. Build a normal precision route (start, turn points, finish) — this task **requires at least one curved leg**; use the curve tool (hold the curve modifier while placing a point, or convert a leg afterward in the point editor) for at least one section.
2. Your ordinary visible route points are the known time points by default. Add explicit known-time markers only if you need extra timing points beyond the normal route geometry.
3. Hidden gates are optional but recommended — insert a few along the route (click the route line in the point editor) to add spatial-precision scoring.

**Create the task:** pick *"2.A1 Curve navigation with time estimation"*, a Precision-family scorecard.

**Contestant declaration:** required. Each known/compulsory time point on the route gets a **Predicted time for {point}** field on the declaration page — the pilot's estimated crossing time, measured from the start point.

**Scoring (per the catalogue):** spatial precision `Qh = 1000 × H/Nh` (H = hidden gates correctly crossed once, in order and proper direction, out of Nh total); time precision `Qt = Emax×Nt − Et` (Emax is typically 180s, Et is the summed absolute timing error, capped at Emax per gate); total `Q = Qh + Qt`, final score `P = 1000×Q/Qmax`. A gate crossed more than once is scored from its first crossing; crossing the same gate twice in any direction invalidates it. A 50% penalty applies for backtracking.

### 2.A2 — Precision Navigation

**Tests:** flying each leg at a constant declared speed and estimating arrival times at every known turn point.

**Build the route:** build the visible route with start, visible turn points, and finish — no curve requirement. Hidden gates along the corridor are optional but recommended for spatial-precision scoring.

**Create the task:** pick *"2.A2 Precision navigation"*, a Precision-family scorecard.

**Contestant declaration:** required — a predicted arrival time for every turn point in the circuit, including the finish point.

**Scoring:** each hidden gate crossed scores a fixed value (typically 180 points), invalidated if crossed twice or in the wrong direction; `Qp = Emax × Ng` (Ng = gates correctly crossed); time precision `Qt = Σ Ei` (summed absolute timing error across gates, Emax per gate if not crossed); total `Q = Qp + Qt`, final `P = 1000×Q/Qmax`. 50% penalty for backtracking.

### 2.A3 — Contract Navigation with Time Controls

**Tests:** the pilot chooses their own route through a catalogue of turn points, flying a mandatory middle point (MP) at exactly T seconds after the start, and the finish point (FP) at exactly 2T seconds after the start.

**Build the route:**
1. Build exactly **three** route waypoints representing SP, MP, and FP (this is the fixed backbone).
2. Place the catalogue turnpoints the pilot may later choose to fly, in the free map area.
3. Optionally add photo markers and associate them with specific catalogue turnpoints.

**Create the task:** pick *"2.A3 Contract navigation with time controls"*, a Precision-family scorecard. The general navigation map only shows SP/MP/FP as circles with no connecting lines to the catalogue points — the actual flown route is per-contestant.

**Contestant declaration:** required, and this is the defining feature of the task. On the declaration page, drag catalogue turnpoints into two ordered lanes — **Before MP** and **After MP** — and set **Declared T (seconds)**: the interval from SP to MP, and from MP to FP. The compiled route, scoring, waypoint list, and live/contestant maps all reflect this per-contestant declared sequence, not a shared route.

**Scoring:** `V = N − Ep` (N = declared turn-points flown in order, excluding SP/MP/FP; Ep = declared points not flown or out of order, including SP/MP/FP); `Qp = 1000 × V/Vmax`. Time estimation: `Qt = Emax×3 − Et` (Et = summed absolute error at SP, MP, FP; Emax typically 180s). Total `Q = Qp + Qt`, final `P = 1000×Q/Qmax`. Points declared after MP are invalid if flown before MP's designated time. 50% penalty for backtracking.

### 2.A4 — Navigation over a Known Circuit

**Tests:** following a known circuit and identifying ground features/photos or crossing hidden gates, optionally with a declared or briefed groundspeed and per-point time overrides.

**Build the route:** build the known circuit first with the normal route tools. Neither hidden gates nor observation/photo markers are required, but the task typically uses at least one form of evidence — add hidden gates, photo markers, or both.

**Create the task:** pick *"2.A4 Navigation over a known circuit"*, a Precision-family scorecard. If the task includes a speed element, set **Speed keeping tolerance (kt)** and **Speed keeping penalty per kt** on the scorecard (the pilot can fly the declared groundspeed as airspeed with zero wind, already supported directly).

**Contestant declaration:** optional per turnpoint — the declaration page lists every turnpoint with a **Declared time override for {point} (optional)** field. Leave a point blank to score it from the declared/briefed groundspeed instead; fill it in to override just that point's expected time.

**Scoring:** spatial precision `Qh = Vh × Nh` (Vh = per-gate/marker value, e.g. 100; markers within 2mm score full value, 2–5mm score half, beyond 5mm or off-track score zero); time precision `Qt = Σ(Vt − Ei)` for gates crossed (Vt = gate value, e.g. 180); speed `Qv = Vs × S/Smax` when included. Total `Q = Qh + Qt + Qv`, final `P = 1000×Q/Qmax`. 50% penalty for backtracking; a hidden gate crossed twice is invalidated.

### 2.A5 — Navigation with Unknown Legs

**Tests:** the pilot only sees route segments up to a photo marker printed with a course to turn onto; the true backbone route (and where the segments actually connect) is hidden from them.

**Build the route:**
1. Build the true backbone route first — the actual route the contestant flies, including curves and photo observation markers as needed.
2. Click a backbone waypoint to mark it as an **unknown-leg trigger**; the wizard immediately switches to placing that trigger's dummy waypoints.
3. For each amber trigger, click the map to add dummy branch waypoints — these extend the visible segment shown to the contestant without being part of the real backbone.
4. Hidden gates directly on the true backbone, and photo/observation markers, are both optional but recommended as scoring evidence.

The contestant only ever sees disjoint segments: from the last visible point, through the unknown-leg trigger (shown as a photo with a course printed on it), through its dummy waypoints. You can add extra "false" photos that don't correspond to any real trigger, to make the task harder — the route editor supports registering these directly.

**Create the task:** pick *"2.A5 Navigation with unknown legs"*, a Precision-family scorecard.

**Contestant declaration:** none — the task is flown identically by every contestant from the authored route.

**Scoring:** spatial precision `Qh = Vh × Nh` (Vh e.g. 100 per correctly crossed hidden gate or correctly placed mark; partial credit for near-miss marks, zero for off-track); time precision (if included) `Qt = Σ(Vt − Ei)`, capped per gate at Vt (e.g. 180). Total `Q = Qh + Qt`, final `P = 1000×Q/Qmax`. 50% penalty for backtracking; treat every active track line as scoreable if the task has more than one (e.g. cog-wheel style unknown legs).

### 2.A6 — Turnpoint Hunt

**Tests:** finding and identifying as many photographed turnpoints as possible, in a predicted order and within a predicted time, with three compulsory timing gates.

**Build the route:** this task has **no route backbone** — everything is a free-map marker.
1. Place exactly **three** standalone timed turnpoints (CP1/CP2/CP3) — their crossing times and order are declared per contestant, not fixed on the route.
2. Place any number of untimed catalogue turnpoints for the pilot to choose from.
3. Optionally add photo markers associated with catalogue turnpoints as identification targets.

**Create the task:** pick *"2.A6 Turnpoint hunt"*, a Precision-family scorecard. Set **Compulsory timing tolerance (s)** — the catalogue's default tolerance is 10 seconds either side of the predicted time.

**Contestant declaration:** required. Before flight, the pilot declares a predicted time for each of the three compulsory gates (**Predicted time for {gate}**) and their intended visiting order for all chosen turnpoints via drag-and-drop.

**Scoring:** typically 100 points per correctly identified photo, 200 points per correctly crossed time gate, plus a bonus for flying the full, correct sequence — this maximum is inherently **route-dependent** (it scales with how many photos and gates you place). Penalties: breach of quarantine −100%; photo wrongly identified on the map −50% of that photo's score; timing gate error beyond the 10-second tolerance, −10 points/second; time over the maximum task duration, −10 points/second.

### 2.A7 — Circle

**Tests:** flying a precise 360° circle of the pilot's own chosen radius (between 200m and 750m) around a center marker, holding altitude within a 200ft band.

**Build the route:** place four free-map markers — **Circle start (SP)**, **Circle center (CM)**, **Circle entry (X)**, and **Circle exit (WP)**, in that order. The route editor renders the center marker with inner/outer rings showing the allowed radius range.

**Create the task:** pick *"2.A7 Circle"*, a Precision-family scorecard. Set **Circle radius min (m)** and **Circle radius max (m)** on the scorecard (catalogue defaults: 200m / 750m).

**Contestant declaration:** none — every contestant flies their own chosen radius within the same authored limits.

**Scoring:** the pilot flies straight over SP then CM to enter, banks left, and the first 180° are unscored orientation; scoring starts on crossing the entry line and ends on crossing it again after a full 360°. `P = (Rmin/Rmax − 0.5) × 500`, capped at `Pmax = 250`. A 20% penalty applies for exceeding the 200ft altitude band. A 100% penalty applies if the circle is flown clockwise, if the center marker ends up outside the flown circle, if SP/CM aren't overflown within the briefed limits, if the aircraft leaves the radius limits, or if the Rmin/Rmax ratio is 0.5 or smaller.

### 2.A8 — Precision Navigation Air Nav Race (ANR)

**Tests:** flying a defined corridor (straight and/or arc legs, given width) at a declared groundspeed, crossing SP and FP at specific times.

**Build the route:** build the ANR route path with start and finish as usual. Auxiliary route-to-SP and route-from-FP paths (if you want compliance checking on the transit legs) still need to be authored separately — they're optional.

**Create the task:** pick *"2.A8 Precision navigation ANR"*, an ANR-family scorecard (e.g. "FAI ANR 2022"). Set **ANR route to SP penalty** / **ANR route from FP penalty** if you're using the auxiliary transit paths.

**Contestant declaration:** none — SP/FP times are calculated centrally from each contestant's declared groundspeed in their registration, not entered per-task.

**Scoring:** per the catalogue, the competitor **starts with 2,000 points**. Corridor excursions: 0–5 seconds outside the corridor is free, additional time costs 3 points/full second. SP/FP timing: ±1 second is free, additional error costs 3 points/full second up to a 200-point cap; not crossing the SP or FP gate at all costs 200 points (each). Time gate width at SP/FP is 0.6 NM (0.3 NM either side).

### 2.B2 — Limited Fuel Turnpoint Hunt

**Tests:** the same turnpoint-hunt mechanics as 2.A6, but under a fuel limit, and every gate crossing scores (it's not a strict precision task).

**Build the route:** identical shape to 2.A6 — no backbone.
1. Place exactly **three** standalone timed turnpoints (CP1/CP2/CP3).
2. Place any number of untimed catalogue turnpoints.
3. Optionally add photo markers as identification targets.

**Create the task:** pick *"2.B2 Limited fuel turnpoint hunt"*, a Precision-family scorecard. Configure **Fuel deadline penalty** and the Duration-group fields as needed.

**Contestant declaration:** required — predicted times for the three compulsory gates, **and** a **Declared fuel endurance (minutes)** field specific to this task.

**Scoring:** typically 100 points per photo, 200 points per time gate — again route-dependent, no fixed sequence bonus (unlike 2.A6, since order is free here). Penalties: breach of quarantine −100%; photo wrongly identified −50% of that photo's score; timing gate error beyond 10 seconds, −10 points/second; time over maximum task duration, −10 points/second.

### 2.B3 — Duration

**Tests:** flying for as long as possible on a limited amount of fuel, landing in a specified area.

**Build the route:** no route backbone required.
1. Take-off gate — optional. If placed, it marks exactly when the measured duration starts; if omitted, take-off is instead inferred from a sustained near-zero-speed hold followed by a rise in tracked speed (less precise).
2. Landing gate — optional, same trade-off in reverse for the end of the duration.
3. Draw the **duration landing area** polygon — the allowed touchdown area.

**Create the task:** pick *"2.B3 Duration"*, a Precision-family scorecard. Configure the Duration group: **Maximum task duration (min)**, **Maximum task duration penalty**, **Fuel deadline penalty**, **Duration normalization policy**, **Duration residual fuel required**.

**Contestant declaration:** none.

**Scoring:** per the catalogue this task is judged mostly outside the platform (judges verify quarantine/prohibited-area breaches and landing-area compliance) — penalties: breach of quarantine −100%; flight in a prohibited area −100%; landing outside the specified area but within the airfield boundary is briefed per-event.

---

## 7. Testing before you go live

There's no separate sandbox mode — you test a task by running a real track through it. Register a contestant on the task (a placeholder one, if you don't want to touch a real entrant), then open their action menu on the task detail page and choose **Upload GPX**. This feeds a GPX file through that contestant's calculator exactly as if they'd flown it, so you can see how the task actually scores before inviting real contestants — but note it first **resets that contestant's existing track and score**, so don't run it against a contestant whose live data you want to keep. This works the same way for legacy and CIMA tasks.
