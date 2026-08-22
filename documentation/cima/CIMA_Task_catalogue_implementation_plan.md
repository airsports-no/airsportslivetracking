# CIMA Task catalogue implementation draft

This document describes how air sports in its current form can support the tasks defined in the CIMA  task catalogue and outlines features/development necessary to add support if required.

A core feature of the CIMA tasks is that each contestant starts with a maximum score which is decreased whenever a penalty is incurred. This is supported by airsports using the new initial score field in the scorecard and applying negative penalties as verified by Yago et al.

CIMA way points are circles. This requires some changes throughout the platform to support. This possibly includes implementing a separate gatekeeper.

### Approximate development time for circle support: 1w

# 2.A1: Curve navigation with time estimation

This task can mostly be handled by the existing precision flying calculator.  The core difference is that instead of pre-calculating the gate times based on a declared speed, a contestant is free to declare their own speeds for each leg.

## Required development

In order to fully support this task airsports must be extended with a user interface that allows manually specifying the declared speed for each leg of the route.  To be sure that the times are entered the calculator will not start unless all legs have declared speeds. 

We assume that the speeds to be declared are ground speed,these must be corrected for the task wind speed and direction.

The current implementation of the precision calculator  does not consider a gate after it has been passed the first time. This must be extended to also provide a penalty for gate crossings of a gate that has been previously crossed.

### Approximate development time: 2w

# 2.A2: Precision navigation

From the point of view of airSports this is similar to 2.A1 and therefore has the same current support and development requirements.

# 2.A3: Contract navigation with time controls

This is a precision route with three waypoints that have defined crossing times and a set of “free” waypoints. These free  waypoints must be crossed, but it is up to the contestant to define the order. The time at the final gate (FP)  is defined as two times the time at the middle gate relative to the time at the starting point (SP). Waypoints defined to be crossed after the middle point cannot be crossed before the middle point time, and vice versa.

## Required development

Free waypoints are not supported by airsports. Support for these must be added by extending the markers used to indicate photos in the route editor  to also support other kinds of markers, in this case an untimed waypoint.  New configuration gui  must be added  to allow the administrator to define the order for these waypoints to be crossed with respect to the middle gate. This user interface must be easy to use since it must be updated in real time after the pilot briefing.

The existing precision calculator must be extended to incorporate these ordered free waypoints into the existing route so that they can be scored by the existing algorithm and also be displayed by the existing live tracking map.

The precision calculator must be extended with a mechanism to detect crossing the free waypoints.  

### Approximate development time: 2w

# 2.A4: Navigation over a known circuit

This is supported using the existing precision task type

# 2.A5:  Navigation with unknown legs

I believe this is supported using the unknown leg feature in the route editor. This is not entirely intuitive and should maybe be redesigned for better usability. It needs to be verified if the current support is sufficient for this task type. Specific unknown leg roots such as inner and outer circles must be supported in the route editor.

### Approximate development time: 3w

Includes other cosmetic changes to the route editor to make it more intuitive.

# 2.A6: Turnpoint hunt

This task has a possibly large set of free waypoints in addition to three fixed waypoints with crossing times defined by the competitor. The competitor must predict order and selection of turn points that should be visited.

## Required development

From the point of view of airsports this is very similar to 2.A3 with the exception that the sequence of free waypoints need not be specified in relation to the fixed waypoints.  The only additional development required for this task beyond what is required for 2.A3 is a mechanism to relax the requirement when specifying waypoint order. 

### Approximate development time: 3d

# 2.A7 Circle

A starting point and centre point defines a circle that must be flown within a certain radius tolerance and altitude tolerance. This is not supported by airsports.

## Required development

This task can build on the free waypoints required by previous tasks. Some additional waypoint types must be introduced, starting point and circle center.  Support for this should be implemented as a new calculator that can be included as part of the existing precision route gatekeeper. This allows a circle task to be added at the end of all tasks supported by the precision gatekeeper similar to how a danger zone is used.

Circle score should be calculated from the maximum and minimum distance to the circle centre for the part of the circle that is valid (after the initial half orbit).  Any altitude penalties should be applied according to the scoring rules.

### Approximate development time: 2w

# 2.A8: Precision navigation air nav race (ANR)

This is supported by the existing ANR og Air Sports Race/Challenge task types

# 2.B1: Split square

A square is defined by four turning points, with an optional marker in the middle to create a longer leg for the economy leg. The square itself is a basic precision route without timing. The optional marker leg is a free waypoint, but with predefined order. Gives bonus points if passed.

## Required development

This is mostly supported by the existing precision calculator, but some extra development may be required to support the optional marker. Add calculator for the bonus waypoint.

### Approximate development time: 1w

# 2.B2: Limited fuel turnpoint hunt

Identical to 2.A6

# 2.B3: Duration

It is not clear to me how this should be implemented as a task in an interesting way. Maybe as a route with the takeoff gate and a landing gate, and simply measuring the time between the two gate passings.

## Required development

Requires a new gatekeeper that simply keeps track of the duration from the takeoff gate to the landing gate and uses this to order contestants as a function of the number of seconds in between.

### Approximate development time: 1w

# Tentative development plan

1. Add support for circle waypoints. Requires some data structure changes.  
2. Add support for free waypoints in the route editor (proof of concept already drafted)  
   1. Regular free waypoints  
   2. Circle start points  
   3. Circle centre points  
   4. Improve unknown leg support (including inner and outer circle)  
3. Add additional regular waypoint types speed leg start and speed leg stop.  
4. Update gatekeeper route with functionality to detect crossing of the free waypoints  
5. Create an interface for adding additional route information for the contestant. The below items could probably be included into the same interface:  
   1. Add a user interface to manually assign leg speeds both to regular routes and the free waypoints.  
   2. Add a user interface to impose an order on an arbitrary number of free waypoints. This order should possibly be relative to fixed waypoints in the route. [https://tanstack.com/table/v8/docs/framework/react/examples/row-dnd](https://tanstack.com/table/v8/docs/framework/react/examples/row-dnd)  
   3. Add a user interface to assign speed for speed leg.  
   4. Free waypoints with gate time or imposed order should be baked into the route for the contestant every time they are changed.  
6. Add functionality and user interface to display which types of tasks for which a route can be used.  
7. Update the live tracking map to show free waypoints in route.  
8. Update live tracking map to display the contestants specific route whenever a contestant is selected in the map. This should display the imposed order and passing times determined by the declared leg speeds of the free waypoints.  
9. Update flight order/navigation map to display the free waypoints. If any timing or order has been entered through the user interface, it should be possible to include this in the navigation map.  
10. Add a separate calculator to keep track of free waypoints that are not part of the route  (has no timing or order). This is required for waypoint hunts. It should not be required for the other tasks since the selected freeway points will be part of the route  with the specified time or order.  
11. Add a separate calculator to score the circle task.  
12. Add a separate speed calculator to score speed legs.   
13. Create specific scorecards for the various CIMA tasks.

Approximate development is three months for something that should work.

---

# Post-implementation alignment pass (2026-08)

The sections above are the original pre-implementation plan and are now
superseded by the actual implementation. See
`CIMA_task_implementation_requirements.md` at the repo root for the
authoritative, current description of how each task type is meant to work,
and `monetization_business_rules.md` §4 for the CIMA task-type rollout
(beta/paywall) model.

A correctness-first alignment pass against that requirements doc fixed
several spec-violating behaviors (2.A5 secrets-shown view leaking dummy
legs, 2.A3's general map showing the full route instead of just the
backbone, CIMA waypoints not rendering as circles), restructured 2.A6/2.B2
to have no route backbone per spec, added 2.A1 curve enforcement, and added
2.A5 decoy/false-photo support. A follow-up pass then implemented the three
gaps that were deferred from that first pass:

- **2.A4 (Known circuit) per-turnpoint time override + speed-keeping
  score.** `KnownCircuitStrategy` (`contestant_task_compiler.py`) accepts an
  optional `turnpoint_time_overrides` declaration payload - any turnpoint
  left undeclared still follows the uniform declared-speed gate-time chain,
  same as before. `GateCalculator._score_speed_keeping` scores each leg's
  actual groundspeed against the declared `air_speed` (tolerance/penalty via
  new `Scorecard.speed_keeping_tolerance_kt`/`speed_keeping_penalty_per_kt`
  fields), skipping legs bordering an overridden turnpoint since the
  contestant is expected to deviate from the declared speed there by design.
- **2.B3 (Duration) speed-based takeoff/landing inference.** New
  `SpeedInferredTakeoffLandingCalculator` acts as a fallback (checked
  independently per side) when a route has no authored takeoff/landing
  gates: takeoff is edge-detected as the first above-threshold sample after
  a sustained near-zero-speed hold, landing once near-zero speed has been
  sustained for a full window while airborne (mirroring the existing
  proactive-termination heuristic in `contestant_processor.py`). The
  `cima_b3` wizard template's takeoff/landing gate steps are now optional
  (`minCount: 0`). Fixing this also required two small pre-existing-bug
  fixes: `TakeoffAndLandingGateCalculator.on_takeoff_passed`/
  `on_landing_passed` were unconditionally scoring any takeoff/landing event
  they received rather than only ones from their own authored gate (would
  have double-scored synthetic events), and `GateCalculator.create_gates()`
  crashed on a route with zero waypoints (which every Duration route has,
  since its wizard has no route-waypoint step) - both fixed.
- **Access-control granularity.** Task-type gating now has a fine layer
  alongside the coarse `"cima"` group: `get_fine_task_type_group()`
  (`task_type_group_definitions.py`) returns a namespaced `"cima:<subtype>"`
  string per subtype, and enforcement
  (`capacity_enforcement.assert_can_add_navigation_task`) accepts either the
  coarse or the fine group - so existing `AccessGrant`/`TokenType` rows
  (which only ever store `"cima"`) keep granting every subtype unchanged,
  while new grants can optionally scope to one subtype. A new
  `UserEntitlementGrant` model (general-purpose, not CIMA-specific - see its
  docstring in `access_control.py`) provides the dedicated "give this user
  direct access, no club/contest/payment involved" beta mechanism; see
  `monetization_business_rules.md` §4 for the rollout instructions using it.
- **2.A7 (Circle) is a 4-marker structure**, not the 3 markers the
  requirements doc's prose describes (start, centre, "next waypoint after
  leaving"). The implementation splits "next waypoint" into a separate
  entry (X) and exit (WP) marker because `circle_calculator.py` needs an
  explicit entry point to validate the straight SP→CM entry line before the
  orbit begins. This is a considered, functionally-motivated deviation, not
  a bug - left as-is.
- **No JS test runner is configured** in `react_vite/` (no vitest/jest
  devDependency, no `test` script in `package.json`). `taskTemplates.test.ts`
  exists but cannot currently be executed; frontend changes in this pass
  were verified via `tsc --noEmit` and manual code review instead. Setting
  up a real frontend test runner is a separate, general infrastructure task.
- **`NewNavigationTaskWizard`** (the "create task from scratch" Django
  wizard, as opposed to `RouteToTaskWizard`/`editableroute_createnavigationtask`,
  which is the flow actually linked from the route editor UI) never calls
  `assert_can_add_navigation_task` at all - task-type-group enforcement is
  bypassed on that path. Pre-existing, not touched by this pass.