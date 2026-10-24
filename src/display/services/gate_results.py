import datetime
from typing import Optional

from display.flight_order_and_maps.effective_route_rendering import get_effective_route_waypoints
from display.utilities.gate_definitions import CIRCLE_CENTER, DUMMY, SECRETPOINT, UNKNOWN_LEG

# Route points that are never crossed as gates.
NOT_GATES = {DUMMY, CIRCLE_CENTER, "route_to_sp", "route_from_fp"}
# Gates whose place the contestant is not told about: the map hides them unless the task shows secrets.
HIDDEN_GATES = {SECRETPOINT, UNKNOWN_LEG}


def _as_datetime(value) -> Optional[datetime.datetime]:
    if value is None or isinstance(value, datetime.datetime):
        return value
    return datetime.datetime.fromisoformat(value)


def gate_results_for(contestant) -> list[dict]:
    """
    Each gate of the contestant's route in order with how it went, for the live map's flight list, gates table and
    replay: the planned (required) time, the actual crossing time (ActualGateTime, recorded by the orchestrator), the
    offset at a gate with a time check (seconds, positive is late), whether it was missed, and the points of its
    timing result or of missing it. Secret and unknown-leg gates are included and marked, so the map can keep hiding
    them unless the task shows secrets.
    """
    waypoints = get_effective_route_waypoints(
        contestant.navigation_task, contestant=contestant, include_contestant_declarations=True
    )
    planned = contestant.gate_times
    actual = contestant.gate_times_actual
    entries_by_gate: dict[str, list] = {}
    for entry in contestant.scorelogentry_set.order_by("time"):
        entries_by_gate.setdefault(entry.gate, []).append(entry)

    results = []
    for waypoint in waypoints:
        if waypoint.type in NOT_GATES or getattr(waypoint, "on_curved_segment", False):
            continue
        entries = entries_by_gate.get(waypoint.name, [])
        # The gate's own timing result carries its planned and actual time; a miss is logged as "missing gate", or as
        # "missed ..." where the miss itself scores nothing (a gate missed while outside the corridor).
        timing = next((e for e in entries if e.planned and e.actual), None)
        miss = next((e for e in entries if e.message.startswith(("missing gate", "missed"))), None)
        planned_time = _as_datetime(planned.get(waypoint.name))
        actual_time = actual.get(waypoint.name)
        # The timing result's own times where there is one: with an adaptive start the crossing sets the start minute,
        # so the starting point's result is 0 s whatever the plan said before.
        if not waypoint.time_check:
            offset = None
        elif timing:
            offset = round((timing.actual - timing.planned).total_seconds())
        elif actual_time and planned_time:
            offset = round((actual_time - planned_time).total_seconds())
        else:
            offset = None
        results.append(
            {
                "gate": waypoint.name,
                "type": waypoint.type,
                "time_check": waypoint.time_check,
                "hidden": waypoint.type in HIDDEN_GATES,
                "planned": planned_time.isoformat() if planned_time else None,
                "actual": actual_time.isoformat() if actual_time else None,
                "offset_seconds": offset,
                "missed": actual_time is None and miss is not None,
                "points": timing.points if timing else (miss.points if miss else 0),
            }
        )
    return results
