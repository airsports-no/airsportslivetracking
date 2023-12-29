import argparse
import datetime
import logging
import os
import random
import sys
import threading
import time
from typing import Tuple, List
from urllib.parse import urlencode

import requests


if __name__ == "__main__":
    sys.path.append("../")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()

from traccar_facade import Traccar

from display.models import (
    Crew,
    Team,
    Contest,
    Aeroplane,
    NavigationTask,
    Contestant,
    Person,
    ContestTeam,
    TRACCAR,
    Club,
    TRACKING_PILOT,
    ContestantReceivedPosition,
)

logger = logging.getLogger(__name__)

# server = "traccar.airsports.no"
TRACCAR_HOST = os.environ.get("TRACCAR_HOST", "traccar")
server = f"{TRACCAR_HOST}:5055"

arguments = None

if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        "navigation_task_id", type=int, help="ID of an existing navigation  task to model the test on"
    )
    argparser.add_argument("number_of_contestants", type=int, help="The number of contestants to create")
    argparser.add_argument(
        "-i",
        "--start_interval_seconds",
        type=int,
        default=60,
        action="store",
        help="The time (in seconds) between each contestant start",
    )
    argparser.add_argument(
        "-p",
        "--pause",
        type=float,
        action="store",
        default=0,
        help="Pause data transmission for 60 seconds this amount of minutes after start",
    )
    argparser.add_argument(
        "-r",
        "--random_pause",
        action="store_true",
        default=False,
        help="Introduce random delays during the playback",
    )
    arguments = argparser.parse_args()

    traccar = Traccar.create_from_configuration()

    traccar.get_device_map()


def send(id, timestamp, lat, lon, speed):
    params = (("id", id), ("timestamp", int(timestamp)), ("lat", lat), ("lon", lon), ("speed", speed))
    requests.post("http://" + server + "/?" + urlencode(params))


def send_data_thread(contestant, positions):
    logger.info(f"Started sending positions for {contestant}")
    start_time = datetime.datetime.now(datetime.timezone.utc)
    have_paused = False
    while len(positions) > 0:
        while len(positions) > 0 and (positions[0]["device_time"] < datetime.datetime.now(datetime.timezone.utc)):
            if (
                arguments.pause > 0
                and not have_paused
                and datetime.datetime.now(datetime.timezone.utc)
                > start_time + datetime.timedelta(minutes=arguments.pause)
            ):
                logger.info(f"Pausing contestant {contestant} for sixty seconds.")
                have_paused = True
                time.sleep(arguments.pause * 60)
                logger.info(f"Resuming contestant {contestant}.")
            if arguments.random_pause and random.randint(0, 1800) == 0:  # Approximately once every half hour
                pause = random.randint(10, 120)
                logger.info(f"Pausing contestant {contestant} for {pause} seconds.")
                time.sleep(pause)
                logger.info(f"Resuming contestant {contestant}.")

            data = positions.pop(0)
            send(
                contestant.team.crew.member1.simulator_tracking_id,
                time.mktime(data["device_time"].timetuple()),
                data["latitude"],
                data["longitude"],
                data["speed"],
            )
        time.sleep(1)
    contestant.blocking_request_calculator_termination()
    logger.info(f"Completed sending positions for {contestant}")


def load_data_traccar(tracks: List[Tuple[Contestant, List[dict]]], real_time: bool = True):
    for contestant, positions in tracks:
        threading.Thread(target=send_data_thread, args=(contestant, positions)).start()


def get_retimed_track(start_time, old_contestant: Contestant) -> List[dict]:
    # existing_track = old_contestant.get_traccar_track()
    existing_track = [
        p.to_traccar(old_contestant.tracker_device_id, index) for index, p in enumerate(old_contestant.get_track())
    ]
    expected_starting_point_time = old_contestant.starting_point_time
    # Assumes start time is in the future, after expected starting point time
    time_difference = start_time - expected_starting_point_time
    for item in existing_track:
        item["device_time"] += time_difference

    return [item for item in existing_track if item["device_time"] > start_time - datetime.timedelta(minutes=1)]


def create_contestants(
    old_navigation_task: NavigationTask,
    new_navigation_task: NavigationTask,
    number_of_contestants: int,
    start_interval: datetime.timedelta,
) -> List[Tuple[Contestant, List[dict]]]:
    logger.info(f"Creating {number_of_contestants} contestants with start interval {start_interval}")
    created_contestants = []
    current_contestant_index = 0
    existing_contestants = list(old_navigation_task.contestant_set.all())
    if len(existing_contestants) == 0:
        logger.error(f"There are no contestants to copy")
        return []
    logger.info(f"Creating based on {len(existing_contestants)} existing contestants")
    existing_contestant_index = 0
    start_time = datetime.datetime.now(datetime.timezone.utc)
    finish_time = start_time + datetime.timedelta(hours=4)
    while current_contestant_index < number_of_contestants:
        logger.info(f"Creating contestant number {current_contestant_index}")
        current_old_contestant = existing_contestants[existing_contestant_index]
        contestant_email = f"test{current_contestant_index}@internal.contestant com"
        person, _ = Person.objects.get_or_create(
            email=contestant_email,
            defaults={"first_name": "Test", "last_name": f"Person {current_contestant_index}"},
        )
        traccar.delete_device(traccar.unique_id_map.get(person.simulator_tracking_id))
        traccar.create_device(person.first_name, person.simulator_tracking_id)
        crew, _ = Crew.objects.get_or_create(member1=person)
        aeroplane, _ = Aeroplane.objects.get_or_create(registration=f"LN-X{current_contestant_index}")
        team, _ = Team.objects.get_or_create(
            crew=crew, aeroplane=aeroplane, club=Club.objects.get_or_create(name="Airsports test")[0]
        )
        ContestTeam.objects.get_or_create(
            team=team,
            contest=new_navigation_task.contest,
            defaults={
                "air_speed": current_old_contestant.air_speed,
                "tracking_service": TRACCAR,
                "tracker_device_id": contestant_email,
            },
        )
        contestant_object = Contestant.objects.create(
            navigation_task=new_navigation_task,
            team=team,
            takeoff_time=start_time,
            finished_by_time=finish_time,
            tracker_start_time=start_time,
            tracker_device_id=contestant_email,
            contestant_number=current_contestant_index,
            minutes_to_starting_point=5,
            air_speed=current_old_contestant.air_speed,
            tracking_device=TRACKING_PILOT,
            wind_direction=current_old_contestant.wind_direction,
            wind_speed=current_old_contestant.wind_speed,
            adaptive_start=True,
        )
        created_contestants.append(
            (
                contestant_object,
                get_retimed_track(start_time + current_contestant_index * start_interval, current_old_contestant),
            )
        )
        current_contestant_index += 1
        existing_contestant_index += 1
        existing_contestant_index %= len(existing_contestants)
    return created_contestants


if __name__ == "__main__":
    navigation_task = NavigationTask.objects.get(pk=arguments.navigation_task_id)
    logger.info(
        f"Creating scaling test from task {navigation_task} with {arguments.number_of_contestants} created from {navigation_task.contestant_set.all().count()} existing contestants spaced by {datetime.timedelta(seconds=arguments.start_interval_seconds)}"
    )
    new_navigation_task_name = f"{navigation_task.name} scaling test"
    start_time = datetime.datetime.today().replace(tzinfo=datetime.timezone.utc)
    finish_time = datetime.datetime.today().replace(tzinfo=datetime.timezone.utc) + datetime.timedelta(days=1)
    contest, _ = Contest.objects.get_or_create(
        name="Scaling test contest",
        defaults={
            "is_public": False,
            "start_time": start_time,
            "finish_time": finish_time,
        },
    )
    contest.time_zone = navigation_task.contest.time_zone
    contest.save()
    contest.navigationtask_set.filter(name=new_navigation_task_name).delete()
    new_navigation_task = NavigationTask.create(
        name=new_navigation_task_name,
        contest=contest,
        route=navigation_task.route.create_copy(),
        original_scorecard=navigation_task.original_scorecard,
        start_time=start_time,
        finish_time=finish_time,
        is_public=False,
    )
    for prohibited in navigation_task.route.prohibited_set.all():
        prohibited.copy_to_new_route(new_navigation_task.route)
    new_navigation_task.scorecard = navigation_task.scorecard.copy(new_navigation_task.pk)
    new_navigation_task.save()

    new_contestants = create_contestants(
        navigation_task,
        new_navigation_task,
        arguments.number_of_contestants,
        datetime.timedelta(seconds=arguments.start_interval_seconds),
    )
    load_data_traccar(new_contestants)
