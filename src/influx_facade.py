import datetime
import logging
import threading
import uuid
from plistlib import Dict
from typing import List, Union, Set, Optional

import dateutil
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from influxdb import InfluxDBClient
from influxdb.resultset import ResultSet

from display.models import ContestantTrack, Contestant, Person
from display.serialisers import ContestantTrackSerialiser
from traccar_facade import Traccar

host = "influx"
port = 8086
user = "airsport"
dbname = "airsport"
password = "notsecret"

logger = logging.getLogger(__name__)
GLOBAL_TRANSMISSION_INTERVAL = 30
PURGE_GLOBAL_MAP_INTERVAL = 1200


class InfluxFacade:
    def __init__(self):
        self.channel_layer = get_channel_layer()
        self.client = InfluxDBClient(host, port, user, password, dbname)
        self.global_map = {}
        self.last_purge = datetime.datetime.now(datetime.timezone.utc)


    def purge_global_map(self):
        logger.info("Purging global map cache")
        now = datetime.datetime.now(datetime.timezone.utc)
        self.last_purge = now
        for key, value in self.global_map.items():
            if (now - value[0]).total_seconds() > PURGE_GLOBAL_MAP_INTERVAL:
                del self.global_map[key]
        cache.set("GLOBAL_MAP_DATA", self.global_map)
        threading.Timer(PURGE_GLOBAL_MAP_INTERVAL, self.purge_global_map).start()
        logger.info("Purged global map cache")


    def add_annotation(self, contestant, latitude, longitude, message, annotation_type, stamp):
        try:
            contestant.annotation_index += 1
        except:
            contestant.annotation_index = 0
        data = {
            "measurement": "annotation",
            "tags": {
                "contestant": contestant.pk,
                "navigation_task": contestant.navigation_task_id,
                "annotation_number": contestant.annotation_index
            },
            "time": stamp.isoformat(),
            "fields": {
                "latitude": float(latitude),
                "longitude": float(longitude),
                "message": message,
                "type": annotation_type
            }
        }
        group_key = "tracking_{}".format(contestant.navigation_task.pk)
        annotation = {}
        annotation.update(data["tags"])
        annotation["time"] = data["time"]
        annotation.update(data["fields"])
        channel_data = {
            "contestant_id": contestant.pk,
            "positions": [],
            "annotations": [annotation],
            "latest_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "contestant_track": ContestantTrackSerialiser(contestant.contestanttrack).data

        }
        async_to_sync(self.channel_layer.group_send)(
            group_key,
            {"type": "tracking.data", "data": channel_data}
        )
        self.client.write_points([data])

    def generate_position_data_for_contestant(self, contestant: Contestant, positions: List) -> List:
        data = []
        for position_data in positions:
            device_time = dateutil.parser.parse(position_data["deviceTime"])
            data.append({
                "measurement": "device_position",
                "tags": {
                    "contestant": contestant.pk,
                    "navigation_task": contestant.navigation_task_id,
                    "device_id": position_data["deviceId"]
                },
                "time": device_time.isoformat(),
                "fields": {
                    "latitude": float(position_data["latitude"]),
                    "longitude": float(position_data["longitude"]),
                    "altitude": float(position_data["altitude"]),
                    "battery_level": float(position_data["attributes"].get("batteryLevel", -1.0)),
                    "speed": float(position_data["speed"]),
                    "course": float(position_data["course"])
                }
            })
        return data

    def generate_position_data(self, traccar: Traccar, positions: List) -> Dict:
        if len(positions) == 0:
            return {}
        # logger.info("Received {} positions".format(len(positions)))
        received_tracks = {}
        for position_data in positions:
            global_tracking_name = ""
            # logger.info("Incoming position: {}".format(position_data))
            try:
                device_name = traccar.device_map[position_data["deviceId"]]
            except KeyError:
                traccar.get_device_map()
                try:
                    device_name = traccar.device_map[position_data["deviceId"]]
                except KeyError:
                    logger.error("Could not find device {}.".format(position_data["deviceId"]))
                    continue
            device_time = dateutil.parser.parse(position_data["deviceTime"])
            # logger.info(device_name)
            if device_time < datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1):
                logger.info(f"Received old position, disregarding: {device_name} {device_time}")
                continue
            # print(device_time)
            contestant = Contestant.get_contestant_for_device_at_time(device_name, device_time)
            if not contestant:
                try:
                    person = Person.objects.get(app_tracking_id=device_name)
                    global_tracking_name = person.app_aircraft_registration
                except ObjectDoesNotExist:
                    # logger.info("Found no person for tracking ID {}".format(device_name))
                    pass
            # print(contestant)
            if contestant:
                # logger.info("Found contestant {}".format(contestant))
                global_tracking_name = contestant.team.aeroplane.registration
                data = {
                    "measurement": "device_position",
                    "tags": {
                        "contestant": contestant.pk,
                        "navigation_task": contestant.navigation_task_id,
                        "device_id": position_data["deviceId"]
                    },
                    "time": device_time.isoformat(),
                    "time_object": device_time,
                    "fields": {
                        "latitude": float(position_data["latitude"]),
                        "longitude": float(position_data["longitude"]),
                        "altitude": float(position_data["altitude"]),
                        "battery_level": float(position_data["attributes"].get("batteryLevel", -1.0)),
                        "speed": float(position_data["speed"]),
                        "course": float(position_data["course"])
                    }
                }
                try:
                    received_tracks[contestant].append(data)
                except KeyError:
                    received_tracks[contestant] = [data]
            last_global, last_data = self.global_map.get(position_data["deviceId"],
                                                         (datetime.datetime.min.replace(tzinfo=datetime.timezone.utc),
                                                          {}))
            now = datetime.datetime.now(datetime.timezone.utc)
            # logger.info(f"Checking transmission for ({contestant}) {global_tracking_name} with last transmitted {last_global} and device ID {position_data['deviceId']}")
            if (now - last_global).total_seconds() > GLOBAL_TRANSMISSION_INTERVAL:
                data = {
                    "type": "tracking.data",
                    "data": {
                        "name": global_tracking_name,
                        "time": device_time.isoformat(),
                        "deviceId": position_data["deviceId"],
                        "latitude": float(position_data["latitude"]),
                        "longitude": float(position_data["longitude"]),
                        "altitude": float(position_data["altitude"]),
                        "battery_level": float(position_data["attributes"].get("batteryLevel", -1.0)),
                        "speed": float(position_data["speed"]),
                        "course": float(position_data["course"])
                    }
                }

                self.global_map[position_data["deviceId"]] = (now, data)
                cache.set("GLOBAL_MAP_DATA", self.global_map)
                async_to_sync(self.channel_layer.group_send)(
                    "tracking_global", data
                )

        return received_tracks

    def put_position_data_for_contestant(self, contestant: "Contestant", data: List, route_progress):
        position_data = []
        for item in data:
            position_data.append({
                "latitude": item["fields"]["latitude"],
                "longitude": item["fields"]["longitude"],
                "speed": item["fields"]["speed"],
                "course": item["fields"]["course"],
                "altitude": item["fields"]["altitude"],
                "time": item["time"]
            })
        channel_data = {
            "contestant_id": contestant.pk,
            "positions": position_data,
            "annotations": [],
            "progress": route_progress,
            "latest_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "contestant_track": ContestantTrackSerialiser(contestant.contestanttrack).data

        }
        group_key = "tracking_{}".format(contestant.navigation_task.pk)
        async_to_sync(self.channel_layer.group_send)(
            group_key,
            {"type": "tracking.data", "data": channel_data}
        )
        self.client.write_points(data)
        # logger.debug("Successfully put {} position".format(len(data)))

    def clear_data_for_contestant(self, contestant_id: int):
        self.client.delete_series(tags={"contestant": str(contestant_id)})

    def get_positions_for_contest(self, navigation_task_pk, from_time: Union[datetime.datetime, str]) -> ResultSet:
        if isinstance(from_time, datetime.datetime):
            from_time = from_time.isoformat()
        query = "select * from device_position where navigation_task=$navigation_task and time>$from_time;"
        bind_params = {'navigation_task': str(navigation_task_pk), 'from_time': from_time}
        response = self.client.query(query, bind_params=bind_params)
        return response

    def get_number_of_positions_in_database(self) -> int:
        query = "select count(*) from device_position;"
        response = self.client.query(query)
        return response

    def get_annotations_for_navigation_task(self, navigation_task_pk,
                                            from_time: Union[datetime.datetime, str]) -> ResultSet:
        if isinstance(from_time, datetime.datetime):
            from_time = from_time.isoformat()
        query = "select * from annotation where navigation_task=$navigation_task and time>$from_time;"
        bind_params = {'navigation_task': str(navigation_task_pk), 'from_time': from_time}
        response = self.client.query(query, bind_params=bind_params)
        return response

    def get_positions_for_contestant(self, contestant_pk, from_time: Union[datetime.datetime, str],
                                     limit: Optional[int] = None) -> ResultSet:
        if isinstance(from_time, datetime.datetime):
            from_time = from_time.isoformat()
        query = "select * from device_position where contestant=$contestant and time>$from_time"
        bind_params = {'contestant': str(contestant_pk), 'from_time': from_time}
        if limit is not None:
            query += " limit $limit"
            bind_params["limit"] = limit
        query += ";"
        response = self.client.query(query, bind_params=bind_params)
        return response

    def get_annotations_for_contestant(self, contestant_pk, from_time: Union[datetime.datetime, str],
                                       until_time: Union[datetime.datetime, str]) -> ResultSet:
        if isinstance(from_time, datetime.datetime):
            from_time = from_time.isoformat()
        if isinstance(until_time, datetime.datetime):
            until_time = until_time.isoformat()
        query = "select * from annotation where contestant=$contestant and time>$from_time and time<=$until_time;"
        bind_params = {'contestant': str(contestant_pk), 'from_time': from_time, "until_time": until_time}
        response = self.client.query(query, bind_params=bind_params)
        return response

    def drop_database(self):
        self.client.drop_database(dbname)

    def create_database(self):
        self.client.create_database(dbname)
