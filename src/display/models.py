import datetime
import math
from collections import namedtuple
from plistlib import Dict
from typing import List
import cartopy.crs as ccrs

from django.db import models

# Create your models here.
from display.coordinate_utilities import calculate_distance_lat_lon, calculate_bearing
from display.my_pickled_object_field import MyPickledObjectField


def user_directory_path(instance, filename):
    return "aeroplane_{0}/{1}".format(instance.registration, filename)


class Aeroplane(models.Model):
    registration = models.CharField(max_length=20)

    def __str__(self):
        return self.registration


Waypoint = namedtuple("Waypoint", "name latitude longitude start_point finish_point is_secret")


class Track(models.Model):
    name = models.CharField(max_length=200)
    waypoints = MyPickledObjectField(default=list)

    def __str__(self):
        return self.name

    @classmethod
    def create(cls, name: str, waypoints: List[Dict]) -> "Track":
        waypoints = cls.add_gate_data(waypoints)
        waypoints = cls.legs(waypoints)
        object = cls(name=name, waypoints=waypoints)
        object.save()
        return object

    @staticmethod
    def add_gate_data(waypoints: List[Dict]) -> List[Dict]:
        """
        Changes waypoint dictionaries

        :param waypoints:
        :return:
        """
        gates = [item for item in waypoints if item["type"] in ("tp", "secret")]
        for index in range(len(gates) - 1):
            gates[index + 1]["gate_line"] = create_perpendicular_line_at_end(gates[index]["longitude"],
                                                                             gates[index]["latitude"],
                                                                             gates[index + 1]["longitude"],
                                                                             gates[index + 1]["latitude"],
                                                                             gates[index + 1]["width"])
        gates[0]["gate_line"] = create_perpendicular_line_at_end(gates[1]["longitude"],
                                                                 gates[1]["latitude"],
                                                                 gates[0]["longitude"],
                                                                 gates[0]["latitude"],
                                                                 gates[0]["width"])
        return waypoints

    @staticmethod
    def legs(waypoints) -> Dict:
        tp_gates = [item for item in waypoints if item["type"] == "tp"]
        for index in range(1, len(tp_gates)):
            tp_gates[index]["bearing"] = calculate_bearing(
                (tp_gates[index - 1]["latitude"], tp_gates[index - 1]["longitude"]),
                (tp_gates[index]["latitude"], tp_gates[index]["longitude"]))
        for index in range(1, len(tp_gates) - 1):
            print(tp_gates[index])
            tp_gates[index]["is_procedure_turn"] = is_procedure_turn(tp_gates[index]["bearing"],
                                                                     tp_gates[index + 1]["bearing"])
            tp_gates[index]["turn_direction"] = "cw" if bearing_difference(tp_gates[index]["bearing"],
                                                                                     tp_gates[index + 1][
                                                                                         "bearing"]) > 0 else "ccw"

        gates = [item for item in waypoints if item["type"] in ("tp", "secret")]
        for index in range(1, len(gates)):
            # distance as nm
            gates[index]["distance"] = calculate_distance_lat_lon(
                (gates[index - 1]["latitude"], gates[index - 1]["longitude"]),
                (gates[index]["latitude"], gates[index]["longitude"])) * 1.852
        return waypoints


def bearing_difference(bearing1, bearing2) -> float:
    return (bearing2 - bearing1 + 540) % 360 - 180


def is_procedure_turn(bearing1, bearing2) -> bool:
    """
    Return True if the turn is more than 90 degrees

    :param bearing1: degrees
    :param bearing2: degrees
    :return:
    """
    reciprocal = (180 - bearing2) % 360
    return abs(bearing_difference(bearing1, reciprocal)) > 90


def create_perpendicular_line_at_end(x1, y1, x2, y2, length):
    pc = ccrs.PlateCarree()
    epsg = ccrs.epsg(3857)
    x1, y1 = epsg.transform_point(x1, y1, pc)
    x2, y2 = epsg.transform_point(x2, y2, pc)
    length_metres = length * 1852 / 2
    slope = (y2 - y1) / (x2 - x1)
    dy = math.sqrt((length_metres / 2) ** 2 / (slope ** 2 + 1))
    dx = -slope * dy
    x1, y1 = pc.transform_point(x2 + dx, y2 + dy, epsg)
    x2, y2 = pc.transform_point(x2 - dx, y2 - dy, epsg)
    return [x1, y1, x2, y2]


class Team(models.Model):
    pilot = models.CharField(max_length=200)
    navigator = models.CharField(max_length=200, blank=True)
    aeroplane = models.ForeignKey(Aeroplane, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return "{} and {} in {}".format(self.pilot, self.navigator, self.aeroplane)


class Contest(models.Model):
    name = models.CharField(max_length=200)
    track = models.ForeignKey(Track, on_delete=models.SET_NULL, null=True)
    server_address = models.CharField(max_length=200, blank=True)
    server_token = models.CharField(max_length=200, blank=True)
    start_time = models.DateTimeField()
    finish_time = models.DateTimeField()

    def __str__(self):
        return "{}: {}".format(self.name, self.start_time.isoformat())


class Contestant(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE)
    takeoff_time = models.DateTimeField()
    minutes_to_starting_point = models.FloatField(default=5)
    finished_by_time = models.DateTimeField(null=True)
    ground_speed = models.FloatField(default=70)
    contestant_number = models.IntegerField()
    traccar_device_name = models.CharField(max_length=100)

    def __str__(self):
        return "{}: {} in {}".format(self.contestant_number, self.team, self.contest)

    @property
    def gate_times(self) -> Dict:
        crossing_times = {}
        gates = [item for item in self.contest.track.waypoints if item["type"] in ("tp", "secret")]
        crossing_time = self.takeoff_time + datetime.timedelta(minutes=self.minutes_to_starting_point)
        crossing_times[gates[0]["name"]] = crossing_time
        for gate in gates[1:]:
            print(gate)
            crossing_time += datetime.timedelta(hours=gate["distance"] / self.ground_speed)
            if gate.get("is_procedure_turn", False):
                crossing_time += datetime.timedelta(minutes=1)
            crossing_times[gate["name"]] = crossing_time
        return crossing_times
