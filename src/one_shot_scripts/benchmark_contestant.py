import os
import sys
import datetime
import logging
import json
import difflib
import re
import time
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
)
from display.calculators.contestant_processor import ContestantProcessor
from redis_queue import RedisQueue

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

CLONE_PREFIX = "[BENCHMARK] "


def delete_existing_clones():
    clones = Contest.objects.filter(name__startswith=CLONE_PREFIX)
    for clone in clones:
        tasks = NavigationTask.objects.filter(contest=clone)
        for task in tasks:
            route_id = task.route_id
            task.delete()
            if route_id:
                Route.objects.filter(pk=route_id).delete()
        clone.delete()
    Scorecard.objects.filter(name__startswith=CLONE_PREFIX).delete()


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


def run_benchmark(contestant, positions):
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

    processor = ContestantProcessor(contestant, live_processing=False, recalculate=True)

    start_time = time.perf_counter()
    processor.run()
    end_time = time.perf_counter()

    return end_time - start_time


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
        discrepancies.append("Score log mismatch detected")

    return discrepancies, log_diff


def main():
    # 13746
    if len(sys.argv) < 2:
        print("Usage: python3 benchmark_contestant.py <contestant_id>")
        sys.exit(1)

    contestant_id = int(sys.argv[1])
    try:
        original_contestant = Contestant.objects.get(pk=contestant_id)
    except Contestant.DoesNotExist:
        print(f"Contestant with PK {contestant_id} not found.")
        sys.exit(1)

    task = original_contestant.navigation_task
    contest = task.contest

    print(f"Benchmarking Contestant: {original_contestant} (PK: {contestant_id})")
    print(f"Task: {task.name} (PK: {task.pk})")
    print(f"Positions: {ContestantReceivedPosition.objects.filter(contestant=original_contestant).count()}")

    delete_existing_clones()

    new_contest = clone_contest(contest)
    new_task = clone_navigation_task(task, new_contest)
    new_contestant, positions = clone_contestant(original_contestant, new_task)

    print("Running calculator...")
    duration = run_benchmark(new_contestant, positions)
    print(f"\nExecution time: {duration:.4f} seconds")

    discrepancies, log_diff = compare_results(original_contestant, new_contestant)

    if discrepancies:
        print("\n" + "!" * 120)
        print("DISCREPANCY FOUND")
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
                l_disp = (l_norm[: col_width - 3] + "..") if len(l_norm) > col_width else l_norm
                r_disp = (r_norm[: col_width - 3] + "..") if len(r_norm) > col_width else r_norm
                print(f"{l_disp:<{col_width}} {marker} {r_disp:<{col_width}}")
            print("-" * 120)
        print("!" * 120 + "\n")
    else:
        print("\nSUCCESS: No scoring discrepancies detected.")

    # Cleanup
    new_task.delete()
    if new_task.route_id:
        Route.objects.filter(pk=new_task.route_id).delete()
    new_contest.delete()


if __name__ == "__main__":
    main()


"""
Run in refactor_calculators

5.7x improvement!!

Execution time: 20.7099 seconds

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
DISCREPANCY FOUND
 - Score mismatch: Original=2338.0, Cloned=2410.0
 - Score log mismatch detected

Side-by-side Score Log (Original vs Cloned):
------------------------------------------------------------------------------------------------------------------------
SP: 57 points passing gate (-21 s) planned: 17:55:00 ac..     SP: 57 points passing gate (-21 s) planned: 17:55:00 ac.. 
SP: 0 points exiting corridor                                 SP: 0 points exiting corridor                             
TP1: 200 points missing gate planned: 17:59:52 actual: --     TP1: 200 points missing gate planned: 17:59:52 actual: -- 
TP1: 0 points entering penalty zone odra zachód               TP1: 0 points entering penalty zone odra zachód           
TP1: 12 points inside penalty zone odra zachód (9s)           TP1: 12 points inside penalty zone odra zachód (9s)       
TP1: 87 points outside corridor (34 s)                        TP1: 87 points outside corridor (34 s)                    
TP 4: 0 points passing gate (no time check) (-16 s) pla..     TP 4: 0 points passing gate (no time check) (-16 s) pla.. 
TP1: 0 points exiting corridor                                TP1: 0 points exiting corridor                            
TP1: 12 points outside corridor (9 s)                         TP1: 12 points outside corridor (9 s)                     
TP 6: 0 points passing gate (no time check) (-15 s) pla..     TP 6: 0 points passing gate (no time check) (-15 s) pla.. 
TP 7: 0 points passing gate (no time check) (-16 s) pla..     TP 7: 0 points passing gate (no time check) (-16 s) pla.. 
TP 8: 0 points passing gate (no time check) (-16 s) pla..     TP 8: 0 points passing gate (no time check) (-16 s) pla.. 
TP 9: 0 points passing gate (no time check) (-15 s) pla..     TP 9: 0 points passing gate (no time check) (-15 s) pla.. 
TP 10: 0 points passing gate (no time check) (-15 s) pl..     TP 10: 0 points passing gate (no time check) (-15 s) pl.. 
TP1: 0 points exiting corridor                                TP1: 0 points exiting corridor                            
TP1: 18 points outside corridor (11 s)                        TP1: 18 points outside corridor (11 s)                    
TP 12: 0 points passing gate (no time check) (-16 s) pl..     TP 12: 0 points passing gate (no time check) (-16 s) pl.. 
TP 13: 0 points passing gate (no time check) (-17 s) pl..     TP 13: 0 points passing gate (no time check) (-17 s) pl.. 
TP 14: 0 points passing gate (no time check) (-17 s) pl..     TP 14: 0 points passing gate (no time check) (-17 s) pl.. 
TP 15: 0 points passing gate (no time check) (-18 s) pl..  !! TP 15: 0 points passing gate (no time check) (-17 s) pl.. 
NEW: 0 points passing gate (no time check) (-18 s) plan..     NEW: 0 points passing gate (no time check) (-18 s) plan.. 
TP 16: 0 points passing gate (no time check) (-19 s) pl..     TP 16: 0 points passing gate (no time check) (-19 s) pl.. 
TP1: 0 points exiting corridor                                TP1: 0 points exiting corridor                            
TP1: 0 points outside corridor (5 s)                       !! TP1: 0 points outside corridor (3 s)                      
TP 18: 0 points passing gate (no time check) (-24 s) pl..     TP 18: 0 points passing gate (no time check) (-24 s) pl.. 
TP1: 0 points exiting corridor                                TP1: 0 points exiting corridor                            
TP1: 0 points outside corridor (3 s)                          TP1: 0 points outside corridor (3 s)                      
TP1: 0 points exiting corridor                                TP1: 0 points exiting corridor                            
TP1: 0 points outside corridor (3 s)                       !! TP1: 0 points outside corridor (1 s)                      
NEW2: 0 points passing gate (no time check) (-30 s) pla..     NEW2: 0 points passing gate (no time check) (-30 s) pla.. 
TP 22: 0 points passing gate (no time check) (-31 s) pl..     TP 22: 0 points passing gate (no time check) (-31 s) pl.. 
TP 23: 0 points passing gate (no time check) (-31 s) pl..     TP 23: 0 points passing gate (no time check) (-31 s) pl.. 
TP 24: 0 points passing gate (no time check) (-32 s) pl..     TP 24: 0 points passing gate (no time check) (-32 s) pl.. 
TP 25: 0 points passing gate (no time check) (-32 s) pl..     TP 25: 0 points passing gate (no time check) (-32 s) pl.. 
TP 26: 0 points passing gate (no time check) (-33 s) pl..     TP 26: 0 points passing gate (no time check) (-33 s) pl.. 
TP 27: 0 points passing gate (no time check) (-34 s) pl..     TP 27: 0 points passing gate (no time check) (-34 s) pl.. 
NEW3: 0 points passing gate (no time check) (-35 s) pla..     NEW3: 0 points passing gate (no time check) (-35 s) pla.. 
TP 28: 0 points passing gate (no time check) (-35 s) pl..     TP 28: 0 points passing gate (no time check) (-35 s) pl.. 
TP1: 0 points exiting corridor                                TP1: 0 points exiting corridor                            
TP1: 0 points outside corridor (5 s)                          TP1: 0 points outside corridor (5 s)                      
TP 30: 0 points passing gate (no time check) (-37 s) pl..     TP 30: 0 points passing gate (no time check) (-37 s) pl.. 
NEW4: 0 points passing gate (no time check) (-39 s) pla..     NEW4: 0 points passing gate (no time check) (-39 s) pla.. 
TP 32: 0 points passing gate (no time check) (-39 s) pl..     TP 32: 0 points passing gate (no time check) (-39 s) pl.. 
TP 33: 0 points passing gate (no time check) (-41 s) pl..     TP 33: 0 points passing gate (no time check) (-41 s) pl.. 
TP1: 0 points exiting corridor                                TP1: 0 points exiting corridor                            
TP1: 0 points outside corridor (5 s)                       !! TP1: 0 points outside corridor (3 s)                      
TP 34: 0 points passing gate (no time check) (-45 s) pl..     TP 34: 0 points passing gate (no time check) (-45 s) pl.. 
NEW6: 0 points passing gate (no time check) (-47 s) pla..     NEW6: 0 points passing gate (no time check) (-47 s) pla.. 
TP 35: 0 points passing gate (no time check) (-47 s) pl..     TP 35: 0 points passing gate (no time check) (-47 s) pl.. 
NEW5: 0 points passing gate (no time check) (-49 s) pla..     NEW5: 0 points passing gate (no time check) (-49 s) pla.. 
TP 36: 0 points passing gate (no time check) (-49 s) pl..     TP 36: 0 points passing gate (no time check) (-49 s) pl.. 
TP 37: 0 points passing gate (no time check) (-45 s) pl..     TP 37: 0 points passing gate (no time check) (-45 s) pl.. 
TP 38: 0 points passing gate (no time check) (-42 s) pl..     TP 38: 0 points passing gate (no time check) (-42 s) pl.. 
TP2: 108 points passing gate (-38 s) planned: 18:07:31 ..     TP2: 108 points passing gate (-38 s) planned: 18:07:31 .. 
SC1: 0 points passing gate (-1 s) planned: 18:08:35 act..     SC1: 0 points passing gate (-1 s) planned: 18:08:35 act.. 
TP3: 0 points passing gate (no time check) (+16 s) plan..  !! TP3: 42 points passing gate (+16 s) planned: 18:09:27 a.. 
TP 41: 0 points passing gate (no time check) (+17 s) pl..     TP 41: 0 points passing gate (no time check) (+17 s) pl.. 
TP 42: 0 points passing gate (no time check) (+17 s) pl..     TP 42: 0 points passing gate (no time check) (+17 s) pl.. 
TP 43: 0 points passing gate (no time check) (+16 s) pl..     TP 43: 0 points passing gate (no time check) (+16 s) pl.. 
TP 44: 0 points passing gate (no time check) (+16 s) pl..     TP 44: 0 points passing gate (no time check) (+16 s) pl.. 
TP 45: 0 points passing gate (no time check) (+15 s) pl..     TP 45: 0 points passing gate (no time check) (+15 s) pl.. 
TP 46: 0 points passing gate (no time check) (+16 s) pl..     TP 46: 0 points passing gate (no time check) (+16 s) pl.. 
TP 47: 0 points passing gate (no time check) (+17 s) pl..     TP 47: 0 points passing gate (no time check) (+17 s) pl.. 
SC2: 0 points passing gate (+18 s) planned: 18:10:53 ac..  !! SC2: 0 points passing gate (no time check) (+18 s) plan.. 
TP 49: 0 points passing gate (no time check) (+18 s) pl..     TP 49: 0 points passing gate (no time check) (+18 s) pl.. 
TP 50: 0 points passing gate (no time check) (+18 s) pl..     TP 50: 0 points passing gate (no time check) (+18 s) pl.. 
TP 51: 0 points passing gate (no time check) (+19 s) pl..     TP 51: 0 points passing gate (no time check) (+19 s) pl.. 
TP 52: 0 points passing gate (no time check) (+20 s) pl..     TP 52: 0 points passing gate (no time check) (+20 s) pl.. 
SC3: 0 points passing gate (+21 s) planned: 18:11:49 ac..  !! SC3: 0 points passing gate (no time check) (+21 s) plan.. 
TP 54: 0 points passing gate (no time check) (+21 s) pl..     TP 54: 0 points passing gate (no time check) (+21 s) pl.. 
TP 55: 0 points passing gate (no time check) (+21 s) pl..     TP 55: 0 points passing gate (no time check) (+21 s) pl.. 
TP 56: 0 points passing gate (no time check) (+21 s) pl..     TP 56: 0 points passing gate (no time check) (+21 s) pl.. 
TP 57: 0 points passing gate (no time check) (+22 s) pl..     TP 57: 0 points passing gate (no time check) (+22 s) pl.. 
TP 58: 0 points passing gate (no time check) (+22 s) pl..     TP 58: 0 points passing gate (no time check) (+22 s) pl.. 
TP2: 0 points exiting corridor                             !! TP3: 0 points exiting corridor                            
TP2: 0 points outside corridor (4 s)                       !! TP3: 0 points outside corridor (2 s)                      
TP 59: 0 points passing gate (no time check) (+21 s) pl..     TP 59: 0 points passing gate (no time check) (+21 s) pl.. 
TP 60: 0 points passing gate (no time check) (+23 s) pl..     TP 60: 0 points passing gate (no time check) (+23 s) pl.. 
TP4: 66 points passing gate (+24 s) planned: 18:13:32 a..     TP4: 66 points passing gate (+24 s) planned: 18:13:32 a.. 
TP5: 93 points passing gate (+33 s) planned: 18:15:19 a..     TP5: 93 points passing gate (+33 s) planned: 18:15:19 a.. 
TP 63: 0 points passing gate (no time check) (+33 s) pl..     TP 63: 0 points passing gate (no time check) (+33 s) pl.. 
TP 64: 0 points passing gate (no time check) (+34 s) pl..     TP 64: 0 points passing gate (no time check) (+34 s) pl.. 
TP 65: 0 points passing gate (no time check) (+37 s) pl..     TP 65: 0 points passing gate (no time check) (+37 s) pl.. 
TP 66: 0 points passing gate (no time check) (+38 s) pl..     TP 66: 0 points passing gate (no time check) (+38 s) pl.. 
TP 67: 0 points passing gate (no time check) (+39 s) pl..     TP 67: 0 points passing gate (no time check) (+39 s) pl.. 
TP 68: 0 points passing gate (+41 s) planned: 18:16:43 ..  !! TP 68: 0 points passing gate (no time check) (+41 s) pl.. 
TP 69: 0 points passing gate (no time check) (+43 s) pl..     TP 69: 0 points passing gate (no time check) (+43 s) pl.. 
TP5: 0 points exiting corridor                                TP5: 0 points exiting corridor                            
TP5: 0 points outside corridor (2 s)                       !! TP5: 0 points outside corridor (3 s)                      
TP 70: 0 points passing gate (no time check) (+45 s) pl..     TP 70: 0 points passing gate (no time check) (+45 s) pl.. 
TP 71: 0 points passing gate (no time check) (+47 s) pl..     TP 71: 0 points passing gate (no time check) (+47 s) pl.. 
TP 72: 0 points passing gate (no time check) (+47 s) pl..     TP 72: 0 points passing gate (no time check) (+47 s) pl.. 
TP 73: 0 points passing gate (+45 s) planned: 18:17:40 ..  !! TP 73: 0 points passing gate (no time check) (+45 s) pl.. 
TP 74: 0 points passing gate (no time check) (+45 s) pl..     TP 74: 0 points passing gate (no time check) (+45 s) pl.. 
TP 75: 0 points passing gate (no time check) (+46 s) pl..     TP 75: 0 points passing gate (no time check) (+46 s) pl.. 
TP5: 0 points exiting corridor                                TP5: 0 points exiting corridor                            
TP5: 0 points entering penalty zone S3                        TP5: 0 points entering penalty zone S3                    
TP6: 200 points missing gate planned: 18:18:31 actual: --     TP6: 200 points missing gate planned: 18:18:31 actual: -- 
TP6: 30 points inside penalty zone S3 (15s)                   TP6: 30 points inside penalty zone S3 (15s)               
TP6: 156 points outside corridor (57 s)                    !! TP6: 147 points outside corridor (54 s)                   
TP7: 165 points passing gate (+57 s) planned: 18:20:32 ..     TP7: 165 points passing gate (+57 s) planned: 18:20:32 .. 
SC7: 0 points passing gate (+67 s) planned: 18:21:03 ac..     SC7: 0 points passing gate (+67 s) planned: 18:21:03 ac.. 
TP7: 0 points exiting corridor                                TP7: 0 points exiting corridor                            
TP7: 96 points outside corridor (37 s)                        TP7: 96 points outside corridor (37 s)                    
SC8: 0 points passing gate (+83 s) planned: 18:22:24 ac..     SC8: 0 points passing gate (+83 s) planned: 18:22:24 ac.. 
TP7: 0 points exiting corridor                                TP7: 0 points exiting corridor                            
TP8: 200 points missing gate planned: 18:22:54 actual: --     TP8: 200 points missing gate planned: 18:22:54 actual: -- 
TP8: 174 points outside corridor (63 s)                    !! TP8: 186 points outside corridor (67 s)                   
SC9: 0 points passing gate (+95 s) planned: 18:24:31 ac..     SC9: 0 points passing gate (+95 s) planned: 18:24:31 ac.. 
TP8: 0 points exiting corridor                                TP8: 0 points exiting corridor                            
TP9: 200 points missing gate planned: 18:25:23 actual: --     TP9: 200 points missing gate planned: 18:25:23 actual: -- 
SC10: 0 points missing gate planned: 18:25:54 actual: --      SC10: 0 points missing gate planned: 18:25:54 actual: --  
SC11: 0 points missing gate planned: 18:26:18 actual: --      SC11: 0 points missing gate planned: 18:26:18 actual: --  
TP9: 264 points outside corridor (93 s)                    !! TP9: 276 points outside corridor (97 s)                   
TP10: 0 points passing gate (no time check) (+122 s) pl..     TP10: 0 points passing gate (no time check) (+122 s) pl.. 
                                                           !! TP9: 0 points exiting corridor                            
                                                           !! TP9: 15 points outside corridor (10 s)                    
FP: 200 points passing gate (+105 s) planned: 18:28:45 ..     FP: 200 points passing gate (+105 s) planned: 18:28:45 .. 
"""

"""
Run in main

Execution time: 114.2941 seconds

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
DISCREPANCY FOUND
 - Score mismatch: Original=2338.0, Cloned=2410.0
 - Score log mismatch detected

Side-by-side Score Log (Original vs Cloned):
------------------------------------------------------------------------------------------------------------------------
SP: 57 points passing gate (-21 s) planned: 17:55:00 ac..     SP: 57 points passing gate (-21 s) planned: 17:55:00 ac.. 
SP: 0 points exiting corridor                                 SP: 0 points exiting corridor                             
TP1: 200 points missing gate planned: 17:59:52 actual: --     TP1: 200 points missing gate planned: 17:59:52 actual: -- 
TP1: 0 points entering penalty zone odra zachód               TP1: 0 points entering penalty zone odra zachód           
TP1: 12 points inside penalty zone odra zachód (9s)           TP1: 12 points inside penalty zone odra zachód (9s)       
TP1: 87 points outside corridor (34 s)                        TP1: 87 points outside corridor (34 s)                    
TP 4: 0 points passing gate (no time check) (-16 s) pla..     TP 4: 0 points passing gate (no time check) (-16 s) pla.. 
TP1: 0 points exiting corridor                                TP1: 0 points exiting corridor                            
TP1: 12 points outside corridor (9 s)                         TP1: 12 points outside corridor (9 s)                     
TP 6: 0 points passing gate (no time check) (-15 s) pla..     TP 6: 0 points passing gate (no time check) (-15 s) pla.. 
TP 7: 0 points passing gate (no time check) (-16 s) pla..     TP 7: 0 points passing gate (no time check) (-16 s) pla.. 
TP 8: 0 points passing gate (no time check) (-16 s) pla..     TP 8: 0 points passing gate (no time check) (-16 s) pla.. 
TP 9: 0 points passing gate (no time check) (-15 s) pla..     TP 9: 0 points passing gate (no time check) (-15 s) pla.. 
TP 10: 0 points passing gate (no time check) (-15 s) pl..     TP 10: 0 points passing gate (no time check) (-15 s) pl.. 
TP1: 0 points exiting corridor                                TP1: 0 points exiting corridor                            
TP1: 18 points outside corridor (11 s)                        TP1: 18 points outside corridor (11 s)                    
TP 12: 0 points passing gate (no time check) (-16 s) pl..     TP 12: 0 points passing gate (no time check) (-16 s) pl.. 
TP 13: 0 points passing gate (no time check) (-17 s) pl..     TP 13: 0 points passing gate (no time check) (-17 s) pl.. 
TP 14: 0 points passing gate (no time check) (-17 s) pl..     TP 14: 0 points passing gate (no time check) (-17 s) pl.. 
TP 15: 0 points passing gate (no time check) (-18 s) pl..  !! TP 15: 0 points passing gate (no time check) (-17 s) pl.. 
NEW: 0 points passing gate (no time check) (-18 s) plan..     NEW: 0 points passing gate (no time check) (-18 s) plan.. 
TP 16: 0 points passing gate (no time check) (-19 s) pl..     TP 16: 0 points passing gate (no time check) (-19 s) pl.. 
TP1: 0 points exiting corridor                                TP1: 0 points exiting corridor                            
TP1: 0 points outside corridor (5 s)                       !! TP1: 0 points outside corridor (3 s)                      
TP 18: 0 points passing gate (no time check) (-24 s) pl..     TP 18: 0 points passing gate (no time check) (-24 s) pl.. 
TP1: 0 points exiting corridor                                TP1: 0 points exiting corridor                            
TP1: 0 points outside corridor (3 s)                          TP1: 0 points outside corridor (3 s)                      
TP1: 0 points exiting corridor                                TP1: 0 points exiting corridor                            
TP1: 0 points outside corridor (3 s)                       !! TP1: 0 points outside corridor (1 s)                      
NEW2: 0 points passing gate (no time check) (-30 s) pla..     NEW2: 0 points passing gate (no time check) (-30 s) pla.. 
TP 22: 0 points passing gate (no time check) (-31 s) pl..     TP 22: 0 points passing gate (no time check) (-31 s) pl.. 
TP 23: 0 points passing gate (no time check) (-31 s) pl..     TP 23: 0 points passing gate (no time check) (-31 s) pl.. 
TP 24: 0 points passing gate (no time check) (-32 s) pl..     TP 24: 0 points passing gate (no time check) (-32 s) pl.. 
TP 25: 0 points passing gate (no time check) (-32 s) pl..     TP 25: 0 points passing gate (no time check) (-32 s) pl.. 
TP 26: 0 points passing gate (no time check) (-33 s) pl..     TP 26: 0 points passing gate (no time check) (-33 s) pl.. 
TP 27: 0 points passing gate (no time check) (-34 s) pl..     TP 27: 0 points passing gate (no time check) (-34 s) pl.. 
NEW3: 0 points passing gate (no time check) (-35 s) pla..     NEW3: 0 points passing gate (no time check) (-35 s) pla.. 
TP 28: 0 points passing gate (no time check) (-35 s) pl..     TP 28: 0 points passing gate (no time check) (-35 s) pl.. 
TP1: 0 points exiting corridor                                TP1: 0 points exiting corridor                            
TP1: 0 points outside corridor (5 s)                          TP1: 0 points outside corridor (5 s)                      
TP 30: 0 points passing gate (no time check) (-37 s) pl..     TP 30: 0 points passing gate (no time check) (-37 s) pl.. 
NEW4: 0 points passing gate (no time check) (-39 s) pla..     NEW4: 0 points passing gate (no time check) (-39 s) pla.. 
TP 32: 0 points passing gate (no time check) (-39 s) pl..     TP 32: 0 points passing gate (no time check) (-39 s) pl.. 
TP 33: 0 points passing gate (no time check) (-41 s) pl..     TP 33: 0 points passing gate (no time check) (-41 s) pl.. 
TP1: 0 points exiting corridor                                TP1: 0 points exiting corridor                            
TP1: 0 points outside corridor (5 s)                       !! TP1: 0 points outside corridor (3 s)                      
TP 34: 0 points passing gate (no time check) (-45 s) pl..     TP 34: 0 points passing gate (no time check) (-45 s) pl.. 
NEW6: 0 points passing gate (no time check) (-47 s) pla..     NEW6: 0 points passing gate (no time check) (-47 s) pla.. 
TP 35: 0 points passing gate (no time check) (-47 s) pl..     TP 35: 0 points passing gate (no time check) (-47 s) pl.. 
NEW5: 0 points passing gate (no time check) (-49 s) pla..     NEW5: 0 points passing gate (no time check) (-49 s) pla.. 
TP 36: 0 points passing gate (no time check) (-49 s) pl..     TP 36: 0 points passing gate (no time check) (-49 s) pl.. 
TP 37: 0 points passing gate (no time check) (-45 s) pl..     TP 37: 0 points passing gate (no time check) (-45 s) pl.. 
TP 38: 0 points passing gate (no time check) (-42 s) pl..     TP 38: 0 points passing gate (no time check) (-42 s) pl.. 
TP2: 108 points passing gate (-38 s) planned: 18:07:31 ..     TP2: 108 points passing gate (-38 s) planned: 18:07:31 .. 
SC1: 0 points passing gate (-1 s) planned: 18:08:35 act..     SC1: 0 points passing gate (-1 s) planned: 18:08:35 act.. 
TP3: 0 points passing gate (no time check) (+16 s) plan..  !! TP3: 42 points passing gate (+16 s) planned: 18:09:27 a.. 
TP 41: 0 points passing gate (no time check) (+17 s) pl..     TP 41: 0 points passing gate (no time check) (+17 s) pl.. 
TP 42: 0 points passing gate (no time check) (+17 s) pl..     TP 42: 0 points passing gate (no time check) (+17 s) pl.. 
TP 43: 0 points passing gate (no time check) (+16 s) pl..     TP 43: 0 points passing gate (no time check) (+16 s) pl.. 
TP 44: 0 points passing gate (no time check) (+16 s) pl..     TP 44: 0 points passing gate (no time check) (+16 s) pl.. 
TP 45: 0 points passing gate (no time check) (+15 s) pl..     TP 45: 0 points passing gate (no time check) (+15 s) pl.. 
TP 46: 0 points passing gate (no time check) (+16 s) pl..     TP 46: 0 points passing gate (no time check) (+16 s) pl.. 
TP 47: 0 points passing gate (no time check) (+17 s) pl..     TP 47: 0 points passing gate (no time check) (+17 s) pl.. 
SC2: 0 points passing gate (+18 s) planned: 18:10:53 ac..  !! SC2: 0 points passing gate (no time check) (+18 s) plan.. 
TP 49: 0 points passing gate (no time check) (+18 s) pl..     TP 49: 0 points passing gate (no time check) (+18 s) pl.. 
TP 50: 0 points passing gate (no time check) (+18 s) pl..     TP 50: 0 points passing gate (no time check) (+18 s) pl.. 
TP 51: 0 points passing gate (no time check) (+19 s) pl..     TP 51: 0 points passing gate (no time check) (+19 s) pl.. 
TP 52: 0 points passing gate (no time check) (+20 s) pl..     TP 52: 0 points passing gate (no time check) (+20 s) pl.. 
SC3: 0 points passing gate (+21 s) planned: 18:11:49 ac..  !! SC3: 0 points passing gate (no time check) (+21 s) plan.. 
TP 54: 0 points passing gate (no time check) (+21 s) pl..     TP 54: 0 points passing gate (no time check) (+21 s) pl.. 
TP 55: 0 points passing gate (no time check) (+21 s) pl..     TP 55: 0 points passing gate (no time check) (+21 s) pl.. 
TP 56: 0 points passing gate (no time check) (+21 s) pl..     TP 56: 0 points passing gate (no time check) (+21 s) pl.. 
TP 57: 0 points passing gate (no time check) (+22 s) pl..     TP 57: 0 points passing gate (no time check) (+22 s) pl.. 
TP 58: 0 points passing gate (no time check) (+22 s) pl..     TP 58: 0 points passing gate (no time check) (+22 s) pl.. 
TP2: 0 points exiting corridor                             !! TP3: 0 points exiting corridor                            
TP2: 0 points outside corridor (4 s)                       !! TP3: 0 points outside corridor (2 s)                      
TP 59: 0 points passing gate (no time check) (+21 s) pl..     TP 59: 0 points passing gate (no time check) (+21 s) pl.. 
TP 60: 0 points passing gate (no time check) (+23 s) pl..     TP 60: 0 points passing gate (no time check) (+23 s) pl.. 
TP4: 66 points passing gate (+24 s) planned: 18:13:32 a..     TP4: 66 points passing gate (+24 s) planned: 18:13:32 a.. 
TP5: 93 points passing gate (+33 s) planned: 18:15:19 a..     TP5: 93 points passing gate (+33 s) planned: 18:15:19 a.. 
TP 63: 0 points passing gate (no time check) (+33 s) pl..     TP 63: 0 points passing gate (no time check) (+33 s) pl.. 
TP 64: 0 points passing gate (no time check) (+34 s) pl..     TP 64: 0 points passing gate (no time check) (+34 s) pl.. 
TP 65: 0 points passing gate (no time check) (+37 s) pl..     TP 65: 0 points passing gate (no time check) (+37 s) pl.. 
TP 66: 0 points passing gate (no time check) (+38 s) pl..     TP 66: 0 points passing gate (no time check) (+38 s) pl.. 
TP 67: 0 points passing gate (no time check) (+39 s) pl..     TP 67: 0 points passing gate (no time check) (+39 s) pl.. 
TP 68: 0 points passing gate (+41 s) planned: 18:16:43 ..  !! TP 68: 0 points passing gate (no time check) (+41 s) pl.. 
TP 69: 0 points passing gate (no time check) (+43 s) pl..     TP 69: 0 points passing gate (no time check) (+43 s) pl.. 
TP5: 0 points exiting corridor                                TP5: 0 points exiting corridor                            
TP5: 0 points outside corridor (2 s)                       !! TP5: 0 points outside corridor (3 s)                      
TP 70: 0 points passing gate (no time check) (+45 s) pl..     TP 70: 0 points passing gate (no time check) (+45 s) pl.. 
TP 71: 0 points passing gate (no time check) (+47 s) pl..     TP 71: 0 points passing gate (no time check) (+47 s) pl.. 
TP 72: 0 points passing gate (no time check) (+47 s) pl..     TP 72: 0 points passing gate (no time check) (+47 s) pl.. 
TP 73: 0 points passing gate (+45 s) planned: 18:17:40 ..  !! TP 73: 0 points passing gate (no time check) (+45 s) pl.. 
TP 74: 0 points passing gate (no time check) (+45 s) pl..     TP 74: 0 points passing gate (no time check) (+45 s) pl.. 
TP 75: 0 points passing gate (no time check) (+46 s) pl..     TP 75: 0 points passing gate (no time check) (+46 s) pl.. 
TP5: 0 points exiting corridor                                TP5: 0 points exiting corridor                            
TP5: 0 points entering penalty zone S3                        TP5: 0 points entering penalty zone S3                    
TP6: 200 points missing gate planned: 18:18:31 actual: --     TP6: 200 points missing gate planned: 18:18:31 actual: -- 
TP6: 30 points inside penalty zone S3 (15s)                   TP6: 30 points inside penalty zone S3 (15s)               
TP6: 156 points outside corridor (57 s)                    !! TP6: 147 points outside corridor (54 s)                   
TP7: 165 points passing gate (+57 s) planned: 18:20:32 ..     TP7: 165 points passing gate (+57 s) planned: 18:20:32 .. 
SC7: 0 points passing gate (+67 s) planned: 18:21:03 ac..     SC7: 0 points passing gate (+67 s) planned: 18:21:03 ac.. 
TP7: 0 points exiting corridor                                TP7: 0 points exiting corridor                            
TP7: 96 points outside corridor (37 s)                        TP7: 96 points outside corridor (37 s)                    
SC8: 0 points passing gate (+83 s) planned: 18:22:24 ac..     SC8: 0 points passing gate (+83 s) planned: 18:22:24 ac.. 
TP7: 0 points exiting corridor                                TP7: 0 points exiting corridor                            
TP8: 200 points missing gate planned: 18:22:54 actual: --     TP8: 200 points missing gate planned: 18:22:54 actual: -- 
TP8: 174 points outside corridor (63 s)                    !! TP8: 186 points outside corridor (67 s)                   
SC9: 0 points passing gate (+95 s) planned: 18:24:31 ac..     SC9: 0 points passing gate (+95 s) planned: 18:24:31 ac.. 
TP8: 0 points exiting corridor                                TP8: 0 points exiting corridor                            
TP9: 200 points missing gate planned: 18:25:23 actual: --     TP9: 200 points missing gate planned: 18:25:23 actual: -- 
SC10: 0 points missing gate planned: 18:25:54 actual: --      SC10: 0 points missing gate planned: 18:25:54 actual: --  
SC11: 0 points missing gate planned: 18:26:18 actual: --      SC11: 0 points missing gate planned: 18:26:18 actual: --  
TP9: 264 points outside corridor (93 s)                    !! TP9: 276 points outside corridor (97 s)                   
TP10: 0 points passing gate (no time check) (+122 s) pl..     TP10: 0 points passing gate (no time check) (+122 s) pl.. 
                                                           !! TP9: 0 points exiting corridor                            
                                                           !! TP9: 15 points outside corridor (10 s)                    
FP: 200 points passing gate (+105 s) planned: 18:28:45 ..     FP: 200 points passing gate (+105 s) planned: 18:28:45 .. 
------------------------------------------------------------------------------------------------------------------------
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

"""
