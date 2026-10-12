"""
The practice flight the MSFS client offers new pilots (SimulatorQuickstart): which one, where to start in the simulator,
and whether the pilot has registered for it already.
"""

import datetime
from typing import Optional

from django.utils import timezone

from display.models import Contestant, Person, SimulatorQuickstart
from display.utilities.coordinate_utilities import calculate_bearing, project_position_lat_lon

# The client's "start in the air" puts the aircraft this far before the starting point, on the course to it.
AIR_START_DISTANCE_M = 2 * 1852


def current_quickstart(now: Optional[datetime.datetime] = None) -> Optional[SimulatorQuickstart]:
    """The newest active quickstart whose task pilots can still register for themselves, or None."""
    now = now or timezone.now()
    return (
        SimulatorQuickstart.objects.filter(
            active=True,
            navigation_task__allow_self_management=True,
            navigation_task__finish_time__gt=now,
        )
        .select_related("navigation_task", "navigation_task__contest", "navigation_task__route")
        .first()
    )


def _runway_heading(gate, towards: Optional[tuple]) -> Optional[float]:
    """
    The take-off direction along the runway: square to the take-off gate's line, the way that points nearest to the first
    waypoint (the runway itself has two directions; the route continues on one side).
    """
    line = getattr(gate, "gate_line", None) or []
    if len(line) < 2:
        return None
    across = calculate_bearing(tuple(line[0]), tuple(line[1]))
    options = [(across + 90) % 360, (across + 270) % 360]
    if towards is None:
        return options[0]
    target = calculate_bearing((gate.latitude, gate.longitude), towards)
    return min(options, key=lambda h: abs((h - target + 180) % 360 - 180))


def ground_start(quickstart: SimulatorQuickstart) -> Optional[dict]:
    """On the runway at the task's take-off gate, facing the take-off direction; None without a take-off gate."""
    route = quickstart.navigation_task.route
    gate = route.first_takeoff_gate if route else None
    if gate is None:
        return None
    first = (route.waypoints[0].latitude, route.waypoints[0].longitude) if route.waypoints else None
    heading = _runway_heading(gate, first)
    return {"latitude": gate.latitude, "longitude": gate.longitude, "heading": round(heading, 1) if heading is not None else None}


def air_start(quickstart: SimulatorQuickstart) -> Optional[dict]:
    """In the air before the starting point, on the course to it, at the quickstart's altitude; None without waypoints."""
    route = quickstart.navigation_task.route
    if not route or not route.waypoints:
        return None
    start = route.waypoints[0]
    course = getattr(start, "bearing_next", -1)
    if course is None or course < 0:
        if len(route.waypoints) < 2:
            return None
        course = calculate_bearing((start.latitude, start.longitude), (route.waypoints[1].latitude, route.waypoints[1].longitude))
    latitude, longitude = project_position_lat_lon((start.latitude, start.longitude), (course + 180) % 360, AIR_START_DISTANCE_M)
    return {
        "latitude": float(latitude),
        "longitude": float(longitude),
        "altitude_ft": quickstart.air_start_altitude_ft,
        "heading": round(float(course), 1),
    }


def registered_flight(quickstart: SimulatorQuickstart, person: Person, now: Optional[datetime.datetime] = None) -> Optional[Contestant]:
    """The pilot's own flight in the quickstart task that has not finished yet, if they have registered."""
    now = now or timezone.now()
    return (
        Contestant.objects.filter(
            navigation_task=quickstart.navigation_task,
            team__crew__member1=person,
            finished_by_time__gt=now,
        )
        .order_by("takeoff_time")
        .first()
    )


def quickstart_for(person: Person, now: Optional[datetime.datetime] = None) -> Optional[dict]:
    """What the client shows: the flight, where to start, how to register and whether the pilot has. None: nothing offered."""
    quickstart = current_quickstart(now)
    if quickstart is None:
        return None
    task = quickstart.navigation_task
    contest = task.contest
    flight = registered_flight(quickstart, person, now)
    return {
        "id": quickstart.pk,
        "title": quickstart.title or task.name,
        "description": quickstart.description,
        "contest_id": contest.pk,
        "contest_name": contest.name,
        "navigation_task_id": task.pk,
        "navigation_task_name": task.name,
        "start_location": quickstart.start_location,
        "start_instructions": quickstart.start_instructions,
        "ground_start": ground_start(quickstart),
        "air_start": air_start(quickstart),
        # The website's own registration page; in the client it reports the registration back (airsportsapp://registered).
        "registration_path": f"/schedule-flight?contestId={contest.pk}&navigationTaskId={task.pk}",
        "registered_flight": (
            {
                "id": flight.pk,
                "takeoff_time": flight.takeoff_time,
                "tracker_start_time": flight.tracker_start_time,
                "finished_by_time": flight.finished_by_time,
            }
            if flight
            else None
        ),
    }
