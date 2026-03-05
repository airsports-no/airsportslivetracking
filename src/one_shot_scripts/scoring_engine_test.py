import os
import sys
import datetime
import logging
import json
import difflib
import re
from django.db import transaction, models
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
STATE_FILE = "scoring_engine_test_state.json"
BASE_URL = "http://localhost:8002"
IGNORE_TASKS = [3108]
SKIP_FAI_ANR_2022 = True


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                if "ignored_task_ids" not in data:
                    data["ignored_task_ids"] = []
                return data
        except Exception:
            pass
    return {"remembered_id": None, "ignored_ids": [], "passed_ids": [], "ignored_task_ids": []}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def restart_script():
    logger.info("Restarting script to load new code...")
    os.execv(sys.executable, [sys.executable] + sys.argv)


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
    new_route = original_task.route.create_copy()
    for prohibited in original_task.route.prohibited_set.all():
        prohibited.copy_to_new_route(new_route)

    new_scorecard = original_task.scorecard.copy(str(datetime.datetime.now().timestamp()))
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


def get_side_by_side_diff(list1, list2):
    matcher = difflib.SequenceMatcher(None, list1, list2)
    out1, out2 = [], []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for i in range(i1, i2):
                out1.append(list1[i])
                out2.append(list2[j1 + (i - i1)])
        elif tag == "replace":
            max_len = max(i2 - i1, j2 - j1)
            for i in range(max_len):
                out1.append(list1[i1 + i] if i1 + i < i2 else "")
                out2.append(list2[j1 + i] if j1 + i < j2 else "")
        elif tag == "delete":
            for i in range(i1, i2):
                out1.append(list1[i])
                out2.append("")
        elif tag == "insert":
            for i in range(j1, j2):
                out1.append("")
                out2.append(list2[i])
    return out1, out2


def compare_results(original, cloned):
    original.contestanttrack.refresh_from_db()
    cloned.contestanttrack.refresh_from_db()

    discrepancies = []
    log_diff = None

    if abs(original.contestanttrack.score - cloned.contestanttrack.score) > 0.01:
        discrepancies.append(
            f"Score mismatch: Original={original.contestanttrack.score}, Cloned={cloned.contestanttrack.score}"
        )

    orig_entries = list(original.scorelogentry_set.all().order_by("time", "pk"))
    clone_entries = list(cloned.scorelogentry_set.all().order_by("time", "pk"))

    orig_strings = [re.sub(r"(\d+)\.0\b", r"\1", e.string) for e in orig_entries]
    clone_strings = [re.sub(r"(\d+)\.0\b", r"\1", e.string) for e in clone_entries]

    if orig_strings != clone_strings:
        log_diff = get_side_by_side_diff(orig_strings, clone_strings)
        discrepancies.append("Score log mismatch detected (see side-by-side view below)")

    return discrepancies, log_diff


def run_test_for_contestant(contestant, task, contest, state, is_remembered=False):
    if (contestant.pk in state["ignored_ids"] or task.pk in state["ignored_task_ids"]) and not is_remembered:
        return True

    new_contest = clone_contest(contest)
    new_task = clone_navigation_task(task, new_contest)
    new_contestant, positions = clone_contestant(contestant, new_task)

    run_recalculation(new_contestant, positions)
    discrepancies, log_diff = compare_results(contestant, new_contestant)

    passed = not discrepancies
    regression = False
    if not passed and contestant.pk in state["passed_ids"]:
        regression = True

    if discrepancies or is_remembered:
        if discrepancies:
            print("\n" + "!" * 120)
            print(f"DISCREPANCY FOUND {'(REGRESSION!)' if regression else ''}")
            print(f"Task: {task.name} (PK: {task.pk})")
            print(f"Contestant: {contestant} (PK: {contestant.pk})")
            for d in discrepancies:
                print(f" - {d}")
            
            if log_diff:
                print("\nSide-by-side Score Log (Original vs Cloned):")
                print("-" * 120)
                col_width = 58
                left_col, right_col = log_diff
                for l, r in zip(left_col, right_col):
                    l_norm = l.replace("\n", " ")
                    r_norm = r.replace("\n", " ")
                    marker = "  " if l == r else "!!"
                    # Truncate if too long for side-by-side
                    l_disp = (l_norm[:col_width-3] + "..") if len(l_norm) > col_width else l_norm
                    r_disp = (r_norm[:col_width-3] + "..") if len(r_norm) > col_width else r_norm
                    print(f"{l_disp:<{col_width}} {marker} {r_disp:<{col_width}}")
                print("-" * 120)
        else:
            print(f"\nReviewing remembered contestant: {contestant}")

        print(f"Original map: {get_tracking_link(contest.pk, task.pk)}")
        print(f"Cloned map: {get_tracking_link(new_contest.pk, new_task.pk)}")
        if discrepancies:
            print("!" * 120 + "\n")

        while True:
            prompt = "[C]ontinue, [I]gnore contestant, ignore [T]ask, [R]etry (restart), or [A]bort? "
            if is_remembered and not discrepancies:
                prompt = "Remembered contestant passed. [C]ontinue with full test or [R]etry? "
            
            choice = input(prompt).strip().lower()
            if choice == 'c':
                if passed and contestant.pk not in state["passed_ids"]:
                    state["passed_ids"].append(contestant.pk)
                break
            elif choice == 'i':
                if contestant.pk not in state["ignored_ids"]:
                    state["ignored_ids"].append(contestant.pk)
                save_state(state)
                break
            elif choice == 't':
                if task.pk not in state["ignored_task_ids"]:
                    state["ignored_task_ids"].append(task.pk)
                save_state(state)
                break
            elif choice == 'r':
                state["remembered_id"] = contestant.pk
                save_state(state)
                restart_script()
            elif choice == 'a':
                sys.exit(0)

    # Cleanup clones
    new_task.delete()
    if new_task.route_id:
        Route.objects.filter(pk=new_task.route_id).delete()
    new_contest.delete()
    
    if passed and contestant.pk not in state["passed_ids"]:
        state["passed_ids"].append(contestant.pk)
        save_state(state)

    return passed


def main():
    state = load_state()
    
    if state["remembered_id"]:
        remembered_id = state["remembered_id"]
        try:
            contestant = Contestant.objects.get(pk=remembered_id)
            task = contestant.navigation_task
            contest = task.contest
            logger.info(f"Running remembered contestant: {contestant}")
            state["remembered_id"] = None
            save_state(state)
            run_test_for_contestant(contestant, task, contest, state, is_remembered=True)
        except Contestant.DoesNotExist:
            logger.warning(f"Remembered contestant {remembered_id} no longer exists.")
            state["remembered_id"] = None
            save_state(state)

    delete_existing_clones()

    contests = Contest.objects.exclude(name__startswith=CLONE_PREFIX).order_by("-start_time")

    with open(REPORT_FILE, "w") as report:
        report.write(f"Recalculation Test Report - {datetime.datetime.now()}\n")
        report.write("=" * 50 + "\n\n")

        for contest in contests:
            tasks = NavigationTask.objects.filter(contest=contest, editable_route__isnull=False)
            if not tasks.exists():
                continue

            for task in tasks:
                if task.pk in IGNORE_TASKS or task.pk in state["ignored_task_ids"]:
                    logger.info(f"Skipping ignored task '{task.name}' (PK: {task.pk})")
                    continue

                if SKIP_FAI_ANR_2022 and task.original_scorecard and task.original_scorecard.name == "FAI ANR 2022":
                    logger.info(f"Skipping task '{task.name}' (PK: {task.pk}) using FAI ANR 2022 scorecard")
                    continue

                contestants = task.contestant_set.all()
                for contestant in contestants:
                    if not contestant.scorelogentry_set.exists():
                        continue

                    success = run_test_for_contestant(contestant, task, contest, state)
                    if success:
                        report.write(f"SUCCESS: {contestant} in {task.name}\n")
                    else:
                        report.write(f"FAILURE: {contestant} in {task.name}\n")

    logger.info("Test run complete.")


if __name__ == "__main__":
    main()
