"""
The practice flight the MSFS client offers new pilots (SimulatorQuickstart): which one, where to start in the simulator,
and whether the pilot has registered for it already.
"""

import datetime
from typing import Optional

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from display.models import Contest, Contestant, ContestTeam, Person, SimulatorQuickstart, Team
from display.services.capacity_enforcement import assert_can_register_team, assert_can_self_register_contestant
from display.services.self_registration import create_self_managed_contestant
from display.utilities.coordinate_utilities import calculate_bearing, project_position_lat_lon
from display.utilities.simulator_policy import FLIGHT_MODE_REAL, FLIGHT_MODE_SIMULATOR, policy_allows

# The client's "start in the air" puts the aircraft this far before the starting point, on the course to it.
AIR_START_DISTANCE_M = 2 * 1852

# A one-press registration plans the starting point this far ahead. With the adaptive start the tracking starts an hour
# before it, so the pilot can fly at once and has two hours to cross the starting line.
REGISTRATION_LEAD = datetime.timedelta(hours=1)


def may_register_for(user, navigation_task) -> bool:
    """
    Who may register themselves in the task, as on the website: anybody for a public task in a public contest,
    otherwise somebody who may view the contest.
    """
    contest = navigation_task.contest
    if navigation_task.is_public and contest.is_public:
        return True
    return bool(user is not None and user.is_authenticated and user.has_perm("display.view_contest", contest))


def current_quickstart(now: Optional[datetime.datetime] = None, user=None) -> Optional[SimulatorQuickstart]:
    """
    The newest active quickstart whose task pilots can still register for themselves and that [user] may register
    in (without a user only public ones qualify), or None.
    """
    now = now or timezone.now()
    candidates = SimulatorQuickstart.objects.filter(
        active=True,
        navigation_task__allow_self_management=True,
        navigation_task__finish_time__gt=now,
    ).select_related("navigation_task", "navigation_task__contest", "navigation_task__route")
    for quickstart in candidates:
        # A task that does not accept simulator flights would drop every position of the practice flight.
        if not policy_allows(quickstart.navigation_task.simulator_policy, True):
            continue
        if may_register_for(user, quickstart.navigation_task):
            return quickstart
    return None


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
        # A real flight in the same task is not the practice flight: it would reject the simulator's positions
        .exclude(flight_mode=FLIGHT_MODE_REAL)
        .order_by("takeoff_time")
        .first()
    )


def register(user, person: Person, now: Optional[datetime.datetime] = None) -> Contestant:
    """
    The client's one-press registration: signs the pilot up for the contest with the quickstart's aircraft, club and speed
    (unless they are signed up already) and sets up the flight at the quickstart's speed (always, also for a pilot signed
    up with a speed of their own), with no wind and an adaptive start that is open now. The
    flight order is made in the background and e-mailed, as on the website. Registering again returns the same flight.
    """
    now = now or timezone.now()
    quickstart = current_quickstart(now, user)
    if quickstart is None:
        raise ValidationError("No practice flight is offered right now")
    existing = registered_flight(quickstart, person, now)
    if existing is not None:
        return existing
    task = quickstart.navigation_task
    contest = task.contest
    with transaction.atomic():
        Contest.objects.select_for_update().get(pk=contest.pk)
        # Again, now that the lock is held: a double press must not make two flights
        existing = registered_flight(quickstart, person, now)
        if existing is not None:
            return existing
        contest_team = ContestTeam.objects.filter(contest=contest, team__crew__member1=person).first()
        if contest_team is None:
            if ContestTeam.objects.filter(contest=contest, team__crew__member2=person).exists():
                raise ValidationError(
                    "You are signed up for this contest as a co-pilot. Register the flight on the website instead."
                )
            team = Team.get_or_create_from_signup(user, None, quickstart.aircraft_registration, quickstart.club_name)
            assert_can_register_team(contest, team)
            contest_team = contest.replace_team(None, team, {"air_speed": quickstart.air_speed})
        assert_can_self_register_contestant(task, contest_team)
        # Whole minutes, rounded down, so the tracking window (an hour before) is open already: the client tracks at once.
        starting_point_time = (now + REGISTRATION_LEAD).replace(second=0, microsecond=0)
        # Always the practice speed, also for a pilot who is signed up already: their team keeps its own speed.
        contestant = create_self_managed_contestant(
            task,
            contest_team,
            starting_point_time,
            adaptive_start=True,
            wind_speed=0,
            wind_direction=0,
            declaration_input={},
            air_speed=quickstart.air_speed,
            flight_mode=FLIGHT_MODE_SIMULATOR,
        )

        def make_flight_order():
            from display.tasks import generate_and_maybe_notify_flight_order

            generate_and_maybe_notify_flight_order.apply_async((contestant.pk, user.email, user.first_name, True))

        transaction.on_commit(make_flight_order)
    return contestant


def flight_order_path(flight: Contestant) -> Optional[str]:
    """The download page of the flight's newest flight order, or None until one has been made."""
    uid = flight.newest_flight_order_link_uid
    return f"/display/maplink/{uid}/" if uid else None


def quickstart_for(person: Person, now: Optional[datetime.datetime] = None, user=None) -> Optional[dict]:
    """What the client shows: the flight, where to start, how to register and whether the pilot has. None: nothing offered."""
    quickstart = current_quickstart(now, user)
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
        # What the one-press registration (POST msfs_quickstart_register) signs the pilot up with.
        "air_speed": quickstart.air_speed,
        "aircraft_registration": quickstart.aircraft_registration,
        "club_name": quickstart.club_name,
        "registered_flight": (
            {
                "id": flight.pk,
                "takeoff_time": flight.takeoff_time,
                "tracker_start_time": flight.tracker_start_time,
                "finished_by_time": flight.finished_by_time,
                "adaptive_start": flight.adaptive_start,
                "air_speed": flight.air_speed,
                # The flight order's download page once it has been made (it is made in the background), else None.
                "flight_order_path": flight_order_path(flight),
            }
            if flight
            else None
        ),
    }
