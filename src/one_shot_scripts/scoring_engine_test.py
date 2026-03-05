import os
import sys
import datetime
import logging
import json
import difflib
from django.db import transaction
from django.core.cache import cache

# Setup Django
sys.path.append("/workspace/src")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
import django

django.setup()

from display.models import (
    Contest,
    ContestTeam,
    NavigationTask,
    Contestant,
    ContestantReceivedPosition,
    ScoreLogEntry,
    ContestantTrack,
    Route,
    Prohibited,
    Scorecard,
    Person,
    Crew,
    Team,
    Aeroplane,
)
from display.calculators.contestant_processor import ContestantProcessor
from redis_queue import RedisQueue

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

CLONE_PREFIX = "[RECALC_TEST] "
REPORT_FILE = "recalculation_test_report.txt"
BASE_URL = "http://localhost:8002"
IGNORE_TASKS = [3108]


def get_tracking_link(contest_pk, task_pk):
    return f"{BASE_URL}/competition-map/{contest_pk}/{task_pk}/"


def delete_existing_clones():
    logger.info("Deleting existing cloned contests...")
    clones = Contest.objects.filter(name__startswith=CLONE_PREFIX)
    count = clones.count()
    for clone in clones:
        tasks = NavigationTask.objects.filter(contest=clone)
        for task in tasks:
            route_id = task.route_id
            task.delete()
            if route_id:
                Route.objects.filter(pk=route_id).delete()
        clone.delete()

    # Also cleanup scorecards
    Scorecard.objects.filter(name__startswith=CLONE_PREFIX).delete()
    logger.info(f"Deleted {count} cloned contests.")


def clone_contest(original_contest):
    logger.info(f"Cloning contest: {original_contest.name}")
    new_contest = Contest.objects.create(
        name=f"{CLONE_PREFIX}{original_contest.name}_{datetime.datetime.now().timestamp()}",
        time_zone=original_contest.time_zone,
        location=original_contest.location,
        start_time=original_contest.start_time,
        finish_time=original_contest.finish_time,
        is_public=False,
        is_featured=False,
        summary_score_sorting_direction=original_contest.summary_score_sorting_direction,
        autosum_scores=original_contest.autosum_scores,
    )

    for ct in ContestTeam.objects.filter(contest=original_contest):
        ContestTeam.objects.create(
            contest=new_contest,
            team=ct.team,
            air_speed=ct.air_speed,
            tracking_service=ct.tracking_service,
            tracking_device=ct.tracking_device,
            tracker_device_id=ct.tracker_device_id,
        )
    return new_contest


def clone_navigation_task(original_task, new_contest):
    logger.info(f"  Cloning navigation task: {original_task.name}")
    new_route = original_task.route.create_copy()
    for prohibited in original_task.route.prohibited_set.all():
        prohibited.copy_to_new_route(new_route)

    new_scorecard = original_task.scorecard.copy(None)
    # Ensure unique name for cloned scorecard to avoid IntegrityError
    new_scorecard.name = f"{CLONE_PREFIX}{original_task.name}_{datetime.datetime.now().timestamp()}"
    new_scorecard.save()

    new_task = NavigationTask.objects.create(
        name=original_task.name,
        contest=new_contest,
        route=new_route,
        original_scorecard=original_task.original_scorecard,
        scorecard=new_scorecard,
        editable_route=original_task.editable_route,
        start_time=original_task.start_time,
        finish_time=original_task.finish_time,
        is_public=False,
        is_featured=False,
        wind_speed=original_task.wind_speed,
        wind_direction=original_task.wind_direction,
        minutes_to_starting_point=original_task.minutes_to_starting_point,
        minutes_to_landing=original_task.minutes_to_landing,
        planning_time=original_task.planning_time,
    )

    new_scorecard.navigation_task_override = new_task
    new_scorecard.save()

    return new_task


def clone_contestant(original_contestant, new_task):
    logger.info(f"    Cloning contestant: {original_contestant}")
    new_contestant = Contestant.objects.create(
        team=original_contestant.team,
        navigation_task=new_task,
        adaptive_start=original_contestant.adaptive_start,
        takeoff_time=original_contestant.takeoff_time,
        minutes_to_starting_point=original_contestant.minutes_to_starting_point,
        finished_by_time=original_contestant.finished_by_time,
        air_speed=original_contestant.air_speed,
        contestant_number=original_contestant.contestant_number,
        tracking_service=original_contestant.tracking_service,
        tracking_device=original_contestant.tracking_device,
        tracker_device_id=original_contestant.tracker_device_id,
        tracker_start_time=original_contestant.tracker_start_time,
        wind_speed=original_contestant.wind_speed,
        wind_direction=original_contestant.wind_direction,
        predefined_gate_times=original_contestant.predefined_gate_times,
    )

    orig_positions = ContestantReceivedPosition.objects.filter(contestant=original_contestant).order_by("time")
    positions_to_create = []
    for pos in orig_positions:
        positions_to_create.append(
            ContestantReceivedPosition(
                contestant=new_contestant,
                time=pos.time,
                latitude=pos.latitude,
                longitude=pos.longitude,
                altitude=pos.altitude,
                speed=pos.speed,
                course=pos.course,
                battery_level=pos.battery_level,
                position_id=pos.position_id,
                device_id=pos.device_id,
                server_time=pos.server_time,
                interpolated=pos.interpolated,
            )
        )
    ContestantReceivedPosition.objects.bulk_create(positions_to_create)

    return new_contestant, orig_positions.filter(interpolated=False)


def run_recalculation(contestant, positions):
    logger.info(f"    Running recalculation for {contestant}...")
    q = RedisQueue(contestant.pk)
    while not q.empty():
        q.pop()

    for pos in positions:
        data = {
            "id": pos.position_id,
            "deviceId": pos.device_id,
            "attributes": {"course": pos.course, "batteryLevel": pos.battery_level},
            "device_time": pos.time,
            "latitude": pos.latitude,
            "longitude": pos.longitude,
            "altitude": pos.altitude,
            "speed": pos.speed,
            "time": pos.time.isoformat(),
            "server_time": pos.server_time,
        }
        q.append(data)
    q.append(None)

    processor = ContestantProcessor(contestant, live_processing=False)
    processor.run()


def compare_results(original, cloned):
    original.contestanttrack.refresh_from_db()
    cloned.contestanttrack.refresh_from_db()

    discrepancies = []

    if original.contestanttrack.score != cloned.contestanttrack.score:
        discrepancies.append(
            f"Score mismatch: Original={original.contestanttrack.score}, Cloned={cloned.contestanttrack.score}"
        )

    orig_entries = list(original.scorelogentry_set.all().order_by("time", "pk"))
    clone_entries = list(cloned.scorelogentry_set.all().order_by("time", "pk"))

    orig_strings = [e.string for e in orig_entries]
    clone_strings = [e.string for e in clone_entries]

    if orig_strings != clone_strings:
        diff = difflib.unified_diff(orig_strings, clone_strings, fromfile="original", tofile="cloned", lineterm="")
        discrepancies.append("Score log mismatch:\n" + "\n".join(list(diff)))

    return discrepancies


def main():
    delete_existing_clones()

    contests = Contest.objects.exclude(name__startswith=CLONE_PREFIX).order_by("-start_time")

    with open(REPORT_FILE, "w") as report:
        report.write(f"Recalculation Test Report - {datetime.datetime.now()}\n")
        report.write("=" * 50 + "\n\n")

        for contest in contests:
            tasks = NavigationTask.objects.filter(contest=contest, editable_route__isnull=False)
            if not tasks.exists():
                continue

            new_contest = clone_contest(contest)
            all_tasks_passed = True

            for task in tasks:
                if task.pk in IGNORE_TASKS:
                    logger.info(f"Skipping ignored task '{task.name}' (PK: {task.pk})")
                    continue

                new_task = clone_navigation_task(task, new_contest)
                all_contestants_passed = True

                # Filter to validate at least 3 contestants as requested (if available)
                contestants = task.contestant_set.all()
                if not contestants.exists():
                    route_id = new_task.route_id
                    new_task.delete()
                    if route_id:
                        Route.objects.filter(pk=route_id).delete()
                    continue

                for contestant in contestants:
                    if not contestant.scorelogentry_set.exists():
                        logger.info(f"    Skipping contestant {contestant} (empty score log)")
                        continue

                    new_contestant, positions = clone_contestant(contestant, new_task)

                    run_recalculation(new_contestant, positions)

                    discrepancies = compare_results(contestant, new_contestant)

                    if discrepancies:
                        print("\n" + "!" * 50)
                        print(f"DISCREPANCY FOUND")
                        print(f"Task: {task.name} (PK: {task.pk})")
                        print(f"Contestant: {contestant}")
                        for d in discrepancies:
                            print(d)
                        print(f"Original map: {get_tracking_link(contest.pk, task.pk)}")
                        print(f"Cloned map: {get_tracking_link(new_contest.pk, new_task.pk)}")
                        print("!" * 50 + "\n")

                        report.write(f"FAILURE: Task '{task.name}' (PK: {task.pk}), Contestant '{contestant}'\n")
                        report.write(f"  Original map: {get_tracking_link(contest.pk, task.pk)}\n")
                        report.write(f"  Cloned map: {get_tracking_link(new_contest.pk, new_task.pk)}\n")
                        for d in discrepancies:
                            report.write(f"  {d}\n")

                        logger.error("TERMINATING TEST DUE TO DISCREPANCY. Cloned objects kept for inspection.")
                        sys.exit(1)

                if all_contestants_passed:
                    msg = f"SUCCESS: Navigation Task '{task.name}' validated. Link: {get_tracking_link(contest.pk, task.pk)}"
                    logger.info(msg)
                    report.write(msg + "\n")
                else:
                    all_tasks_passed = False

                # Delete cloned task and its route
                route_id = new_task.route_id
                new_task.delete()
                if route_id:
                    Route.objects.filter(pk=route_id).delete()

            if all_tasks_passed:
                logger.info(f"Contest '{contest.name}' fully validated.")
                new_contest.delete()
            else:
                logger.warning(f"Contest '{contest.name}' had some failures.")


if __name__ == "__main__":
    main()
