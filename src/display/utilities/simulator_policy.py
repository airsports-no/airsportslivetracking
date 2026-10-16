"""
Real flights versus simulator flights (see documentation/PLAN_simulator_separation.md).

A navigation task has a simulator policy; a contestant has a declared flight mode (what the pilot said they would do when
registering). Together they decide which positions are accepted: a position tracked on a pilot's simulator tracking ID is a
simulator position, anything else is a real one.
"""

SIMULATOR_NOT_ALLOWED = "not_allowed"
SIMULATOR_ALLOWED = "allowed"
SIMULATOR_ONLY = "simulator_only"
SIMULATOR_POLICY_CHOICES = (
    (SIMULATOR_NOT_ALLOWED, "Not allowed: simulator flights are ignored"),
    (SIMULATOR_ALLOWED, "Allowed: simulator flights count, and are marked as simulator flights"),
    (SIMULATOR_ONLY, "Simulator only: real flights (tracker or app) are ignored"),
)

FLIGHT_MODE_REAL = "real"
FLIGHT_MODE_SIMULATOR = "simulator"
FLIGHT_MODE_CHOICES = (
    (FLIGHT_MODE_REAL, "Real aircraft"),
    (FLIGHT_MODE_SIMULATOR, "Flight simulator"),
)

# The X-App-Platform values the clients send (and the `client` marker of an embedded web view) and what they imply.
PLATFORM_FLIGHT_MODES = {"msfs": FLIGHT_MODE_SIMULATOR, "android": FLIGHT_MODE_REAL, "ios": FLIGHT_MODE_REAL}


def policy_allows(policy: str, is_simulator: bool) -> bool:
    """Whether a task with [policy] accepts a flight flown in the simulator (True) or in a real aircraft (False)."""
    if policy == SIMULATOR_NOT_ALLOWED:
        return not is_simulator
    if policy == SIMULATOR_ONLY:
        return is_simulator
    return True


def flight_mode_for_platform(platform) -> str | None:
    """The flight mode implied by the client that makes a request, None for the website and unknown clients."""
    return PLATFORM_FLIGHT_MODES.get((platform or "").lower())


def flight_mode_is_simulator(flight_mode: str) -> bool:
    return flight_mode == FLIGHT_MODE_SIMULATOR
