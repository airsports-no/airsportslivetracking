import datetime
import logging
from typing import List, Tuple

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django.db.models import Q

from display.utilities.calculate_gate_times import calculate_and_get_relative_gate_times
from display.contestant_scheduling.contestant_scheduler import TeamDefinition, Solver
from display.models import NavigationTask, ContestTeam, Contestant
from display.services.task_compiler import TaskCompiler
from display.services.contestant_task_compiler import ContestantTaskCompiler
from display.utilities.navigation_task_type_definitions import LANDING

logger = logging.getLogger(__name__)

# Scheduler-created contract-navigation contestants are seeded with a conservative
# placeholder declaration so downstream compilation has an explicit T contract.
# Organizers are expected to review/edit the declaration in the dedicated editor
# before using the contestant for real competition operations.
DEFAULT_CONTRACT_NAVIGATION_T_SECONDS = 600

def _build_default_declaration_payload(navigation_task: NavigationTask) -> dict:
    if not navigation_task.requires_contestant_task_configuration():
        return {}
    compiled_task = TaskCompiler(navigation_task).compile()
    if not compiled_task.is_valid:
        return {}
    primitives = compiled_task.get_compiled_primitives()
    if navigation_task.task_subtype == "contract_navigation_time_controls":
        catalogue_turnpoints = [name for name in primitives.get("catalogue_turnpoint", []) if name not in ("MP", "FP")]
        if not catalogue_turnpoints:
            return {}
        declared_sequence = [catalogue_turnpoints[0], "MP"]
        if len(catalogue_turnpoints) > 1:
            declared_sequence.append(catalogue_turnpoints[1])
        declared_sequence.append("FP")
        return {"declared_sequence": declared_sequence, "declared_t_seconds": DEFAULT_CONTRACT_NAVIGATION_T_SECONDS}
    return {}


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
    next_takeoff_time: datetime.datetime = None,
) -> Tuple[bool, List[str]]:
    if next_takeoff_time is None:
        next_takeoff_time = first_takeoff_time
    navigation_task.schedule_start_time = first_takeoff_time
    navigation_task.save(update_fields=["schedule_start_time"])
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
            next_takeoff_time,
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
            next_takeoff_time,
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
    next_takeoff_time: datetime.datetime = None,
) -> Tuple[bool, List[str]]:
    # contest= scoping is deliberate: contest_teams_pks is client-supplied (only coerced to
    # ints by _normalize_contest_team_ids, no ownership check), so without this an organiser
    # could pull another contest's team - and its tracker_device_id - into this task.
    selected_contest_teams = ContestTeam.objects.filter(pk__in=contest_teams_pks, contest=navigation_task.contest)

    for index, contest_team in enumerate(selected_contest_teams):
        try:
            contestant = navigation_task.contestant_set.get(team=contest_team.team)
            contestant.takeoff_time = next_takeoff_time
            contestant.finished_by_time = navigation_task.finish_time
            contestant.tracker_start_time = navigation_task.start_time
            contestant.save()
            ContestantTaskCompiler(contestant).compile(
                declaration_payload=_build_default_declaration_payload(navigation_task),
                force=True,
            )
        except ObjectDoesNotExist:
            contestant = Contestant.objects.create(
                takeoff_time=next_takeoff_time,
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
            ContestantTaskCompiler(contestant).compile(
                declaration_payload=_build_default_declaration_payload(navigation_task),
                force=True,
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
    next_takeoff_time: datetime.datetime = None,
) -> Tuple[bool, List[str]]:
    optimisation_messages = []

    # 1. Identify Existing Locked Contestants (Immutable)
    locked_contestants = navigation_task.contestant_set.filter(
        Q(schedule_locked=True) | Q(contestanttrack__calculator_started=True), finished_by_time__gte=first_takeoff_time
    )

    # 2. Clean up Unlocked Contestants (Mutable)
    # Delete contestants that are NOT locked and are scheduled AFTER the first takeoff time.
    # The scheduling process owns everything after this point.
    # We also need to remove contestants whose teams are no longer in the selected list, unless they are locked.

    mutable_contestants = navigation_task.contestant_set.filter(
        finished_by_time__gte=first_takeoff_time, schedule_locked=False, contestanttrack__calculator_started=False
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

    # contest= scoping is deliberate - see the comment on the equivalent line in
    # schedule_and_create_contestants_landing_task above.
    selected_contest_teams = ContestTeam.objects.filter(pk__in=contest_teams_pks, contest=navigation_task.contest)
    if not selected_contest_teams.exists():
        mutable_contestants.delete()
        return True, []

    mutable_contestants = list(mutable_contestants)
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
        next_takeoff_time,
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

    with transaction.atomic():
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
                        ContestantTaskCompiler(contestant).compile(
                            declaration_payload=_build_default_declaration_payload(navigation_task),
                            force=True,
                        )
                        contestant.reset_gate_times()
                        optimisation_messages.extend(contestant.get_overlap_warnings())

                    except IndexError:
                        contestant = None
                if not contestant:
                    # Create new contestant
                    contestant = Contestant.objects.create(
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
                    ContestantTaskCompiler(contestant).compile(
                        declaration_payload=_build_default_declaration_payload(navigation_task),
                        force=True,
                    )
                    optimisation_messages.extend(contestant.get_overlap_warnings())
                new_contestants_created += 1

        # Delete any remaining mutable contestants that were not reused (i.e. team was deselected or schedule reduced)
        for unused_contestant in mutable_contestants:
            unused_contestant.delete()

        # Re-assign contestant numbers based on takeoff time for ALL contestants in task
        # Constraints:
        # 1. Locked contestants MUST keep their number.
        # 2. Unlocked contestants should be numbered to be "consistent with starting order as far as possible".

        all_contestants = list(navigation_task.contestant_set.all().order_by("takeoff_time"))

        def _keeps_its_number(c) -> bool:
            # Must match the freeze-set query above (locked_contestants / mutable_contestants):
            # a contestant whose calculator has started is frozen there too, but this loop
            # only checked schedule_locked - nothing sets schedule_locked when a calculator
            # starts (only the CIMA declaration lock and a manual UI toggle do), so a live
            # contestant could get renumbered here and collide with a new contestant's
            # number, raising IntegrityError on the (navigation_task, contestant_number)
            # unique constraint.
            calculator_started = hasattr(c, "contestanttrack") and c.contestanttrack.calculator_started
            return c.schedule_locked or c.finished_by_time < first_takeoff_time or calculator_started

        # Identify locked numbers
        locked_numbers = set()
        historical_contestant_numbers = []
        for c in all_contestants:
            if _keeps_its_number(c):
                locked_numbers.add(c.contestant_number)
            if c.finished_by_time < first_takeoff_time:
                historical_contestant_numbers.append(c.contestant_number)

        # Assign numbers
        target_number = max(historical_contestant_numbers) + 1 if historical_contestant_numbers else 1
        for c in all_contestants:
            if _keeps_its_number(c):
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
