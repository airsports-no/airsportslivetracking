TURNPOINT = "tp"
STARTINGPOINT = "sp"
FINISHPOINT = "fp"
SECRETPOINT = "secret"
ANR_TP = "anrtp"
TAKEOFF_GATE = "to"
LANDING_GATE = "ldg"
DUMMY = "dummy"
UNKNOWN_LEG = "ul"
INTERMEDIARY_STARTINGPOINT = "isp"
INTERMEDIARY_FINISHPOINT = "ifp"
HIDDEN_GATE = "hidden_gate"
KNOWN_TIME_GATE = "known_time_gate"
CATALOGUE_TURNPOINT = "catalogue_turnpoint"
CIRCLE_CENTER = "circle_center"
CIRCLE_START = "circle_start"
CIRCLE_ENTRY = "circle_entry"
CIRCLE_EXIT = "circle_exit"
ROUTE_TO_SP = "route_to_sp"
ROUTE_FROM_FP = "route_from_fp"
GATE_TYPES = (
    (TURNPOINT, "Turning Point"),
    (STARTINGPOINT, "Starting Point"),
    (FINISHPOINT, "Finish Point"),
    (SECRETPOINT, "Secret Point"),
    (ANR_TP, "ANR Turning Point"),
    (TAKEOFF_GATE, "Takeoff Gate"),
    (LANDING_GATE, "Landing Gate"),
    (INTERMEDIARY_STARTINGPOINT, "Intermediary Starting Point"),
    (INTERMEDIARY_FINISHPOINT, "Intermediary Finish Point"),
    (DUMMY, "Dummy"),
    (UNKNOWN_LEG, "Unknown leg"),
    (HIDDEN_GATE, "Hidden gate"),
    (KNOWN_TIME_GATE, "Known time gate"),
    (CATALOGUE_TURNPOINT, "Catalogue turnpoint"),
    (CIRCLE_CENTER, "Circle center"),
    (CIRCLE_START, "Circle start"),
    (CIRCLE_ENTRY, "Circle entry"),
    (CIRCLE_EXIT, "Circle exit"),
)

# Legacy CIMA alias: a "hidden_gate" pointType is a secret point that predates canonicalization
# onto SECRETPOINT. New authoring never writes HIDDEN_GATE; these helpers exist so read paths
# treat both spellings identically.
SECRET_GATE_TYPES = (SECRETPOINT, HIDDEN_GATE)

# Legacy CIMA pointType aliases: predate canonicalization onto the platform's existing gate types
# (secret for hidden_gate, turnpoint for known_time_gate). New authoring never writes these; these
# helpers exist so read paths treat the legacy spelling and the canonical one identically.
_LEGACY_POINT_TYPE_ALIASES = {
    HIDDEN_GATE: SECRETPOINT,
    KNOWN_TIME_GATE: TURNPOINT,
}


def is_secret_gate_type(gate_type: str | None) -> bool:
    """True if gate_type is the canonical secret point type or its legacy hidden_gate alias."""
    return gate_type in SECRET_GATE_TYPES


def normalize_gate_type(gate_type: str | None) -> str | None:
    """Map legacy CIMA pointType aliases (hidden_gate, known_time_gate) onto their canonical
    platform gate types. Passes through every other gate type (including None) unchanged."""
    return _LEGACY_POINT_TYPE_ALIASES.get(gate_type, gate_type)
