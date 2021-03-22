import datetime
from typing import Optional, List

from django.core.exceptions import ObjectDoesNotExist, ValidationError

from display.calculate_gate_times import calculate_and_get_relative_gate_times
from display.contestant_scheduler import TeamDefinition, Solver
from display.models import NavigationTask, ContestTeam, Contestant, Scorecard


def schedule_and_create_contestants(navigation_task: NavigationTask, contest_teams_pks: List[int],
                                    tracker_leadtime_minutes: int, aircraft_switch_time_minutes: int,
                                    tracker_switch_time: int, minimum_start_interval: int, crew_switch_time: int,
                                    optimise: bool = False) -> bool:
    if Scorecard.LANDING in navigation_task.scorecard.task_type:
        return schedule_and_create_contestants_landing_task(navigation_task, contest_teams_pks,
                                                            tracker_leadtime_minutes, aircraft_switch_time_minutes,
                                                            tracker_switch_time, minimum_start_interval,
                                                            crew_switch_time, optimise)
    else:
        return schedule_and_create_contestants_navigation_tasks(navigation_task, contest_teams_pks,
                                                                tracker_leadtime_minutes, aircraft_switch_time_minutes,
                                                                tracker_switch_time, minimum_start_interval,
                                                                crew_switch_time, optimise)


def schedule_and_create_contestants_landing_task(navigation_task: NavigationTask, contest_teams_pks: List[int],
                                                 tracker_leadtime_minutes: int, aircraft_switch_time_minutes: int,
                                                 tracker_switch_time: int, minimum_start_interval: int,
                                                 crew_switch_time: int,
                                                 optimise: bool = False) -> bool:
    selected_contest_teams = ContestTeam.objects.filter(pk__in=contest_teams_pks)
    # Remove contestants that are not selected:
    navigation_task.contestant_set.exclude(team__in=[item.team for item in selected_contest_teams]).delete()
    for index, contest_team in enumerate(selected_contest_teams):
        try:
            contestant = navigation_task.contestant_set.get(team=contest_team.team)
            contestant.takeoff_time = navigation_task.start_time
            contestant.finished_by_time = navigation_task.finish_time
            contestant.tracker_start_time = navigation_task.start_time
            contestant.save()
        except ObjectDoesNotExist:
            Contestant.objects.create(takeoff_time=navigation_task.start_time,
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
                                      contestant_number=index + 1)
    return True


def schedule_and_create_contestants_navigation_tasks(navigation_task: NavigationTask, contest_teams_pks: List[int],
                                                     tracker_leadtime_minutes: int, aircraft_switch_time_minutes: int,
                                                     tracker_switch_time: int, minimum_start_interval: int,
                                                     crew_switch_time: int,
                                                     optimise: bool = False) -> bool:
    contest_teams = []
    final_waypoint = navigation_task.route.waypoints[-1]
    selected_contest_teams = ContestTeam.objects.filter(pk__in=contest_teams_pks)
    if tracker_switch_time < tracker_leadtime_minutes:
        raise ValidationError(
            f"The tracker switch time {tracker_switch_time} must be larger than the tracker leadtime {tracker_leadtime_minutes}")
    # Remove contestants that are not selected:
    navigation_task.contestant_set.exclude(team__in=[item.team for item in selected_contest_teams]).delete()

    for contest_team in selected_contest_teams:
        try:
            contestant = navigation_task.contestant_set.get(team=contest_team.team)

            contest_teams.append((contest_team, contestant.air_speed, contestant.wind_speed,
                                  contestant.wind_direction, contestant.minutes_to_starting_point,
                                  (contestant.finished_by_time - contestant.gate_times[
                                      final_waypoint.name]).total_seconds() / 60))
        except ObjectDoesNotExist:
            contest_teams.append((contest_team, contest_team.air_speed, navigation_task.wind_speed,
                                  navigation_task.wind_direction, navigation_task.minutes_to_starting_point,
                                  navigation_task.minutes_to_landing))
    team_data = []
    for contest_team, speed, wind_speed, wind_direction, minutes_to_starting_point, minutes_to_landing in contest_teams:
        gate_times = calculate_and_get_relative_gate_times(navigation_task.route, speed,
                                                           wind_speed, wind_direction)
        duration = datetime.timedelta(minutes=minutes_to_starting_point + minutes_to_landing) + gate_times[-1][1]
        team_data.append(
            TeamDefinition(contest_team.pk, duration.total_seconds() / 60, contest_team.get_tracker_id(),
                           contest_team.tracking_service, contest_team.team.aeroplane.registration,
                           contest_team.team.crew.member1.pk if contest_team.team.crew.member1 else None,
                           contest_team.team.crew.member2.pk if contest_team.team.crew.member2 else None))
    print("Initiating solver")
    solver = Solver(navigation_task.start_time,
                    int((navigation_task.finish_time - navigation_task.start_time).total_seconds() / 60), team_data,
                    minimum_start_interval=minimum_start_interval, aircraft_switch_time=aircraft_switch_time_minutes,
                    tracker_start_lead_time=tracker_leadtime_minutes, tracker_switch_time=tracker_switch_time,
                    crew_switch_time=crew_switch_time, optimise=optimise)
    print("Running solver")
    team_definitions = solver.schedule_teams()
    if len(team_definitions) == 0:
        return False
    for team_definition in team_definitions:
        contest_team = ContestTeam.objects.get(pk=team_definition.pk)
        # print(f"start_time: {team_definition.start_time}")
        # print(f"start_slot: {team_definition.start_slot}")
        try:
            contestant = navigation_task.contestant_set.get(team=contest_team.team)
            start_offset = team_definition.start_time - contestant.takeoff_time
            contestant.tracker_start_time = team_definition.start_time - datetime.timedelta(
                minutes=tracker_leadtime_minutes)
            contestant.takeoff_time += start_offset
            contestant.finished_by_time += start_offset
            if contestant.predefined_gate_times is not None:
                for key, value in contestant.predefined_gate_times.items():
                    contestant.predefined_gate_times[key] = value + start_offset
            contestant.save()
        except ObjectDoesNotExist:
            if navigation_task.contestant_set.all().count() > 0:
                maximum_contestant = max([item.contestant_number for item in navigation_task.contestant_set.all()])
            else:
                maximum_contestant = 0
            contestant = Contestant.objects.create(takeoff_time=team_definition.start_time.replace(microsecond=0),
                                                   finished_by_time=(team_definition.start_time + datetime.timedelta(
                                                       minutes=team_definition.flight_time + tracker_switch_time - tracker_leadtime_minutes)).replace(
                                                       microsecond=0),
                                                   air_speed=contest_team.air_speed,
                                                   wind_speed=navigation_task.wind_speed,
                                                   wind_direction=navigation_task.wind_direction,
                                                   team=contest_team.team,
                                                   tracking_device=contest_team.tracking_device,
                                                   minutes_to_starting_point=navigation_task.minutes_to_starting_point,
                                                   navigation_task=navigation_task,
                                                   tracking_service=contest_team.tracking_service,
                                                   tracker_device_id=contest_team.tracker_device_id,
                                                   tracker_start_time=(team_definition.start_time - datetime.timedelta(
                                                       minutes=tracker_leadtime_minutes)).replace(microsecond=0),
                                                   contestant_number=maximum_contestant + 1)
    return True
