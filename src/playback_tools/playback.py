import datetime
import time
from urllib.parse import urlencode

import logging
import requests
import gpxpy

from display.utilities.calculator_termination_utilities import cancel_termination_request
from display.calculators.calculator_factory import calculator_factory
from display.utilities.coordinate_utilities import calculate_speed_between_points, calculate_bearing

from display.models import Contestant, ContestantUploadedTrack

import os

from redis_queue import RedisQueue

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


def load_data_traccar(tracks, offset=30, leadtime=0, round_sleep=0.2, contestant_map=None):
    def send(id, time, lat, lon, speed):
        params = (("id", id), ("timestamp", int(time)), ("lat", lat), ("lon", lon), ("speed", speed))
        requests.post("http://" + server + "/?" + urlencode(params))

    next_times = {}
    previous_positions = {}
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
                try:
                    p_stamp, p_latitude, p_longitude = previous_positions[contestant_name]
                    speed = calculate_speed_between_points(
                        (p_latitude, p_longitude),
                        (latitude, longitude),
                        p_stamp, stamp)
                except KeyError:
                    speed = 0
                previous_positions[contestant_name] = (stamp, latitude, longitude)
                if not first_round:
                    if contestant_map and contestant_name in contestant_map:
                        print(f"Saving contestant {contestant_map[contestant_name]}")
                        contestant_map[contestant_name].save()
                        del contestant_map[contestant_name]
                    send(contestant_name, time.mktime(stamp.timetuple()), latitude, longitude, speed)
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
    now = datetime.datetime.now(datetime.timezone.utc)
    if contestant.finished_by_time > now:
        contestant.finished_by_time = max(contestant.takeoff_time + datetime.timedelta(seconds=1), now)
        contestant.save(update_fields=["finished_by_time"])
    track = contestant.get_traccar_track()
    queue_name = f"override_{contestant.pk}"
    q = RedisQueue(queue_name)
    while not q.empty():
        q.pop()
    for i in track:
        q.append(i)
    q.append(None)
    logger.debug(f"Loaded {len(track)} positions")
    cancel_termination_request(contestant.pk)
    calculator = calculator_factory(contestant, live_processing=False, queue_name_override=queue_name)
    calculator.run()
    while not q.empty():
        q.pop()


def insert_gpx_file(contestant_object: "Contestant", file):
    now = datetime.datetime.now(datetime.timezone.utc)
    if contestant_object.finished_by_time > now:
        contestant_object.finished_by_time = max(contestant_object.takeoff_time + datetime.timedelta(seconds=1), now)
        contestant_object.save(update_fields=["finished_by_time"])

    try:
        gpx = gpxpy.parse(file)
        logger.debug("Successfully parsed GPX file")
    except:
        logger.exception("Failed parsing GPX file")
        return
    positions = []
    index = 0
    previous_point = None
    try:
        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    if point.time:
                        speed = 0.0
                        course = 0.0
                        if previous_point:
                            speed = calculate_speed_between_points(
                                (previous_point["latitude"], previous_point["longitude"]),
                                (float(point.latitude), float(point.longitude)),
                                previous_point["device_time"], point.time)
                            # logger.debug(f"speed: {speed}")
                            course = calculate_bearing((previous_point["latitude"], previous_point["longitude"]),
                                                       (point.latitude, point.longitude))
                        positions.append(
                            {
                                "deviceId": contestant_object.tracker_device_id,
                                "id": index,
                                "latitude": float(point.latitude),
                                "longitude": float(point.longitude),
                                "altitude": float(point.elevation) if point.elevation else 0,
                                "attributes": {"batteryLevel": 1.0},
                                "speed": speed,
                                "course": course,
                                "device_time": point.time,
                            }
                        )
                        if len(positions) > 2:
                            previous_point = positions[-2]
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
    queue_name = f"override_{contestant_object.pk}"
    q = RedisQueue(queue_name)
    while not q.empty():
        q.pop()
    for i in positions:
        q.append(i)
    q.append(None)
    cancel_termination_request(contestant_object.pk)
    calculator = calculator_factory(contestant_object, live_processing=False, queue_name_override=queue_name)
    calculator.run()
    while not q.empty():
        q.pop()
