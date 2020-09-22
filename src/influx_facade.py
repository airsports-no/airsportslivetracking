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

    def add_annotation(self, contestant, latitude, longitude, message, type):
        data = {
            "measurement": "annotation",
            "tags": {
                "contestant": contestant.pk,
                "contest": contestant.contest_id,
            },
            "time": datetime.datetime.now().astimezone().isoformat(),
            "fields": {
                "latitude": latitude,
                "longitude": longitude,
                "message": message,
                "type": type
            }
        }
        self.client.write_points([data])

    def store_positions(self, devices, positions: List) -> Dict:
        if len(positions) == 0:
            return {}
        # logger.debug("Received {} positions".format(len(positions)))
        received_tracks = {}
        positions_to_store = []
        for position_data in positions:
            # logger.debug("Incoming position: {}".format(position_data))
            try:
                device_name = devices[position_data["deviceId"]]
            except KeyError:
                logger.error("Could not find device {}.".format(position_data["deviceId"]))
            device_time = dateutil.parser.parse(position_data["deviceTime"])
            contestant = Contestant.get_contestant_for_device_at_time(device_name, device_time)
            if contestant:
                # logger.debug("Found contestant")
                data = {
                    "measurement": "device_position",
                    "tags": {
                        "contestant": contestant.pk,
                        "contest": contestant.contest_id,
                        "device_id": position_data["deviceId"]
                    },
                    "time": position_data["deviceTime"],
                    "fields": {
                        "latitude": position_data["latitude"],
                        "longitude": position_data["longitude"],
                        "altitude": position_data["altitude"],
                        "battery_level": position_data["attributes"].get("batteryLevel", -1.0),
                        "speed": position_data["speed"],
                        "course": position_data["course"]
                    }
                }
                data_record = dict(data["fields"])
                data_record["time"] = data["time"]
                try:
                    received_tracks[contestant].append(data_record)
                except KeyError:
                    received_tracks[contestant] = [data_record]
                positions_to_store.append(data)
            else:
                logger.debug("Found no contestant for device {} {} at {}".format(device_name, position_data["deviceId"],
                                                                                 device_time))
        if len(positions_to_store):
            self.put_data(positions_to_store)
        # else:
        #     logger.debug("No positions to store")
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

    def drop_database(self):
        self.client.drop_database(dbname)

    def create_database(self):
        self.client.create_database(dbname)
