"""
A pilot setting up their own flight in a self-managed task: shared by the website's "schedule flight" page
(NavigationTaskViewSet.contestant_self_registration) and the MSFS client's one-press practice flight.
"""

import datetime
import logging
from typing import Optional

from rest_framework.exceptions import ValidationError

from display.models import Contestant, ContestTeam, NavigationTask
from display.services.contestant_task_compiler import ContestantTaskCompiler
from display.utilities.simulator_policy import (
    FLIGHT_MODE_SIMULATOR,
    SIMULATOR_NOT_ALLOWED,
    flight_mode_for_platform,
    policy_allows,
)

logger = logging.getLogger(__name__)


def create_self_managed_contestant(
    navigation_task: NavigationTask,
    contest_team: ContestTeam,
    starting_point_time: datetime.datetime,
    adaptive_start: bool,
    wind_speed: float,
    wind_direction: float,
    declaration_input: Optional[dict] = None,
    air_speed: Optional[float] = None,
    flight_mode: Optional[str] = None,
) -> Contestant:
    """
    Creates and compiles the contestant. The caller checks that the pilot may register (team, contest and capacity) and
    queues the flight order (generate_and_maybe_notify_flight_order). The flight is planned at the team's speed in the
    contest unless [air_speed] is given (the MSFS practice flight); the team's registration is not changed.
    """
    takeoff_time = starting_point_time - datetime.timedelta(minutes=navigation_task.minutes_to_starting_point)
    existing_contestants = navigation_task.contestant_set.all()
    if existing_contestants.exists():
        contestant_number = max([item.contestant_number for item in existing_contestants]) + 1
    else:
        contestant_number = 1
    tracker_start_time = takeoff_time - datetime.timedelta(minutes=10)
    if adaptive_start:
        tracker_start_time = starting_point_time - datetime.timedelta(hours=1)
        takeoff_time = tracker_start_time

    contestant = Contestant(
        team=contest_team.team,
        takeoff_time=takeoff_time,
        navigation_task=navigation_task,
        tracker_start_time=tracker_start_time,
        adaptive_start=adaptive_start,
        finished_by_time=tracker_start_time + datetime.timedelta(days=1) - datetime.timedelta(minutes=1),
        minutes_to_starting_point=navigation_task.minutes_to_starting_point,
        air_speed=air_speed if air_speed is not None else contest_team.air_speed,
        contestant_number=contestant_number,
        wind_speed=wind_speed,
        wind_direction=wind_direction,
        flight_mode=flight_mode,
    )
    logger.debug("Created contestant")
    # None for a route without any timed gates (e.g. only dummy waypoints)
    flight_duration = contestant.flight_duration
    final_time = takeoff_time + flight_duration if flight_duration is not None else None
    logger.debug(f"Final gate time is {final_time}")

    if final_time is None:
        final_time = starting_point_time
    if adaptive_start:
        duration = final_time - starting_point_time
        # Properly account for how final time is created when adaptive start is active
        final_time = starting_point_time + datetime.timedelta(hours=1) + duration
    logger.debug(f"Take-off time is {contestant.takeoff_time}")
    logger.debug(f"Final time is {final_time}")
    contestant.finished_by_time = final_time + datetime.timedelta(minutes=navigation_task.minutes_to_landing + 2)
    logger.debug(f"Finished by time is {contestant.finished_by_time}")

    contestant.save()
    declaration_payload = ContestantTaskCompiler(contestant).build_declaration_payload_from_input(declaration_input)
    ContestantTaskCompiler(contestant).compile(declaration_payload=declaration_payload, force=True)
    logger.debug("Updated contestant")
    return contestant


def implied_flight_mode(request) -> Optional[str]:
    """The flight mode the requesting client implies (MSFS client: simulator, phone apps: real), None for the website."""
    return flight_mode_for_platform(request.META.get("HTTP_X_APP_PLATFORM")) or flight_mode_for_platform(
        getattr(request, "embed_client", None)
    )


def resolve_flight_mode(request, declared: Optional[str], navigation_task: NavigationTask) -> str:
    """
    The flight mode (real aircraft or simulator) of a registration made through [request]. The MSFS client and the phone apps
    are recognised by the server (their X-App-Platform header, or the client marker of their embedded web pages) and decide for
    themselves; on the website the pilot has to choose, so nothing is assumed. Refused when the task does not accept that kind
    of flight.
    """
    mode = implied_flight_mode(request) or declared
    if not mode:
        raise ValidationError({"flight_mode": "Choose whether you will fly a real aircraft or in a flight simulator."})
    if not policy_allows(navigation_task.simulator_policy, mode == FLIGHT_MODE_SIMULATOR):
        if navigation_task.simulator_policy == SIMULATOR_NOT_ALLOWED:
            message = "This task does not accept flights flown in a simulator."
        else:
            message = "This task is for flight simulators only."
        raise ValidationError({"flight_mode": message})
    return mode
