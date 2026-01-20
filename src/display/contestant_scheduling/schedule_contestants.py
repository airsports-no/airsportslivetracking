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

    # 1. Identify Existing Locked Contestants (Immutable)
    locked_contestants = navigation_task.contestant_set.filter(
        finished_by_time__gte=first_takeoff_time, schedule_locked=True
    )

    # 2. Clean up Unlocked Contestants (Mutable)
    # Delete contestants that are NOT locked and are scheduled AFTER the first takeoff time.
    # The scheduling process owns everything after this point.
    # We also need to remove contestants whose teams are no longer in the selected list, unless they are locked.

    mutable_contestants = list(
        navigation_task.contestant_set.filter(finished_by_time__gte=first_takeoff_time, schedule_locked=False)
    )

    # Also delete contestants for unselected teams if they are not locked, regardless of time?
    # The requirement says: "Contestants and that belonged to a contest team that is not selected must be deleted."
    # AND "Contestants that finish after the first take off time with schedule_locked=False are subject to the scheduling algorithm."
    # Let's interpret this as:
    # - Locked contestants are kept no matter what.
    # - Contestants taking off BEFORE first_takeoff_time are kept (historical/fixed).
    # - Contestants taking off AFTER first_takeoff_time and NOT locked are cleared and re-scheduled.

    # However, we also need to handle the case where a team is DESELECTED.
    # If a team is not in contest_teams_pks, its future unlocked contestant should be gone (handled by delete above).
    # But what if it had a contestant BEFORE the start time? The prompt implies "scheduling process owns everything that happens after the first take off time".
    # So we leave "past" contestants alone.

    selected_contest_teams = ContestTeam.objects.filter(pk__in=contest_teams_pks)

    # Teams to be scheduled are the selected teams.
    # Some of these teams might already have a LOCKED contestant in the future window (though user shouldn't select them if they want new schedule, or maybe the system should handle it).
    # If a team has a locked contestant, we probably shouldn't schedule another one for it in the same window?
    # For simplicity, the scheduler generates a slot. If a team is "frozen", it uses that slot.
    # Here, "frozen" maps to "schedule_locked".

    # Include locked contestants as "frozen" teams in the scheduler
    # We need to map them back to ContestTeams to include them in the constraints

    # A team might be in selected_contest_teams OR it might be associated with a locked contestant.
    # We need to consider ALL relevant teams for constraint checking.

    teams_to_process = {}  # Map team_pk -> (ContestTeam, existing_contestant or None)

    # Add selected teams (that need new or updated scheduling)
    for ct in selected_contest_teams:
        teams_to_process[ct.pk] = (ct, None)

    # Add locked contestants (as frozen constraints)
    # Only consider locked contestants that overlap with our scheduling window?
    # Or all locked contestants to ensure no resource conflicts?
    # Safer to include all locked contestants that effectively "exist" during the scheduling period.
    # Ideally, the scheduler handles the entire timeline, but here we are inserting into a window.
    # The constraints (aircraft, crew) must hold against ALL existing locked contestants.

    for contestant in locked_contestants:
        # If this contestant is far in the past, maybe it doesn't matter?
        # But for safety, let's include them.
        # Note: The scheduler assumes a single start time (first_takeoff_time).
        # Frozen teams with start_time < first_takeoff_time might cause issues with negative slots if not handled.
        # But we can just pass their fixed start time.

        ct = ContestTeam.objects.get(contest=navigation_task.contest, team=contestant.team)
        # If this team was also selected, the locked contestant takes precedence?
        # Or does "selected" mean "I want to schedule a NEW flight"?
        # Usually, one team = one contestant per task.
        # So if a team has a locked contestant, it is "done" and acts as a constraint.
        teams_to_process[ct.pk] = (ct, contestant)

    if tracker_switch_time < tracker_leadtime_minutes:
        raise ValidationError(
            f"The tracker switch time {tracker_switch_time} must be larger than the tracker leadtime {tracker_leadtime_minutes}"
        )

    team_definitions = []

    for pk, (contest_team, existing_contestant) in teams_to_process.items():
        # Determine parameters
        speed = contest_team.air_speed
        # Use contestant's speed if it exists and differs?
        if existing_contestant:
            speed = existing_contestant.air_speed

        gate_times = calculate_and_get_relative_gate_times(
            navigation_task.route, speed, navigation_task.wind_speed, navigation_task.wind_direction
        )
        duration = (
            datetime.timedelta(minutes=navigation_task.minutes_to_starting_point + navigation_task.minutes_to_landing)
            + gate_times[-1][1]
        )

        frozen = False
        start_time = None

        if existing_contestant:
            frozen = True
            # We must use the contestant's actual takeoff time
            # The scheduler expects timezone aware datetime if we give it one?
            # Or naive? Solver uses self.first_takeoff_time which is aware.
            start_time = existing_contestant.takeoff_time

        team_definitions.append(
            TeamDefinition(
                pk=contest_team.pk,
                flight_time=duration.total_seconds() / 60,
                tracker_id=contest_team.get_tracker_id(),
                tracker_service=contest_team.tracking_service,
                aircraft_registration=contest_team.team.aeroplane.registration,
                member1=contest_team.team.crew.member1.pk if contest_team.team.crew.member1 else None,
                member2=contest_team.team.crew.member2.pk if contest_team.team.crew.member2 else None,
                frozen=frozen,
                start_time=start_time,
            )
        )

    print("Initiating solver")
    solver = Solver(
        first_takeoff_time,
        int((navigation_task.finish_time - navigation_task.start_time).total_seconds() / 60),
        team_definitions,
        minimum_start_interval=minimum_start_interval,
        minimum_finish_interval=minimum_finish_interval,
        aircraft_switch_time=aircraft_switch_time_minutes,
        tracker_start_lead_time=tracker_leadtime_minutes,
        tracker_switch_time=tracker_switch_time,
        crew_switch_time=crew_switch_time,
        optimise=optimise,
    )
    print("Running solver")
    solved_teams = solver.schedule_teams()
    optimisation_messages.extend(solver.optimisation_messages)

    if len(solved_teams) == 0:
        return False, optimisation_messages

    # Create or Update contestants based on solution
    # Only process teams that were NOT frozen (i.e., the ones we wanted to schedule)

    earliest_tracking_start = datetime.datetime.max.replace(tzinfo=datetime.timezone.utc)
    latest_tracking_finish = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)

    # Sort results by start time for numbering
    solved_teams.sort(key=lambda t: t.start_time)

    new_contestants_created = 0

    for team_def in solved_teams:
        contest_team = ContestTeam.objects.get(pk=team_def.pk)

        # Calculate times
        tracking_start_time = (
            (team_def.start_time - datetime.timedelta(minutes=tracker_leadtime_minutes))
            .replace(microsecond=0)
            .astimezone(datetime.timezone.utc)
        )

        tracking_finish_time = (
            (
                team_def.start_time
                + datetime.timedelta(minutes=team_def.flight_time + tracker_switch_time - tracker_leadtime_minutes)
            )
            .replace(microsecond=0)
            .astimezone(datetime.timezone.utc)
        )

        takeoff_time = team_def.start_time.replace(microsecond=0).astimezone(datetime.timezone.utc)

        earliest_tracking_start = min(earliest_tracking_start, tracking_start_time)
        latest_tracking_finish = max(latest_tracking_finish, tracking_finish_time)

        if team_def.frozen:
            # Locked contestant, leave alone
            pass
        else:
            # Check if we can reuse a mutable contestant
            contestant = None
            if mutable_contestants:
                try:
                    index = [i for i, c in enumerate(mutable_contestants) if c.team == contest_team.team][0]
                    contestant = mutable_contestants.pop(index)
                    # Update existing contestant
                    contestant.takeoff_time = takeoff_time
                    contestant.finished_by_time = tracking_finish_time
                    contestant.air_speed = contest_team.air_speed
                    contestant.wind_speed = navigation_task.wind_speed
                    contestant.wind_direction = navigation_task.wind_direction
                    contestant.team = contest_team.team
                    contestant.minutes_to_starting_point = navigation_task.minutes_to_starting_point
                    # navigation_task remains same
                    contestant.tracking_service = contest_team.tracking_service
                    contestant.tracker_device_id = contest_team.tracker_device_id
                    contestant.tracking_device = contest_team.tracking_device
                    contestant.tracker_start_time = tracking_start_time
                    contestant.contestant_number = (
                        10000 + new_contestants_created + 1
                    )  # Temporary large numbercontestant
                    contestant.save()
                    contestant.reset_gate_times()

                except IndexError:
                    contestant = None
            if not contestant:
                # Create new contestant
                Contestant.objects.create(
                    takeoff_time=takeoff_time,
                    finished_by_time=tracking_finish_time,
                    air_speed=contest_team.air_speed,
                    wind_speed=navigation_task.wind_speed,
                    wind_direction=navigation_task.wind_direction,
                    team=contest_team.team,
                    minutes_to_starting_point=navigation_task.minutes_to_starting_point,
                    navigation_task=navigation_task,
                    tracking_service=contest_team.tracking_service,
                    tracker_device_id=contest_team.tracker_device_id,
                    tracking_device=contest_team.tracking_device,
                    tracker_start_time=tracking_start_time,
                    contestant_number=10000 + new_contestants_created + 1,  # Temporary large number
                )
            new_contestants_created += 1

    # Delete any remaining mutable contestants that were not reused (i.e. team was deselected or schedule reduced)
    for unused_contestant in mutable_contestants:
        unused_contestant.delete()

    # Re-assign contestant numbers based on takeoff time for ALL contestants in task
    # Constraints:
    # 1. Locked contestants MUST keep their number.
    # 2. Unlocked contestants should be numbered to be "consistent with starting order as far as possible".

    all_contestants = list(navigation_task.contestant_set.all().order_by("takeoff_time"))

    # Identify locked numbers
    locked_numbers = set()
    for c in all_contestants:
        if c.schedule_locked:
            locked_numbers.add(c.contestant_number)

    # Assign numbers
    target_number = 1
    for c in all_contestants:
        if c.schedule_locked:
            # Locked: Update target to be at least this + 1, so subsequent unlocked are higher if possible
            if c.contestant_number >= target_number:
                target_number = c.contestant_number + 1
        else:
            # Unlocked: Assign next available number
            while target_number in locked_numbers:
                target_number += 1

            c.contestant_number = target_number
            c.save(update_fields=["contestant_number"])
            target_number += 1

    return True, optimisation_messages
