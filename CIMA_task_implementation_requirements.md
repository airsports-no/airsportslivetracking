# Task description overview

This document describes how the various tasks from them CIMA Task catalogue are implemented in the air sports live tracking system. Tasks that are not explicitly mentioned have not been and should not be implemented. 

## Fixed versus adaptive start

Several of the tasks below require explicit times defined for certain waypoints. This is fine for regular absolute time contestants, but does not work well with the adaptive start feature in the air sports platform. We must therefore differentiate between these two contestant types. For absolute contestants we use absolute times we're required, but for adaptive contestants we should use relative time from passing the starting point.

## Implementation note: hidden gates are secret points

Wherever a task description below says "hidden gate", implement it as the platform's existing
secret point type (pointType `secret`, featureType `route_waypoint`) — do not introduce a separate
gate/point type for it. An earlier CIMA implementation pass added a parallel `hidden_gate`
pointType by mistake; it has since been collapsed back into `secret` (see
`display.utilities.gate_definitions.normalize_gate_type`/`is_secret_gate_type` and the matching
frontend `gateTypes.ts` helpers). `hidden_gate` still exists purely as a read-only compatibility
alias for routes saved before the collapse — every code path that reads a gate/point type must
accept both spellings, but nothing should ever write `hidden_gate` again. The compiled-payload key
names (`compiled_primitives["hidden_gate"]`, `hidden_gate_names`, `unknown_legs_hidden_gates`) keep
their existing names regardless — they are a frozen persisted contract, not a description of the
underlying point type.

## Tasks

### Task 2.A1

This is a regular precision navigation task that is already supported by the platform and the route editor. Since the task explicitly include curves, the route editor should make sure that the route contains at least one curve.

### Task 2.A2

This is also a regular precision navigation task, but without the explicit curve requirement.

### Task 2.A3

This Is flown as a regular precision task, but route creation and contestant planning differs from the normal precision task flow. The route should consist of a backbone of three waypoints, start point, middle point, and finish point. In addition there is any number of freeway points currently called catalog points in the implementation. These are designed in the route editor. When registering a contestant the organizer sets up the contestant declaration which orders the waypoint between themselves and before and after the middle point. Start point and finish point are always first and last.  in the contestant declaration we also declare the relative times that the middle point and finish point will be crossed, i. e. T seconds.  This is done in a separate contestant declaration page in the navigation task administration section. what's the declaration is in place, it is flown as a regular precision task given the declared route. Scoring, waypoint lists, and route display when the contestant is selected in the live navigation map should reflect the contestant declared task. The same should be the case for the  contestant specific navigation map to be handed to the contestant or in the flight order. The general navigation map for the task should only display these three backbone waypoints start point, middle point, and finish point without any lines between and the freeway points. For the CIMA tasks alway points are represented as circles.

### Task 2.A4

This is also basically a precision flying task.  the contestant can choose to fly a specific groundspeed which is already supported by the platform by setting ground speed as air speed with zero wind. It should also be possible for the contestant to declare specific times at certain turn points, effectively overriding the declared groundspeed for these points.  In addition to scoring regular gate crossings as detailed in the scoring section, the contestant is also scored on their speed.

### Task 2.A5

This is also basically a position task, but the information handed to the contestant is different than normal. The organizer designs a route with a main backbone which is the route to be flown. Certain waypoints will be dedicated as unknown leg waypoints. These are not visible to the contestant, but are represented by a photo with a course printed on them. When the contestant identifies the photo against a landmark where they are, they should turn in the indicated direction on the photo. This should lead them to the next way point on the backbone track. To further confuse the contestant, from each unknown leg the organizer will add several dumbly waypoints to extend portion of the route where the contestant is looking for the photos. So for the contestant they will be presented with several disjoint route segments. They know where to start, and along each route segment they know there will be a photo identifying where to turn. They do not know where along this route segment the photo is. After turning the required course they will be heading towards the first waypoint of the next route segment, which is the first visible waypoint after the unknown leg waypoint. Note that there will probably be hidden gates along the leg from the unknown leg way point to the first waypoint of the next route segment. How this the task is visualized is very different for the different use a facing faces:

#### Route editor

The route editor straws the backbone route which is the precision wrote the contestant should follow. This includes hidden waypoints and curves and photo observation markers. After this, they identify several waypoints as unknown leg waypoints which marks the end of a segment. From each unknown leg waypoint they extend the segment with dummy waypoints to increase the length of the segment that is displayed to the contestant, but not the backbone route itself.

#### Contestant map

The contestant should only see the route segments with dummy legs.  There will be multiple route segments, and each goes from the first visible waypoint (e.g. start point or turn point), passed the unknown leg waypoint, including all dummy leg waypoints extending from the unknown leg waypoint. Secret gates should of course be hidden as usual.  The flight order will contain an extra section including the photos of all of the unknown leg white points with a course printed on them. These photos should be in arbitrary order. it should be possible for the organizer to add extra photos that do not match any features along the route to make it harder for the contestant with false photos. The user interface must be updated to allow the organizer to register these false photos.

#### Live navigation map

There are two modes on the live navigation map, one where secrets are hidden, and one where secrets are displayed.

##### Secrets are hidden

When secrets are hidden the live navigation map should display the same Information as is included in the contestant map.

##### Secrets are displayed

When secrets are displayed the live navigation map should display the same view as the route editor sees.

### Task 2.A6

This is also very similar to a precision flight during execution, but the planning differs from regular precision tasks. The route editor designs a route with three free waypoints that have time checks.  In addition they add several free or catalog waypoints without time checks. There should be no backbone route. In the contestant declaration the organizer orders all waypoints in the order provided by the contestant. The three white points with time checks require an explicit time in the contestant declaration.  This is quite similar to task 2.A3 come I accept that the timing is free for the three way points, and the order is free. In task 2.A3 The order of the start point, middle point, and finish point is given by the backbone route.

### Taks 2.A7

This is completely different from position flying And requires its own calculator. The organizer should provide the start points which is where the task starts come up the centre market of the circle, and the next way point after leaving the task. So this is the backbone of exactly three waypoints. The second point on the route which is the center marker of the circle should be rendered with an inner and outer circle that corresponds to the smallest and largest radius allowed for the circle.

### Task 2.A8

This is the existing ANR task.

### Task 2.B2

This is not a precision task. the route editor creates a route consisting of all three waypoints, were three other waypoints have time checks, and the remaining do not. It is important that the route creation wizard in the route editor enforces this constraint come I also for task 2.A6. during contestant declaration there is no required order for the waypoints,  except for the three timed waypoints that must be provided the crossing time.  This requires a calculater we're all gate crossings provide points, and the three waypoints with time checks are evaluated.

### Task 2.B3

This requires no specific route, I think. It is only a matter of timing the duration from take off to landing. Getting exact timing for this will most likely be up to the judges on the ground, but we can have a calculator where we try to infer this based on sudden speed increases from zero and sudden speed decreases to near zero.