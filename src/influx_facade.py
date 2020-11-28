import datetime
import logging
from plistlib import Dict
from typing import List, Union, Set

import dateutil
from influxdb import InfluxDBClient
from influxdb.resultset import ResultSet

from display.models import ContestantTrack, Contestant

host = "influx"
port = 8086
user = "airsport"
dbname = "airsport"
password = "notsecret"

logger = logging.getLogger(__name__)


class InfluxFacade:
    def __init__(self):
        self.client = InfluxDBClient(host, port, user, password, dbname)

    def add_annotation(self, contestant, latitude, longitude, message, annotation_type, stamp):
        try:
            contestant.annotation_index += 1
        except:
            contestant.annotation_index = 0
        data = {
            "measurement": "annotation",
            "tags": {
                "contestant": contestant.pk,
                "contest": contestant.contest_id,
                "annotation_number": contestant.annotation_index
            },
            "time": stamp.isoformat(),
            "fields": {
                "latitude": latitude,
                "longitude": longitude,
                "message": message,
                "type": annotation_type
            }
        }
        self.client.write_points([data])

    def generate_position_data(self, traccar_facade, positions: List) -> Dict:
        if len(positions) == 0:
            return {}
        # logger.debug("Received {} positions".format(len(positions)))
        received_tracks = {}
        positions_to_store = []
        for position_data in positions:
            # logger.debug("Incoming position: {}".format(position_data))
            try:
                device_name = self.devices[position_data["deviceId"]]
            except KeyError:
                self.devices = traccar_facade.get_device_map()
                try:
                    device_name = self.devices[position_data["deviceId"]]
                except KeyError:
                    logger.error("Could not find device {}.".format(position_data["deviceId"]))
                    continue
            device_time = dateutil.parser.parse(position_data["deviceTime"])
            # print(device_name)
            # print(device_time)
            contestant = Contestant.get_contestant_for_device_at_time(device_name, device_time)
            # print(contestant)
            if contestant:
                # logger.info("Found contestant")
                data = {
                    "measurement": "device_position",
                    "tags": {
                        "contestant": contestant.pk,
                        "contest": contestant.contest_id,
                        "device_id": position_data["deviceId"]
                    },
                    "time": device_time.isoformat(),
                    "fields": {
                        "latitude": position_data["latitude"],
                        "longitude": position_data["longitude"],
                        "altitude": position_data["altitude"],
                        "battery_level": position_data["attributes"].get("batteryLevel", -1.0),
                        "speed": position_data["speed"],
                        "course": position_data["course"]
                    }
                }
                try:
                    received_tracks[contestant].append(data)
                except KeyError:
                    received_tracks[contestant] = [data]
        return received_tracks

    def put_data(self, data: List):
        self.client.write_points(data)
        logger.debug("Successfully put {} position".format(len(data)))

    def get_positions_for_contest(self, contest_pk, from_time: Union[datetime.datetime, str]) -> ResultSet:
        if isinstance(from_time, datetime.datetime):
            from_time = from_time.isoformat()
        query = "select * from device_position where contest=$contest and time>$from_time;"
        bind_params = {'contest': str(contest_pk), 'from_time': from_time}
        response = self.client.query(query, bind_params=bind_params)
        return response

    def get_annotations_for_contest(self, contest_pk, from_time: Union[datetime.datetime, str]) -> ResultSet:
        if isinstance(from_time, datetime.datetime):
            from_time = from_time.isoformat()
        query = "select * from annotation where contest=$contest and time>$from_time;"
        bind_params = {'contest': str(contest_pk), 'from_time': from_time}
        response = self.client.query(query, bind_params=bind_params)
        return response

    def get_positions_for_contestant(self, contestant_pk, from_time: Union[datetime.datetime, str]) -> ResultSet:
        if isinstance(from_time, datetime.datetime):
            from_time = from_time.isoformat()
        query = "select * from device_position where contestant=$contestant and time>$from_time;"
        bind_params = {'contestant': str(contestant_pk), 'from_time': from_time}
        response = self.client.query(query, bind_params=bind_params)
        return response

    def get_annotations_for_contestant(self, contestant_pk, from_time: Union[datetime.datetime, str]) -> ResultSet:
        if isinstance(from_time, datetime.datetime):
            from_time = from_time.isoformat()
        query = "select * from annotation where contestant=$contestant and time>$from_time;"
        bind_params = {'contestant': str(contestant_pk), 'from_time': from_time}
        response = self.client.query(query, bind_params=bind_params)
        return response

    def drop_database(self):
        self.client.drop_database(dbname)

    def create_database(self):
        self.client.create_database(dbname)
