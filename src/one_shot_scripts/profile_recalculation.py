import os
import sys
import datetime
import logging
import json
import difflib
import cProfile
import pstats
from io import StringIO
from django.db import transaction
from django.core.cache import cache

# Setup Django
sys.path.append("/workspace/src")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
import django
django.setup()

from display.models import (
    Contest, ContestTeam, NavigationTask, Contestant, 
    ContestantReceivedPosition, ScoreLogEntry, ContestantTrack,
    Route, Prohibited, Scorecard, Person, Crew, Team, Aeroplane
)
from display.calculators.contestant_processor import ContestantProcessor
from redis_queue import RedisQueue, RedisEmpty

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CLONE_PREFIX = "[PROFILE_TEST] "

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
    
    # Also cleanup scorecards
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
    )
    return new_contest

def clone_navigation_task(original_task, new_contest):
    new_route = original_task.route.create_copy()
    for prohibited in original_task.route.prohibited_set.all():
        prohibited.copy_to_new_route(new_route)
    
    timestamp = str(datetime.datetime.now().timestamp())
    new_scorecard = original_task.scorecard.copy(timestamp)
    new_scorecard.name = f"{CLONE_PREFIX}{original_task.name}_{timestamp}"
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

def clone_contestant(original_contestant, new_task, suffix_int=0):
    # Ensure unique contestant number for cloned task
    new_contestant = Contestant.objects.create(
        team=original_contestant.team,
        navigation_task=new_task,
        adaptive_start=original_contestant.adaptive_start,
        takeoff_time=original_contestant.takeoff_time,
        minutes_to_starting_point=original_contestant.minutes_to_starting_point,
        finished_by_time=original_contestant.finished_by_time,
        air_speed=original_contestant.air_speed,
        contestant_number=original_contestant.contestant_number + suffix_int * 100,
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
        positions_to_create.append(ContestantReceivedPosition(
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
        ))
    ContestantReceivedPosition.objects.bulk_create(positions_to_create)
    return new_contestant, orig_positions.filter(interpolated=False)

def run_recalculation(contestant, positions):
    q = RedisQueue(contestant.pk)
    while not q.empty():
        try:
            q.pop()
        except RedisEmpty:
            break
        
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
            "server_time": pos.server_time
        }
        q.append(data)
    q.append(None)
    
    processor = ContestantProcessor(contestant, live_processing=False, recalculate=True)
    processor.run()

def get_results(contestant):
    contestant.contestanttrack.refresh_from_db()
    entries = list(contestant.scorelogentry_set.all().order_by("time", "pk"))
    return {
        "score": contestant.contestanttrack.score,
        "log": [e.string for e in entries]
    }

def compare_two_results(res1, res2):
    discrepancies = []
    if res1["score"] != res2["score"]:
        discrepancies.append(f"Score mismatch: {res1['score']} vs {res2['score']}")
    
    if res1["log"] != res2["log"]:
        diff = difflib.unified_diff(res1["log"], res2["log"], fromfile='baseline', tofile='current', lineterm="")
        discrepancies.append("Score log mismatch:\n" + "\n".join(list(diff)))
        
    return discrepancies

def main():
    try:
        delete_existing_clones()
        
        # Target specific contest and task
        task_id = 3129
        contestant_id = 14349
        
        try:
            task = NavigationTask.objects.get(pk=task_id)
        except NavigationTask.DoesNotExist:
            logger.error(f"Task {task_id} not found")
            return

        original_contestant = Contestant.objects.get(pk=contestant_id)
        contestants = [original_contestant]

        new_contest = clone_contest(task.contest)
        new_task = clone_navigation_task(task, new_contest)

        baselines = []
        for i, original_contestant in enumerate(contestants):
            logger.info(f"Step 1: Establishing local baseline for contestant {i+1}/{len(contestants)}: {original_contestant}")
            # Use unique suffix for each clone to avoid duplication
            new_contestant, positions = clone_contestant(original_contestant, new_task, suffix_int=i+1)
            run_recalculation(new_contestant, positions)
            baselines.append({
                "contestant": original_contestant,
                "results": get_results(new_contestant),
                "positions": positions
            })
            logger.info(f"  Baseline score: {baselines[-1]['results']['score']}")

        logger.info("\n" + "="*50)
        logger.info("LOCAL BASELINES ESTABLISHED. Ready for validation.")
        logger.info("="*50 + "\n")
        
        # Profile the first contestant (run again on a new clone to be clean)
        logger.info(f"Profiling current code for {baselines[0]['contestant']} (LIVE PROCESSING)...")
        new_contestant_p, positions_p = clone_contestant(baselines[0]['contestant'], new_task, suffix_int=10)
        
        # Manually enable live processing for profiling
        q_p = RedisQueue(new_contestant_p.pk)
        while not q_p.empty():
            try:
                q_p.pop()
            except RedisEmpty:
                break
        for pos in positions_p:
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
                "server_time": pos.server_time
            }
            q_p.append(data)
        q_p.append(None)
        
        processor_p = ContestantProcessor(new_contestant_p, live_processing=True, recalculate=True)
        
        pr = cProfile.Profile()
        pr.enable()
        processor_p.run()
        pr.disable()
        s = StringIO()
        sortby = 'cumulative'
        ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
        ps.print_stats(30)
        profile_output = s.getvalue()

        # Step 2: Validation Step
        logger.info("Step 2: Validating against established baselines...")
        for i, baseline in enumerate(baselines):
            # Run again on a new clone
            new_contestant_v, positions_v = clone_contestant(baseline['contestant'], new_task, suffix_int=20+i)
            run_recalculation(new_contestant_v, positions_v)
            current_results = get_results(new_contestant_v)
            
            print(f"\nScore Log for {baseline['contestant']}:")
            for entry in current_results['log']:
                print(f"  {entry}")

            discrepancies = compare_two_results(baseline['results'], current_results)
            if discrepancies:
                print("\n" + "!"*50)
                print(f"VALIDATION FAILED for {baseline['contestant']}")
                for d in discrepancies:
                    print(d)
                print("!"*50 + "\n")
            else:
                logger.info(f"  VALIDATION SUCCESSFUL for {baseline['contestant']}")
        
        print("\nProfile for first contestant:")
        print(profile_output)

    finally:
        # delete_existing_clones()
        pass

if __name__ == "__main__":
    main()
