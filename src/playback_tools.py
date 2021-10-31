import datetime
import time
from queue import Queue
from typing import TYPE_CHECKING
from urllib.parse import urlencode

import logging
import requests
import gpxpy

from display.calculators.calculator_factory import calculator_factory

from display.models import Contestant, ContestantUploadedTrack

import os

TRACCAR_HOST = os.environ.get("TRACCAR_HOST", "traccar")
server = f"{TRACCAR_HOST}:5055"

logger = logging.getLogger(__name__)


# server = 'localhost:5055'


def build_traccar_track(
        filename,
        today: datetime.datetime,
        start_index: int = 0,
        starting_time: datetime.datetime = None,
        leadtime_seconds: int = 0,
        time_offset: datetime.timedelta = datetime.timedelta(minutes=0),
):
    with open(filename, "r") as i:
        gpx = gpxpy.parse(i)
    positions = []
    lead = datetime.timedelta(seconds=leadtime_seconds)
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points[start_index:]:
                now = today.replace(
                    hour=point.time.hour,
                    minute=point.time.minute,
                    second=point.time.second,
                    microsecond=point.time.microsecond,
                )
                now += time_offset
                if starting_time is None or now > starting_time - lead:
                    positions.append((now.astimezone(), point.latitude, point.longitude))
    return positions


def load_data_traccar(tracks, offset=30, leadtime=0, round_sleep=0.2):
    def send(id, time, lat, lon, speed):
        params = (("id", id), ("timestamp", int(time)), ("lat", lat), ("lon", lon), ("speed", speed))
        requests.post("http://" + server + "/?" + urlencode(params))

    next_times = {}
    index = 0
    for contestant_name, (positions, start_time) in tracks.items():
        next_times[contestant_name] = start_time - datetime.timedelta(seconds=index * offset + leadtime)
        index += 1
    count = 0
    time_step = 2
    first_round = True
    while True:
        remaining = False
        for contestant_name, (positions, start_time) in tracks.items():
            next_times[contestant_name] += datetime.timedelta(seconds=time_step)
            while len(positions) > 0 and positions[0][0] < next_times[contestant_name]:
                count += 1
                stamp, latitude, longitude = positions.pop(0)
                if not first_round:
                    send(contestant_name, time.mktime(stamp.timetuple()), latitude, longitude, 0)
            remaining = remaining or len(positions) > 0
        print(count)
        first_round = False
        time.sleep(round_sleep)
        if not remaining:
            break


def recalculate_traccar(contestant: "Contestant"):
    try:
        contestant.contestantuploadedtrack.delete()
        logger.debug("Deleted existing uploaded track")
    except:
        pass
    contestant.contestantreceivedposition_set.all().delete()
    track = contestant.get_traccar_track()
    q = Queue()
    for i in track:
        q.put(i)
    q.put(None)
    calculator = calculator_factory(contestant, q, live_processing=False)
    calculator.run()
    while not q.empty():
        q.get_nowait()


def insert_gpx_file(contestant_object: "Contestant", file):
    try:
        gpx = gpxpy.parse(file)
        logger.debug("Successfully parsed GPX file")
    except:
        logger.exception("Failed parsing GPX file")
        return
    positions = []
    index = 0
    try:
        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    if point.time:
                        positions.append(
                            {
                                "deviceId": contestant_object.tracker_device_id,
                                "id": index,
                                "latitude": float(point.latitude),
                                "longitude": float(point.longitude),
                                "altitude": float(point.elevation) if point.elevation else 0,
                                "attributes": {"batteryLevel": 1.0},
                                "speed": 0.0,
                                "course": 0.0,
                                "device_time": point.time,
                            }
                        )
                        index += 1
    except:
        logger.exception("Something bad happened when building position list")
    try:
        contestant_object.contestantuploadedtrack.delete()
        logger.debug("Deleted existing uploaded track")
    except:
        pass
    ContestantUploadedTrack.objects.create(contestant=contestant_object, track=positions)
    logger.debug("Created new uploaded track with {} positions".format(len(positions)))
    # generated_positions = influx.generate_position_data_for_contestant(contestant_object, positions)
    # influx.put_position_data_for_contestant(contestant_object, positions)
    q = Queue()
    for i in positions:
        q.put(i)
    q.put(None)
    calculator = calculator_factory(contestant_object, q, live_processing=False)
    calculator.run()
    while not q.empty():
        q.get_nowait()
