---
layout: ../../layouts/DocsLayout.astro
title: "CIMA Task Guide: Routes, Declarations and Scoring"
---

# CIMA Task Guide: Routes, Declarations and Scoring

This guide is for contest organisers who run the microlight tasks of the FAI task catalogue (Sporting Code Section 10, Annex 4, tasks **2.A1** to **2.B3**). It also has a section for the pilots who fly them ([section 4](#4-for-pilots)) and one for the Air Sports Race scorecard of Annex 9 ([section 6](#6-air-sports-race-annex-9)).

> **New to ASLT?** Read [How ASLT Works](/docs/00_How_ASLT_Works) and [Route Creation and Task Configuration](/docs/04_Route_Creation_and_Tasks) first. This guide only covers what is special about the CIMA tasks. The older task types (Precision, ANR, Air Sports Challenge, Poker Run, Landing) are in [Competition Types and Scorecards](/docs/07_Competition_Types_and_Scorecards).

**In short**

1. [What is different](#1-what-is-different-about-cima-tasks): scores are scaled against the best pilot, and can change until everybody has flown.
2. [From route to results](#2-from-route-to-results-step-by-step): route, task, scorecard, contestants, declarations, flight orders, flying, penalties, results.
3. [One section per task](#3-the-tasks-one-by-one): what the pilot does, what the route needs, how it is scored, with an example.
4. [For pilots](#4-for-pilots): booking, the declaration, the flight order.
5. [Known limits](#5-known-limits): what the system does not do.
6. [Air Sports Race and Air Sport Challenge](#6-air-sports-race-annex-9): the Annex 9 scorecard.

---

## 1. What is different about CIMA tasks

Older task types add up penalty points. The lowest total wins. CIMA tasks work the other way round, as the catalogue says. A pilot earns points, and the highest score wins.

| | What it means |
|---|---|
| **Raw points (Q)** | What a pilot's flight is worth before scaling. A hidden gate crossed correctly keeps its points, and a timing error takes points off. The live map's score log shows raw points, for example "-12 raw" or "+100 raw". |
| **Task score (P)** | The score the pilot gets. By default it is worked out against the best pilot in the task: **P = task value × Q / Qmax**. The task value is 1000 unless you change it (500 to 1500 is allowed). **Qmax** is the raw points of the best pilot in the task. The best pilot gets the full task value. |
| **Percentage penalties** | Taken off after the task score is worked out. Backtracking costs 50% of the task score in 2.A1 to 2.A5. A quarantine breach costs 100%. Percentages add up, to at most 100%. The result is rounded to a whole number (0.5 rounds up) and is never below zero. |
| **Provisional scores** | The task score depends on the best pilot, so it **can go down after a pilot has landed**. A later pilot who flies better raises Qmax, and everybody else's score drops. Scores are final when every flight in the task is finished. A pilot who never flew stops holding the scores open when their "finished by" time has passed. While a pilot is still flying, their own score is only a preview (never above the task value) and does not set the best score of the task until they have landed. Until then the live map and the results show a **Provisional** badge. |
| **Pilots who did not fly** | They score 0, are shown as **DNF** and do not count in Qmax. |

**The alternative: scaled against a perfect flight.** For 2.A1 to 2.A6 and 2.B2 you can choose that each pilot is compared with the raw points of a perfect flight over *their own* route and declaration. A pilot's score is then fixed when the pilot lands, and does not depend on the other pilots. The price is that nobody reaches the full task value without a perfect flight. You choose this when you create the task ("How is the best score determined?") or later in the scorecard ("Scaled to"). It has limits:

- In **2.A3** the points for the declared turn points (V) stay shared against the best pilot. In **2.A4** the speed term (S) does too. Those scores stay provisional until all flights are finished.
- **2.B3** (duration) can only be scaled against the best pilot. A flight's duration has no "perfect flight".
- **2.A7** (circle) and **2.A8** (ANR) have a fixed scale. They never depend on other pilots.

All pilots of a task are compared with each other. There are no classes inside a task.

---

## 2. From route to results, step by step

### Build the route

Open the route editor and click **Task Wizard** in the toolbar. The **Task Route Guide** panel lists the task types. Pick yours, and the panel becomes a checklist of what the route needs. A step turns green when the route has enough of it. When you create a task later, only the task types your route can be used for are offered.

What each task needs of its route:

| Task | The route needs |
|---|---|
| 2.A1 Curve navigation | A route path from SP to FP with at least one **curved leg**. Hidden gates are optional. |
| 2.A2 Precision navigation | A route path with at least three route waypoints: **SP first, FP last**, visible turn points between. At least one **hidden gate**. |
| 2.A3 Contract navigation | Exactly three route waypoints, in this order: **SP, MP, FP**. At least one free **catalogue turnpoint** besides them. |
| 2.A4 Known circuit | A route path with its waypoints. Hidden gates and observation photos are optional. |
| 2.A5 Unknown legs | A route path with at least three route waypoints (SP first, FP last). At least one **unknown-leg point**, and at least one **extension waypoint** after each one. |
| 2.A6 Turnpoint hunt | **No route path.** Exactly three standalone **timed turnpoints**. At least one **catalogue turnpoint** as a target. |
| 2.A7 Circle | Exactly one each of **circle start (SP), circle centre (CM), circle entry (X)** and **circle exit (WP)**. |
| 2.A8 ANR | A route path with its waypoints. |
| 2.B2 Limited fuel hunt | The same as 2.A6. |
| 2.B3 Duration | A **duration landing area** polygon. Take-off and landing gates are optional. |

Details for each task are in [section 3](#3-the-tasks-one-by-one).

### Create the task and choose the scorecard

Open your contest and choose **Add a navigation task**. The steps are **Task type**, **Route**, sometimes **Parameters**, and **Details**.

- **Task type.** CIMA tasks are listed by their catalogue number, for example "2.A3 Contract navigation with time controls". If you started from a route, only the types that route supports are offered. If you see no CIMA task types, your contest does not have access to the CIMA task package yet. Ask whoever administers your access.
- **Parameters.** 2.A8 asks for **Rounded corners** and **Corridor width (NM)**.
- **Details.** Name, start and finish time, wind, and the **Scorecard**. A CIMA task type offers only its own scorecard: **CIMA Precision 2026** for 2.A1 to 2.A7 and 2.B2, **CIMA ANR 2026** for 2.A8 and **CIMA Duration 2026** for 2.B3. The task gets a **private copy** of the scorecard, so changing it never touches other tasks.
- **How this task is scored.** A box under the scorecard explains in words how the task is scored, with the numbers of the scorecard. For the tasks that can be scaled against a perfect flight it asks **"How is the best score determined?"**. The rules' default, *Scaled against the best pilot*, is preselected.
- **Allow self-management** lets pilots who are registered for the contest book their own start time. The task must also be public and featured. See [section 4](#4-for-pilots).
- **Allow observation registration in the app** matters for 2.A4 and 2.A5. See those tasks.

The same explanation, "How this task is scored", is on the task's page, at the top of the scorecard editor and, in short form, behind the **Provisional** badge that pilots see.

### Tuning the scorecard for your CIMA task

On the task's page, open the **Scorecard**. This is the private copy. Press **Save changes** to keep your changes. The scores of the task are then worked out again. The groups are:

| Group | Fields (as labelled) | Used by |
|---|---|---|
| General | Score sorting direction, Initial score, Scoring model, Scaled to, Task value | all |
| Backtracking | Backtracking penalty, Backtracking bearing difference, Backtracking grace time, Backtracking maximum penalty, Backtracking penalty (% of the task score) | tasks with backtracking |
| Zones | Prohibited zone and Penalty zone penalties and grace times | all |
| Corridor | Corridor grace time, Corridor outside penalty, Corridor maximum penalty | 2.A8 |
| ANR route | ANR route to SP penalty, ANR route from FP penalty | 2.A8 |
| Duration | Compulsory timing tolerance, Compulsory timing penalty per second beyond the tolerance, Time gate value, Maximum task duration, Maximum task duration penalty per second over, Fuel deadline penalty, Landing outside the area penalty, Turnpoint hunt sequence bonus | 2.A6, 2.B2, 2.B3 |
| Circle | Circle radius min, Circle radius max, Circle altitude band, Circle altitude penalty, Circle centre outside penalty | 2.A7 |
| Speed keeping | Speed term value (Vs), Penalise deviation from the declared speed, tolerance and penalty per kt | 2.A4 |
| Hidden gates | Points per hidden gate (2.A4, 2.A5) | 2.A4, 2.A5 |
| Observation photos | Points per observation (CIMA), tolerances | 2.A4, 2.A5 |

Below the groups are the **gate settings** for each gate type: *Turning Point*, *Starting Point*, *Finish Point*, *Secret Point* (the hidden gates), *Takeoff Gate* and *Landing Gate*. Each has **Penalty per second**, **Maximum penalty**, **Missed penalty** and **Grace period before/after**. In the catalogue's words, **Emax**, the largest timing error that counts at one gate (typically 180), is the *Maximum penalty* of the gate type.

Things to know:

- **Scoring model.** Leave it on *Task type default*. Choosing *Penalty points* turns a CIMA task into an old-style task where penalties add up.
- **Scaled to.** The editor lists all three ways. Use only the ones the task's own explanation offers. Choosing *An absolute scale* for a task other than 2.A7 and 2.A8 makes the task score equal the raw points, which is almost never what you want.
- **Task value.** Between 500 and 1500. The editor refuses other values.
- **Initial score** and **Score sorting direction** do not decide the score of a CIMA task. A CIMA task always ranks the highest task score first.
- If you make a mistake, use **Reset to standard**, for a single field or for the whole scorecard.

### Add contestants

Either you add them, or the pilots book themselves.

- **You add them.** From the task's **Manage** menu, use quick add, **Add contestant (advanced)**, or the scheduling tools.
- **Pilots book themselves.** Tick **Allow self-management** on the task. The pilot then uses **Book start time**. See [section 4](#4-for-pilots).

A contestant's planned times follow from the **airspeed** and **wind** of the contestant and from **Minutes to starting point** of the task.

With **adaptive start** the pilot does not have to hit an exact time. The start becomes the nearest whole minute at which the pilot crosses the starting line, anywhere between one hour before and one hour after the planned start. All gate times are counted from that minute.

### Declarations

Some tasks need the crew to declare something before take-off.

| Task | Declaration |
|---|---|
| 2.A1 | **Required.** Expected times at the visible turn points and at FP. |
| 2.A2 | **Required.** Expected times at every visible turn point and at FP. |
| 2.A3 | **Required.** The turn points to fly, before and after MP, and the period **T**. |
| 2.A4 | **Optional.** Times for single turn points, which replace the calculated time. |
| 2.A6 | **Required.** Times for the three compulsory points, and the sequence. |
| 2.B2 | **Optional.** Times for the three compulsory points, the sequence and the fuel endurance. |
| 2.A5, 2.A7, 2.A8, 2.B3 | None. |

**Who enters it, and until when.**

- **You** can always enter and change it. Open the task, and in the contestant's menu choose **Edit declaration**. It is there for 2.A1, 2.A2, 2.A3, 2.A4, 2.A6 and 2.B2. You enter clock times, and a **Declaration preview** shows what will be used.
- **The pilot** can read and change their own declaration on their own page, which is made for a phone, **until take-off**. With adaptive start the limit is the take-off time or the tracker start time, whichever is earlier. The limit also ends when the live calculator has started. After that the pilot can only read the declaration, and a change has to go through you.

**Times relative to the start.** The pilot's page asks for each time as **minutes and seconds after the pilot crosses the start point**. For a hunt, the start is the planned time over the starting point (take-off plus *Minutes to starting point*). A time given this way moves with the flight. If you move the flight, or the pilot flies with adaptive start, the declared times follow the real start. A time you enter as a clock time stays where it is. A contestant with a saved declaration is skipped when you run the start-time scheduler again, so their planned times do not change under them.

**Checks.** A declaration is saved even if it is not finished, and the page lists what is missing. In the contestant list a missing declaration is marked.

### Flight orders

The flight order is the briefing with the map. For a task with a declaration it shows the **declared route**, so make the declarations first.

- Flights **you** added: generate the flight orders from **Manage → Generate flight orders**, or for one contestant from the contestant's menu.
- Flights a **pilot booked**: the system makes the flight order and e-mails it to the pilot. If the declaration is required, this happens when the declaration is complete, and again each time the pilot changes it. The old flight order is removed when the declaration changes. The pilot sees the status and a download button on the declaration page and under *My Upcoming Flights*.
- Flight orders are deleted five days after the flight.

### Flying and the live map

The live map shows each pilot's **task score** under the heading "Score (of 1000)", with a **Provisional** badge while the scores can still change. Pilots who have not started show **DNF**. Select a pilot to see the **score log**. It lists every event with its raw points ("-12 raw", "+180 raw") or its percentage ("-50% of task score"), and shows the arithmetic step by step. In 2.A3 and 2.A4 two kinds of entry are measures, not points. The declared points appear as "V +1" or "V -1", and the speed as "S = 62.4 kt".

**Try it before the event.** Add a placeholder contestant, open the contestant's menu and choose **Upload GPX**. The track is run through the calculators as if it had been flown. It **resets that contestant's existing track and score**.

### Penalties you apply by hand

The system detects most mistakes itself, but not all. Open the contestant's menu, choose **View / remove penalties**, and use **Apply penalty**. Choose a category (Quarantine, Fuel check, Task instructions, Observation evidence, Map placement). Then choose one of:

- **A percentage of the task score**, for example 100 for a quarantine breach.
- **Raw points off the quality score.**

The window shows what the penalty will do to the score. You can take an entry away again with **Remove**.

### Results

The task's results list the task scores, highest first, with the Provisional badge while flights are still open. The contest results add up the teams' task scores. Pilots find their own results under *My Past Flights*. The [Results Service Guide](/docs/05_Results_Service_Guide) covers results tables.

---

## 3. The tasks, one by one

In every example, the pilot is compared with a best pilot who flew perfectly in the same task, unless the text says otherwise. The examples are cases that the automatic scoring tests check, except where the text says "worked by hand".

**Symbols.** Q is the raw points. P is the task score. Emax is the largest timing error that counts at one gate (180 by default). Qmax is the raw points of the best pilot in the task.

### 2.A1 Curve navigation with time estimation

**What the pilot does.** Before take-off the pilot declares the time at which they expect to cross each visible turn point, counted from the start point. The pilot then flies the drawn course, with its curves, as precisely as possible. Hidden gates along the way check that the course was flown in order and in the right direction.

**What the route needs.** A route path with at least one curved leg. To make a curved leg, hold the curve modifier while placing a point, or select a point and change its leg to curved. Hidden gates are optional. Click a leg of the finished route to insert one.

**What is declared (required).** A time for each visible turn point (points on a curved part are not asked for) and for FP. At least one time must be given. A turn point without a declared time is scored against the time calculated from the planned airspeed. If a longest allowed time (Tmax) is set for the task, the declared FP time may not be later than that long after SP. FP itself is not scored as a time gate.

**Setting Tmax.** Open the task's management menu and choose **Update**. For 2.A1 there is a field **Longest time from SP to FP (Tmax)**, in minutes and seconds. Leave both empty for no limit. A pilot who gives a later FP time is told to give an earlier one. Pilots who declared before you changed Tmax are checked again when they save their declaration.

**How it is scored.**

| Part | Rule | Default |
|---|---|---|
| Hidden gates | The hidden gates share **1000 points** equally. A gate crossed once, in order and in the right direction earns 1000 / Nh, where Nh is the number of hidden gates. This is **Qh = 1000 × H / Nh**, with H the number of gates that count. | 1000 |
| Time gates | Each visible turn point is worth Emax and loses 1 point per second of error, at most Emax. A time gate that is not flown loses all of Emax. **Qt = Emax × Nt − Et**, with Nt the number of time gates and Et the sum of the errors. | 180, 1 per second |
| SP and FP | Not time gates. The start point starts the clock. | |
| Hidden gate crossed twice, in either direction, or first crossed against the route | Counts as not crossed. | |
| Time of a gate crossed more than once | Taken from its first crossing. | |
| Backtracking | 50% of the task score for each backtrack. | 50% |

Raw points are **Q = Qh + Qt**. The task score is **P = 1000 × Q / Qmax**.

**What you can change.** Emax, points per second and missed penalty (gate settings of *Turning Point* and *Secret Point*), Tmax (in the task details), the backtracking percentage and grace time, *Scaled to* and *Task value*.

**Example.** The route has 4 hidden gates and 2 time gates, so a perfect flight is 1000 + 2 × 180 = **1360** raw points.

| What happened | Raw points | Task score |
|---|---|---|
| Perfect flight | 1360 | 1000 |
| TP1 crossed 8 s late | 1352 | 994 |
| One hidden gate missed (750 + 360) | 1110 | 816 |
| One hidden gate crossed twice | 1110 | 816 |

The scoring tests check these numbers (`test_simulated_cima_curve_precision_flights.py`). The catalogue's sequence 1-2-4-3-5-6-5-7 over seven hidden gates counts as 1-2-4-6-7: gate 3 was crossed after gate 4 and gate 5 twice, so five gates count (`test_simulated_cima_backtracking_flights.py`).

### 2.A2 Precision navigation

**What the pilot does.** The pilot declares an expected arrival time at every visible turn point and at FP, then flies each leg at a constant speed. The organisation works out the times of the hidden gates itself, by interpolating between the declared times. The pilot does not predict them.

**What the route needs.** A route path with at least three route waypoints: SP first, FP last, visible turn points between. At least one hidden gate, because the task is scored on them. Without one every pilot would score zero, so such a route is not offered for this task.

**What is declared (required).** A time for every visible turn point and for FP. Times given for SP or for hidden gates are ignored.

**How it is scored.**

| Part | Rule | Default |
|---|---|---|
| Hidden gates | Each gate crossed once, in the right direction, earns Emax. **Qp = Emax × Ng**, with Ng the number of gates that count. | 180 |
| Time gates | The visible turn points, the hidden gates and FP are time gates. Every second of error takes 1 point off, at most Emax per gate. A gate not flown takes Emax off. **Qt = −Σ Ei**, with Ei the error at gate i. | 1 per second, at most 180 |
| A missed hidden gate | Loses its 180 *and* 180 for its time: 360 in all. | |
| SP | Not a time gate. It starts the clock. | |
| Hidden gate crossed twice or first against the route | Counts as not crossed. | |
| Backtracking | 50% of the task score for each backtrack. | 50% |

**What you can change.** As for 2.A1.

**Example.** Four hidden gates give a perfect flight of 4 × 180 = **720** raw points.

| What happened | Raw points | Task score |
|---|---|---|
| Perfect flight | 720 | 1000 |
| TP1 crossed 8 s late | 712 | 989 |
| FP crossed 200 s late (counts as 180) | 540 | 750 |
| One hidden gate missed (−180 −180) | 360 | 500 |

(`test_simulated_cima_curve_precision_flights.py`.)

### 2.A3 Contract navigation with time controls

**What the pilot does.** The pilot chooses their own route through a catalogue of turn points. SP, MP (the middle point) and FP are mandatory. The pilot declares the turn points to fly before MP and between MP and FP, and a period **T**. SP is crossed at time zero, MP exactly T after SP, and FP exactly 2T after SP. A point declared after MP that is flown before MP's time is invalid.

**What the route needs.** Exactly three route waypoints, named and ordered SP, MP, FP. At least one free catalogue turnpoint. Photo markers are optional, but they are not scored in this task. The general map shows SP, MP and FP as circles without lines. A pilot's own route is drawn when the pilot is selected.

**What is declared (required).** The sequence, with MP exactly once and FP last, using only catalogue points. And T, which must be longer than zero. On the pilot's page these are *Your turn points, in order* and *Your period T*. On your page they are two lanes, *Before MP* and *After MP*, and the declared T.

**How it is scored.**

| Part | Rule | Default |
|---|---|---|
| Declared points | **V = N − Ep.** N is the number of declared turn points (not SP, MP and FP) flown in order. Ep is the number of declared points not flown or not in order, SP, MP and FP included, and points declared after MP that were flown before MP's time. A turn point counts once. | |
| Points share | **Qp = 1000 × V / Vmax**, with Vmax the best V in the task. This is **always shared against the best pilot**. | 1000 |
| Time gates | SP, MP and FP are each worth Emax and lose 1 point per second of error, at most Emax. One that is not flown loses all of Emax. **Qt = Emax × 3 − Et.** | 180, 1 per second |
| Backtracking | 50% of the task score for each backtrack. | 50% |

Declaring more points can earn more. Each declared point that you then fail to fly takes one off V.

**What you can change.** Emax and points per second (gate settings of *Starting Point*, *Turning Point* and *Finish Point*), the backtracking percentage and *Task value*.

**Example.** Four points are declared (A and B before MP, C and D after), with T = 240 s. A perfect flight has V = 4 and Q = 1000 + 3 × 180 = **1540**.

| What happened | Raw points | Task score |
|---|---|---|
| Perfect flight | 1540 | 1000 |
| MP crossed 8 s late | 1532 | 995 |
| Point C declared and not flown (V = 3 − 1 = 2, so 500 + 540) | 1040 | 675 |
| A second pilot declares nothing but MP and FP and flies them perfectly (V = 0) | 540 | 351 |

(`test_simulated_cima_contract_flights.py`.)

### 2.A4 Navigation over a known circuit

**What the pilot does.** The pilot flies a circuit that is known beforehand. The pilot may declare a time for single turn points. It replaces the time calculated from the flight's airspeed and wind. If you allow it, the pilot marks observation photos in the app while flying. An optional speed term rewards the fastest pilot.

**What the route needs.** A route path with its waypoints. Hidden gates and observation photos are optional. Most tasks use at least one of them as evidence.

**What is declared (optional).** A time for any turn point or FP. Points left empty use the calculated time.

**How it is scored.**

| Part | Rule | Default |
|---|---|---|
| Hidden gates | A gate crossed correctly keeps its value, **Vh**. A gate missed, crossed twice or first crossed against the route loses it. The value is its own setting, *Points per hidden gate*. It is not the gate setting of the *Secret Point*, which is 180 for 2.A1 and 2.A2. | 100 each |
| Time gates | Worth up to Emax each. Every second of error takes 1 point off, at most Emax. A gate not flown loses Emax. | 180, 1 per second |
| Observation photos | Each photo marked at the right place earns its value, half if it is marked a little off. This only counts when **Allow observation registration in the app** is ticked on the task. | 100 each. Full within 2 mm and half within 5 mm on the map |
| Speed term | **Qv = Vs × S / Smax.** S is the ground speed in knots between the first and the last time gate the pilot crossed. Smax is the best S in the task. Vs is set in the scorecard. | Vs = 0, so not used |
| Speed keeping | A penalty per knot for a leg flown faster or slower than declared. It is not in the catalogue. | Off |
| Backtracking | 50% of the task score for each backtrack. | 50% |

The speed term is **always shared against the best pilot** in the task.

**What you can change.** *Points per hidden gate* (Vh), the time gate values (gate settings), *Speed term value (Vs)*, the photo value and tolerances, the speed-keeping rule and the backtracking percentage.

**Example.** SP, TP1, TP2 and FP are time gates worth 180 each, and there are 4 hidden gates worth 100 each. A perfect flight is 4 × 100 + 4 × 180 = **1120** raw points.

| What happened | Raw points | Task score |
|---|---|---|
| Perfect flight | 1120 | 1000 |
| TP2 crossed 36 s early | 1084 | 968 |
| One hidden gate missed | 1020 | 911 |

(`test_simulated_cima_circuit_flights.py`.) With Vs = 100, a pilot who flies at 90% of the best pilot's ground speed gets 90 points for the speed term (worked by hand).

### 2.A5 Navigation with unknown legs

**What the pilot does.** The pilot does not see the whole route. Each unknown-leg point is shown as a photo with a course to turn onto, and the leg that follows is not known beforehand. The pilot flies the true route.

**What the route needs.** Build the true route first, with SP first, FP last and at least one waypoint between. Click a route waypoint to make it an **unknown-leg point**. The guide then goes straight to placing its **extension waypoints**. Each unknown-leg point needs at least one extension waypoint after it. Hidden gates on the true route and observation photos are optional.

**What is declared.** Nothing. Every pilot flies the same task.

**How it is scored.** As 2.A4, without declared times and without the speed term: hidden gates, time gates and observation photos as in the table of 2.A4, and 50% for each backtrack. Backtracking is only judged on the true route. The extension waypoints do not count as active legs.

**What you can change.** As for 2.A4.

**Example.** The numbers of 2.A4 apply (perfect 1120, one hidden gate missed 911). The same tests cover both tasks.

### 2.A6 Turnpoint hunt

**What the pilot does.** The pilot collects as many targets as possible. Three compulsory points have a declared crossing time. The pilot also declares the order in which the points will be flown.

**What the route needs.** No route path. Exactly three standalone timed turnpoints (CP1, CP2, CP3). At least one catalogue turnpoint as a target. Give each target its **Score Value** in the point editor. A target without a value earns nothing. Observation photos are optional, but they are not scored.

**What is declared (required).** A time for each of the three compulsory points, and the sequence of the points. The compulsory points must be in the order of the times given.

**How it is scored.**

| Part | Rule | Default |
|---|---|---|
| Targets | Each target crossed earns its Score Value. | as set for each target |
| Compulsory time gates | A time gate crossed earns its value. An error up to the tolerance costs nothing. Every second beyond it costs points. | 200, 10 s tolerance, 10 per second |
| Sequence bonus | Added when the points were flown in exactly the declared sequence. | 0 |
| Maximum task duration | Every second the last gate is crossed after the maximum duration, counted from take-off, costs points. | none set, 10 per second |
| A gate not flown | Earns and costs nothing. | |
| Backtracking | Not penalised. | |

A late gate can cost more than its value, because the points per second are not capped. The end of the task is the last gate crossed.

**What you can change.** *Time gate value*, *Compulsory timing tolerance*, *Compulsory timing penalty per second beyond the tolerance*, *Turnpoint hunt sequence bonus*, *Maximum task duration* and its penalty, the target values and *Scaled to*.

**Example.** Targets A and B are worth 100 each and the sequence bonus is set to 250. A perfect flight is 100 + 100 + 3 × 200 + 250 = **1050** raw points.

| What happened | Raw points | Task score |
|---|---|---|
| Perfect flight | 1050 | 1000 |
| CP2 crossed 8 s late (inside the tolerance) | 1050 | 1000 |
| CP2 crossed 25 s late (15 s beyond the tolerance, × 10) | 900 | 857 |
| Target B not flown (loses its 100 and the bonus) | 700 | 667 |

(`test_simulated_cima_hunt_flights.py`.)

### 2.A7 Circle

**What the pilot does.** The pilot flies in a straight line over SP and CM (the centre marker) and banks **left**. The first 180 degrees are not scored. Scoring starts when the pilot crosses the entry line X, and ends when X is crossed again after 360 degrees. The pilot then leaves towards WP.

**What the route needs.** Exactly one each of *Circle start (SP)*, *Circle centre (CM)*, *Circle entry (X)* and *Circle exit (WP)*, placed on the map.

**What is declared.** Nothing.

**How it is scored.** The score is **P = (Rmin / Rmax − 0.5) × 500**. Rmin and Rmax are the smallest and the largest distance from CM over the scored 360 degrees. A perfect circle (Rmin = Rmax) scores the maximum, **250**. This is a fixed scale. It never depends on other pilots, and the task value is not used.

| Rule | Cost | Default |
|---|---|---|
| The circle is flown clockwise | The whole score | |
| SP and CM are not overflown in a straight line (within 20 degrees of the SP–CM line, and within 75 m of CM) | The whole score | |
| The radius goes outside the limits during the scored circle | The whole score | 200 to 750 m |
| Rmin / Rmax is 0.5 or lower | The whole score | |
| The scored circle is not completed | The whole score | |
| CM is outside the circle the pilot flew | 100% of the score | 100% |
| The highest and the lowest point of the scored circle are more than the altitude band apart | 20% of the score | 200 ft |

**CM outside the circle.** If the pilot flies a whole circle but CM is not inside it, the system gives the percentage penalty and says so in the score log. It tells this from the angle around CM. A circle around CM takes that angle past a half turn. A circle beside CM does not. A pilot who does not fly a whole circle at all gets "scored arc not completed" instead.

**What you can change.** *Circle radius min*, *Circle radius max*, *Circle altitude band*, *Circle altitude penalty* and *Circle centre outside penalty* (set it to 0 and the flight is then judged as an incomplete circle).

**Example.**

| What happened | Task score |
|---|---|
| Constant radius of 500 m | 250 |
| Radius between 450 m and 550 m (ratio 0.818) | 159 |
| Constant radius, altitude band exceeded (250 less 20%) | 200 |
| A circle of 500 m flown beside CM, not around it | 0 |
| Radius reaches 800 m during the circle | 0 |

(`test_simulated_cima_circle_flights.py`.)

### 2.A8 Precision navigation Air Nav Race (ANR)

**What the pilot does.** The pilot flies a corridor and crosses SP and FP at their calculated times. The calculated times come from the airspeed and wind of the booking.

**What the route needs.** A route path with its waypoints, and a corridor width. SP and FP are time gates 0.6 NM wide.

**What is declared.** Nothing.

**How it is scored.** The pilot starts with **2000** raw points and loses points for mistakes. The task score is **P = 1000 × Q / 2000**. This is a fixed scale and does not depend on other pilots.

| Mistake | Cost | Default |
|---|---|---|
| Outside the corridor | per second after the grace time | 3 per second after 5 s |
| Time error at SP or FP | per second after the grace period, at most the maximum | 3 per second after 1 s, at most 200 |
| SP or FP not crossed inside its 0.6 NM gate | the missed penalty | 200 |
| Take-off outside the allowed window (from the given time to 60 s after), if the route has a take-off gate | once | 100 |
| Route to SP or route from FP not followed, if the route has these paths | each | 200 |
| Backtracking or circling | each time | 200, no maximum |

**What you can change.** The corridor fields, the gate settings of *Starting Point*, *Finish Point* and *Takeoff Gate*, *ANR route to SP penalty*, *ANR route from FP penalty* and the backtracking fields.

**Example.**

| What happened | Raw points | Task score |
|---|---|---|
| Perfect flight | 2000 | 1000 |
| SP crossed 5 s late (4 s beyond the grace, × 3) | 1988 | 994 |
| SP crossed 90 s late (capped at 200) | 1800 | 900 |
| One backtrack | 1800 | 900 |
| Two backtracks on two legs | 1600 | 800 |

(`test_simulated_cima_anr_flights.py`.) If two pilots both lose 200 points, both score 900. The best pilot does not become 1000.

### 2.B2 Limited fuel turnpoint hunt

**What the pilot does.** The same hunt as 2.A6, on a limited amount of fuel. Every crossing scores, **in any order and in either direction**.

**What the route needs.** As 2.A6: no route path, three timed turnpoints, at least one catalogue turnpoint and a Score Value on each target.

**What is declared (optional).** Times for the compulsory points, a sequence, and the **fuel endurance** in minutes. A declaration is not needed to fly and score. A compulsory point without a declared time earns its value without a timing penalty.

**How it is scored.** As 2.A6, with these differences:

- There is no sequence bonus, and the order is free.
- Each gate passed **after the declared fuel endurance**, counted from take-off, costs the *Fuel deadline penalty* (100 by default).

**What you can change.** As for 2.A6, and the *Fuel deadline penalty*.

**Example.** With the same targets and no bonus, a perfect flight is 100 + 100 + 3 × 200 = **800** raw points. CP2 crossed 25 s late costs 150. That gives 650 raw points and a task score of **813** (812.5 rounds up). (`test_simulated_cima_hunt_flights.py`.)

### 2.B3 Duration

**What the pilot does.** The pilot flies as long as possible on a limited amount of fuel, and lands in the specified area.

**What the route needs.** A **duration landing area** polygon. A take-off gate and a landing gate are optional. With them, the duration is exact. Without them, take-off is recognised from a sustained stop followed by speed, and landing from a sustained drop to nearly zero speed. That is less precise. A landing gate that is authored ends the flight when it is crossed after take-off.

**What is declared.** Nothing.

**How it is scored.** The raw points are the minutes in the air. **P = 1000 × minutes / the minutes of the longest flight in the task.** The longest flight gets the task value. This task can only be scaled against the best pilot.

| Part | Rule | Default |
|---|---|---|
| Duration | One raw point per minute airborne. | |
| Landing outside the area | A percentage of the task score. The catalogue leaves the amount to the briefing. | 50% |
| Take-off and landing gates | They mark the flight and cost nothing. | |

**What you can change.** *Landing outside the area penalty* and *Task value*.

**Example.** One pilot flies 60 minutes and another 30. They score **1000** and **500**. If the 60-minute pilot lands outside the area, 50% comes off and the score is **500**. (`test_simulated_cima_duration_flights.py`.)

---

## 4. For pilots

You can send this section to the pilots of your contest.

**Booking.** Open the task and choose **Book start time**, on the website or in the app (*Register today*, then *Register a flight*). Check the aircraft registration, the airspeed and the club. Set the **Starting Point Time**, the wind speed and the wind direction. Tick **Adaptive Start** if you want a one-hour window around the start. Then choose **Book start time**. The steps are the same as in [Register for a Navigation Task](/docs/16_Register_for_a_Navigation_Task).

**The declaration.** If your task has a declaration, booking continues to the **declaration page**, which is made for a phone. It says what you are asked for.

- **Times** are given as **minutes and seconds after you cross the start point**. With adaptive start the page shows no clock time, because your times count from when you actually start.
- **2.A3:** tap the turn points you will fly, in order, before and after MP, and enter your period T.
- **Hunts:** tap the targets in order. The compulsory points follow the times you gave. For 2.B2 you can also give your fuel endurance in minutes.
- Choose **Save declaration**. If it is not finished, the page says what is missing. A required declaration must be complete. An optional one can be skipped with **Skip the declaration**.
- **Do this later** leaves the booking in place. **Done** appears when the declaration is complete.

When you book in the app, you return to the app when you finish. On the website you return to the contest page if you booked there, and to the map of the task if you booked from the booking page.

**The cut-off.** You can read and change your declaration **until take-off**. With adaptive start the limit is the earlier of the take-off and the tracker start. After that the page only lets you read it, and you must ask the organiser to change it. You find your flights, with **Make declaration** or **Edit declaration**, under *My Upcoming Flights*. Under *My Past Flights*, open the contest and choose **View declaration** to see what you declared.

**The flight order.** You do not have to wait for an e-mail. A note under the declaration shows the status:

| You see | It means |
|---|---|
| Your flight order is made when your declaration is complete. | The task needs a declaration first. |
| Your flight order is being made. | It updates by itself. |
| **Download flight order** | It is ready. |
| A reason, and "Save your declaration again to try again." | It failed. Saving again tries again. |
| Nothing | The organiser makes the flight order for your flight. |

If you change your declaration, the flight order is made again, so print the newest one.

**What "Provisional" means.** In most CIMA tasks your task score is a share of the best pilot's raw points. Your score can **go down after you land** when a later pilot flies better. The scores are final when every flight in the task is finished (a pilot who never flew does not hold them open after their "finished by" time). A pilot who is still flying shows a preview that does not lower the others. Tap the badge for the explanation. In 2.A7 and 2.A8 your score never depends on other pilots. A pilot who did not fly shows **DNF** and scores 0.

---

## 5. Known limits

These are things the system does not detect or does not do. Each one has been checked against the code.

**Rules that are not implemented**

- **Microlight backtracking clause.** Backtracking is flying more than 90 degrees off the intended direction for more than 5 seconds, inside the corridor of the leg and outside the turn point radius. For microlight tasks the catalogue also counts rejoining the track line at a point before the point where it was left. That part is not detected.
- **Backtracks add up.** Each backtrack in 2.A1 to 2.A5 costs 50%, so two backtracks cost 100%. One long backtrack counts once.
- **The last 10 degrees of the 2.A7 circle are not measured.** Radius and altitude are measured until the pilot is within 10 degrees of the full 360, because the aircraft turns off towards WP there.
- **2.A4 speed section.** The catalogue does not say where the speed is measured. The system measures S from the first to the last time gate the pilot crossed.
- **2.A3: turn points visited once.** A point counts once. Flying over it again gives nothing and costs nothing extra.
- **Time errors are rounded to the nearest second.**
- **Photo identification in the hunts and in 2.A3.** Targets score when the aircraft crosses them. The catalogue's "photo wrongly identified: 50% of its value" is not implemented, and the photos of these tasks are not scored. Photos are scored only in 2.A4 and 2.A5, and only when the app registration is allowed.
- **Only the true route is active in 2.A5.** Backtracking is not judged on the extension waypoints.
- **Two time limits count from take-off**, not from the start point: the maximum task duration and the fuel endurance. The end of a hunt is the last gate crossed.
- **The residual fuel setting of 2.B3** is information only. It is not scored.
- **No "disqualified" mark.** Only DNF is shown. To disqualify a flight, apply a 100% percentage penalty.

**Penalties you apply by hand**

- Quarantine breaches (100%), fuel checks, ignored task instructions and wrongly placed maps.
- **Flight planning room** (2.A8: failing to leave in time, 100 points).
- Prohibited areas in 2.B3 (100%). A prohibited zone drawn in the route only costs points if you set a *Prohibited zone penalty*. It is 0 in the CIMA Precision and CIMA Duration scorecards.
- A penalty for an **excessive delay** crossing SP or FP, which the catalogue allows, is not part of the default scorecards.

**Setup limits**

- **2.A8 route to SP and route from FP.** The checks only run if the route has those paths. The route editor cannot draw them, so by default they are not scored.
- **There is no class in a task.** All contestants of a task are compared with each other.

**Not part of the system**

- **Landing strips.** Landing strip scoring is judged at the field. The system does not score it, and has no table of strips A to E.
- **Departure and arrival route check for Air Sports Race.** There is no check of the route to the start and from the finish. Only 2.A8 checks the route to SP and from FP.

---

## 6. Air Sports Race (Annex 9)

The **Air Sports Race** family uses the scorecard **Air Sports Race 2025 (Annex 9)**. It is preselected when you create a task of this family. The **Air Sport Challenge** family now does the same with the scorecard **Air Sport Challenge 2025 (Annex 9)**. It has exactly the same rules, and the two families score a flight in the same way. It follows table 6.7.5 of Annex 9. It is **not** a CIMA task. Penalties add up, and the **lowest total wins**. There is no task score, no scaling and no provisional state. The older "Air Sports Race" and "Air Sport Challenge 2023" scorecards stay available. Tasks that were made from them keep them, and you can still choose them when you create a new task.

| Mistake | Default |
|---|---|
| Known time gates, SP and FP | 2 points per second after 2 s, at most 200, and 200 if missed |
| Hidden time gates | 1 point per second after 2 s, at most 100, and 100 if missed |
| Take-off. From 3 s before to 60 s after the given time is free | 200 outside it |
| Outside the corridor | 1 point per second after 5 s, no maximum |
| Inside a penalty zone | 1 point per second after 5 s, no maximum |
| Prohibited zone | 100 for each entrance that lasts more than 5 s |
| Backtracking | 100 each time, at most 100 in total |

A crossing of SP in the wrong direction costs nothing on this scorecard.

**What is manual.** Nothing detects these two, so the contest director applies them as penalties (**View / remove penalties**, then **Apply penalty**, with the category *Quarantine* or *Task instructions*):

- Leaving the quarantine late: **100**.
- Not following the departure and arrival instructions at the airfield: **200**.

**Overall result by standings points.** Annex 9, 6.7.7, gives an example where the overall result is made from points for the place in each task (25, 20, 16 and so on) instead of the sum of the task scores. ASLT has this as a contest option: **Overall result: Standings points per task placing**. The points table is only an example in the annex, and your local rules decide whether to use it and what the table is. You can edit the table in the contest settings. See section 8.3 of the Results Service Guide.
