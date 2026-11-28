"""
The vocabulary a task type uses to declare what its route must contain: small frozen requirement objects.

A requirement counts one fact about the route (the number of a kind of feature, or a derived fact such as the number of
curved legs) and says how many there must be. The facts are computed and the requirements evaluated by
display.services.route_compatibility; this module only holds the data, so the task type registry can import it.
"""

from dataclasses import dataclass, field

# Facts: the names a requirement can count. Most are the primitives of extract_route_primitives (one count per authored
# feature); the others are derived from the route.
ROUTE_PATH = "route_path"
ROUTE_WAYPOINT = "route_waypoint"
TAKEOFF_GATE = "takeoff_gate"
LANDING_GATE = "landing_gate"
CATALOGUE_TURNPOINT = "catalogue_turnpoint"
CIRCLE_CENTER_MARKER = "circle_center_marker"
CIRCLE_START_MARKER = "circle_start_marker"
CIRCLE_ENTRY_MARKER = "circle_entry_marker"
CIRCLE_EXIT_MARKER = "circle_exit_marker"
KNOWN_TIME_GATE = "known_time_gate"
HIDDEN_GATE = "hidden_gate"
UNKNOWN_LEG = "unknown_leg"
DUMMY_WAYPOINT = "dummy_waypoint"
CURVED_LEG = "curved_leg"
DURATION_LANDING_AREA = "duration_landing_area"
OBSERVATION_PHOTO = "observation_photo"
# Derived facts.
NAMED_KNOWN_TIME_GATE = "named_known_time_gate"
NAMED_CATALOGUE_TURNPOINT = "named_catalogue_turnpoint"
NAMED_UNKNOWN_LEG = "named_unknown_leg"
# Catalogue turn points other than the backbone's own SP, MP and FP.
FREE_CATALOGUE_TURNPOINT = "free_catalogue_turnpoint"
# Unknown-leg points that have no extension waypoint after them.
UNKNOWN_LEG_WITHOUT_EXTENSION = "unknown_leg_without_extension"
# Timed turn points of the route itself (not SP, FP or hidden gates): the known time gates of a known circuit.
TIMED_TURN_POINT = "timed_turn_point"
# Route waypoints that are not where the ordering requirement expects them (see WaypointOrdering).
ROUTE_WAYPOINT_ORDER_VIOLATIONS = "route_waypoint_order_violations"


# Tools: the route editor tool that satisfies a requirement (RouteRequirement.tool). The route editor's guide starts the
# tool of the requirement the user is working on. A requirement that no tool satisfies, such as the order of the
# waypoints or a forbidden feature, has none.
TOOL_ROUTE_WAYPOINT = "route_waypoint"
TOOL_HIDDEN_GATE = "hidden_gate"
TOOL_KNOWN_TIME_GATE = "known_time_gate"
TOOL_CATALOGUE_TURNPOINT = "catalogue_turnpoint"
TOOL_CIRCLE_START = "circle_start"
TOOL_CIRCLE_CENTER = "circle_center"
TOOL_CIRCLE_ENTRY = "circle_entry"
TOOL_CIRCLE_EXIT = "circle_exit"
TOOL_PHOTO = "photo"
TOOL_LANDING_AREA = "landing_area"
TOOL_TAKEOFF_GATE = "takeoff_gate"
TOOL_LANDING_GATE = "landing_gate"
TOOL_UNKNOWN_LEG_POINT = "unknown_leg_point"
TOOL_EXTENSION_WAYPOINT = "extension_waypoint"
TOOL_CURVED_LEG = "curved_leg"
TOOLS = (
    TOOL_ROUTE_WAYPOINT,
    TOOL_HIDDEN_GATE,
    TOOL_KNOWN_TIME_GATE,
    TOOL_CATALOGUE_TURNPOINT,
    TOOL_CIRCLE_START,
    TOOL_CIRCLE_CENTER,
    TOOL_CIRCLE_ENTRY,
    TOOL_CIRCLE_EXIT,
    TOOL_PHOTO,
    TOOL_LANDING_AREA,
    TOOL_TAKEOFF_GATE,
    TOOL_LANDING_GATE,
    TOOL_UNKNOWN_LEG_POINT,
    TOOL_EXTENSION_WAYPOINT,
    TOOL_CURVED_LEG,
)


@dataclass(frozen=True)
class WaypointSpec:
    """What a route waypoint must be: its point type (pointType) and, when given, its name."""

    point_type: str
    name: str | None = None

    def matches(self, point_type: str | None, name: str | None) -> bool:
        return point_type == self.point_type and (self.name is None or name == self.name)


@dataclass(frozen=True)
class WaypointOrdering:
    """
    How the route waypoints, sorted by their sequence number, must be arranged: `exact` lists every waypoint in order,
    `first` and `last` only constrain the ends of the route.
    """

    exact: tuple[WaypointSpec, ...] = ()
    first: WaypointSpec | None = None
    last: WaypointSpec | None = None

    def violations(self, waypoints: list[tuple[str | None, str | None]]) -> int:
        """
        The number of expected positions that [waypoints] (point type and name, in route order) do not fill. A route
        without waypoints, or with another number than `exact` lists, has no ordering to check: that is a count
        requirement's failure.
        """
        if not waypoints or (self.exact and len(waypoints) != len(self.exact)):
            return 0
        violations = sum(
            1 for spec, (point_type, name) in zip(self.exact, waypoints) if not spec.matches(point_type, name)
        )
        if self.first is not None and not self.first.matches(*waypoints[0]):
            violations += 1
        if self.last is not None and not self.last.matches(*waypoints[-1]):
            violations += 1
        return violations


@dataclass(frozen=True)
class RouteRequirement:
    """
    One thing the route must (not) contain: the number of `fact` must be at least `minimum` and at most `maximum`
    (None: no limit; 0: the feature is forbidden). A requirement with no minimum and no maximum is optional: it is
    always satisfied and only describes a step of the route editor's guide.
    """

    # Unique among the requirements of one task type; what the route editor wizard identifies the requirement by.
    key: str
    # What is counted (one of the fact names above). A tuple counts the sum of several facts: "at least one of".
    fact: str | tuple[str, ...]
    # Short human-readable name of what is counted, for the route editor.
    label: str
    minimum: int = 0
    maximum: int | None = None
    # What is wrong when the requirement is not met. When omitted it is derived from the label and the limits.
    message: str | None = None
    # The ordering the route waypoints must have; the fact is then ROUTE_WAYPOINT_ORDER_VIOLATIONS.
    ordering: WaypointOrdering | None = None
    # The keys of requirements that must be met before this one is checked (an ordering means nothing until the
    # waypoint count is right); until then it counts as met so that the one root cause is reported once.
    depends_on: tuple[str, ...] = field(default=())
    # What the route editor's guide tells the user to do to satisfy the requirement: plain, short, says what to click.
    help: str = ""
    # The tool (one of TOOLS) that satisfies the requirement, None when no tool does. `other_tools` are the further
    # tools that also count, for a requirement that is met by any of several kinds of feature.
    tool: str | None = None
    other_tools: tuple[str, ...] = field(default=())

    @property
    def is_required(self) -> bool:
        return self.minimum > 0

    @property
    def is_optional(self) -> bool:
        """Always satisfied: the requirement only describes an optional step of the guide."""
        return self.minimum == 0 and self.maximum is None

    def is_met_by(self, found: int) -> bool:
        return found >= self.minimum and (self.maximum is None or found <= self.maximum)

    def failure_message(self, found: int) -> str:
        if self.message:
            return self.message
        if self.is_optional:
            return f"{self.label} are optional."
        if self.maximum == 0:
            return f"Route feature not allowed for this task type: {self.key}"
        if found < self.minimum and self.minimum == 1:
            return f"Missing required route feature: {self.key}"
        if self.maximum is not None and found > self.maximum:
            return f"Route has too many {self.label} ({found}, at most {self.maximum})."
        return f"Route needs at least {self.minimum} {self.label} (found {found})."


def present(fact: str, label: str, key: str | None = None, **kwargs) -> RouteRequirement:
    """At least one of [fact]."""
    return RouteRequirement(key or fact, fact, label, minimum=1, **kwargs)


def forbidden(fact: str, label: str, key: str | None = None, **kwargs) -> RouteRequirement:
    """None of [fact]."""
    return RouteRequirement(key or fact, fact, label, maximum=0, **kwargs)


def exactly(fact: str, label: str, count: int, key: str | None = None, **kwargs) -> RouteRequirement:
    """Exactly [count] of [fact]."""
    return RouteRequirement(key or fact, fact, label, minimum=count, maximum=count, **kwargs)


def optional(fact: str, label: str, key: str | None = None, **kwargs) -> RouteRequirement:
    """[fact] may be there but need not be: an optional step of the guide, always satisfied."""
    return RouteRequirement(key or fact, fact, label, **kwargs)


def at_least_one_of(facts: tuple[str, ...], label: str, key: str, **kwargs) -> RouteRequirement:
    """At least one feature of any of [facts]."""
    return RouteRequirement(key, tuple(facts), label, minimum=1, **kwargs)
