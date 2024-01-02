import datetime
import logging
from typing import List, Tuple

from django.core.exceptions import ObjectDoesNotExist, ValidationError

from display.utilities.calculate_gate_times import calculate_and_get_relative_gate_times
from display.contestant_scheduling.contestant_scheduler import TeamDefinition, Solver
from display.models import NavigationTask, ContestTeam, Contestant
from display.utilities.navigation_task_type_definitions import LANDING

logger = logging.getLogger(__name__)


def schedule_and_create_contestants(
    navigation_task: NavigationTask,
    contest_teams_pks: List[int],
    first_takeoff_time: datetime.datetime,
    tracker_leadtime_minutes: int,
    aircraft_switch_time_minutes: int,
    tracker_switch_time: int,
    minimum_start_interval: int,
    minimum_finish_interval: int,
    crew_switch_time: int,
    optimise: bool = False,
) -> Tuple[bool, List[str]]:
    if LANDING in navigation_task.scorecard.task_type:
        return schedule_and_create_contestants_landing_task(
            navigation_task,
            contest_teams_pks,
            first_takeoff_time,
            tracker_leadtime_minutes,
            aircraft_switch_time_minutes,
            tracker_switch_time,
            minimum_start_interval,
            crew_switch_time,
            optimise,
        )
    else:
        return schedule_and_create_contestants_navigation_tasks(
            navigation_task,
            contest_teams_pks,
            first_takeoff_time,
            tracker_leadtime_minutes,
            aircraft_switch_time_minutes,
            tracker_switch_time,
            minimum_start_interval,
            minimum_finish_interval,
            crew_switch_time,
            optimise,
        )


def schedule_and_create_contestants_landing_task(
    navigation_task: NavigationTask,
    contest_teams_pks: List[int],
    first_takeoff_time: datetime.datetime,
    tracker_leadtime_minutes: int,
    aircraft_switch_time_minutes: int,
    tracker_switch_time: int,
    minimum_start_interval: int,
    crew_switch_time: int,
    optimise: bool = False,
) -> Tuple[bool, List[str]]:
    selected_contest_teams = ContestTeam.objects.filter(pk__in=contest_teams_pks)

    for index, contest_team in enumerate(selected_contest_teams):
        try:
            contestant = navigation_task.contestant_set.get(team=contest_team.team)
            contestant.takeoff_time = first_takeoff_time
            contestant.finished_by_time = navigation_task.finish_time
            contestant.tracker_start_time = navigation_task.start_time
            contestant.save()
        except ObjectDoesNotExist:
            Contestant.objects.create(
                takeoff_time=navigation_task.start_time,
                finished_by_time=navigation_task.finish_time,
                air_speed=contest_team.air_speed,
                wind_speed=navigation_task.wind_speed,
                wind_direction=navigation_task.wind_direction,
                team=contest_team.team,
                minutes_to_starting_point=navigation_task.minutes_to_starting_point,
                navigation_task=navigation_task,
                tracking_service=contest_team.tracking_service,
                tracker_device_id=contest_team.tracker_device_id,
                tracking_device=contest_team.tracking_device,
                tracker_start_time=navigation_task.start_time,
                contestant_number=index + 1,
            )
    return True, []


def schedule_and_create_contestants_navigation_tasks(
    navigation_task: NavigationTask,
    contest_teams_pks: List[int],
    first_takeoff_time: datetime.datetime,
    tracker_leadtime_minutes: int,
    aircraft_switch_time_minutes: int,
    tracker_switch_time: int,
    minimum_start_interval: int,
    minimum_finish_interval: int,
    crew_switch_time: int,
    optimise: bool = False,
) -> Tuple[bool, List[str]]:
    optimisation_messages = []
    contest_teams = []
    selected_contest_teams = ContestTeam.objects.filter(pk__in=contest_teams_pks)
    if tracker_switch_time < tracker_leadtime_minutes:
        raise ValidationError(
            f"The tracker switch time {tracker_switch_time} must be larger than the tracker leadtime {tracker_leadtime_minutes}"
        )
    for contest_team in selected_contest_teams:  # type: ContestTeam
        contest_teams.append(
            (
                contest_team,
                contest_team.air_speed,
                navigation_task.wind_speed,
                navigation_task.wind_direction,
                navigation_task.minutes_to_starting_point,
                navigation_task.minutes_to_landing,
                False,  # frozen
                None,  # start_time
            )
        )
    team_data = []
    for (
        contest_team,
        speed,
        wind_speed,
        wind_direction,
        minutes_to_starting_point,
        minutes_to_landing,
        frozen,
        start_time,
    ) in contest_teams:
        gate_times = calculate_and_get_relative_gate_times(navigation_task.route, speed, wind_speed, wind_direction)
        duration = datetime.timedelta(minutes=minutes_to_starting_point + minutes_to_landing) + gate_times[-1][1]
        team_data.append(
            TeamDefinition(
                contest_team.pk,
                duration.total_seconds() / 60,
                contest_team.get_tracker_id(),
                contest_team.tracking_service,
                contest_team.team.aeroplane.registration,
                contest_team.team.crew.member1.pk if contest_team.team.crew.member1 else None,
                contest_team.team.crew.member2.pk if contest_team.team.crew.member2 else None,
                frozen,
                start_time,
            )
        )
    print("Initiating solver")
    solver = Solver(
        first_takeoff_time,
        int((navigation_task.finish_time - navigation_task.start_time).total_seconds() / 60),
        team_data,
        minimum_start_interval=minimum_start_interval,
        minimum_finish_interval=minimum_finish_interval,
        aircraft_switch_time=aircraft_switch_time_minutes,
        tracker_start_lead_time=tracker_leadtime_minutes,
        tracker_switch_time=tracker_switch_time,
        crew_switch_time=crew_switch_time,
        optimise=optimise,
    )
    print("Running solver")
    team_definitions = solver.schedule_teams()
    optimisation_messages.extend(solver.optimisation_messages)
    if len(team_definitions) == 0:
        return False, optimisation_messages
    contestants = []
    earliest_tracking_start = datetime.datetime.max.replace(tzinfo=datetime.timezone.utc)
    latest_tracking_finish = datetime.datetime.max.replace(tzinfo=datetime.timezone.utc)
    for team_definition in team_definitions:
        contest_team = ContestTeam.objects.get(pk=team_definition.pk)
        tracking_start_time = (
            team_definition.start_time - datetime.timedelta(minutes=tracker_leadtime_minutes)
        ).replace(microsecond=0)
        tracking_finish_time = (
            team_definition.start_time
            + datetime.timedelta(minutes=team_definition.flight_time + tracker_switch_time - tracker_leadtime_minutes)
        ).replace(microsecond=0)
        earliest_tracking_start = min(earliest_tracking_start, tracking_start_time)
        latest_tracking_finish = max(latest_tracking_finish, tracking_finish_time)
        contestants.append(
            Contestant(
                takeoff_time=team_definition.start_time.replace(microsecond=0),
                finished_by_time=tracking_finish_time,
                air_speed=contest_team.air_speed,
                wind_speed=navigation_task.wind_speed,
                wind_direction=navigation_task.wind_direction,
                team=contest_team.team,
                tracking_device=contest_team.tracking_device,
                minutes_to_starting_point=navigation_task.minutes_to_starting_point,
                navigation_task=navigation_task,
                tracking_service=contest_team.tracking_service,
                tracker_device_id=contest_team.tracker_device_id,
                tracker_start_time=tracking_start_time,
                contestant_number=0,
            )
        )
    if navigation_task.contestant_set.filter(
        finished_by_time__gte=earliest_tracking_start, tracker_start_time__lte=latest_tracking_finish
    ).exists():
        raise ValidationError(
            f"There are pre-existing contestants in the task time interval ({earliest_tracking_start.strftime('%Y-%m-%m %H:%M:%S %z')} "
            f"to {latest_tracking_finish.strftime('%Y-%m-%m %H:%M:%S %z')}.  This is not supported by the scheduling "
            f"algorithm. Please remove any contestants in this interval or consider changing the first takeoff time. "
            f"If you do not wish to do this, consider creating the new contestants manually using the 'Add contestant' "
            f"link at the bottom of the contestants overview page."
        )
    contestants.sort(key=lambda c: c.takeoff_time)
    if navigation_task.contestant_set.all().count() > 0:
        maximum_contestant = max([item.contestant_number for item in navigation_task.contestant_set.all()])
    else:
        maximum_contestant = 0
    for index, contestant in enumerate(contestants):
        contestant.contestant_number = maximum_contestant + index + 1
    Contestant.objects.bulk_create(contestants)
    return True, optimisation_messages
