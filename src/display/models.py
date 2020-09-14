import math
from collections import namedtuple
from plistlib import Dict
from typing import List
import cartopy.crs as ccrs

from django.db import models

# Create your models here.
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
    gates = MyPickledObjectField(default=dict)

    def __str__(self):
        return self.name

    def get_gates(self) -> Dict:
        gates = [item for item in self.waypoints if item["type"] in ("tp", "secret")]
        gate_lines = {}
        for index in range(len(gates) - 1):
            gate_lines[gates[index + 1]["name"]] = create_perpendicular_line_at_end(gates[index]["longitude"],
                                                                                    gates[index]["latitude"],
                                                                                    gates[index + 1]["longitude"],
                                                                                    gates[index + 1]["latitude"],
                                                                                    gates[index + 1]["width"])
        gate_lines[gates[0]["name"]] = create_perpendicular_line_at_end(gates[1]["longitude"],
                                                                        gates[1]["latitude"],
                                                                        gates[0]["longitude"],
                                                                        gates[0]["latitude"],
                                                                        gates[0]["width"])
        return gate_lines


def create_perpendicular_line_at_end(x1, y1, x2, y2, length):
    pc = ccrs.PlateCarree()
    epsg = ccrs.epsg(3857)
    x1, y1 = epsg.transform_point(x1, y1, pc)
    x2, y2 = epsg.transform_point(x2, y2, pc)
    length_metres = length*1852/2
    slope = (y2 - y1) / (x2 - x1)
    dy = math.sqrt((length_metres / 2) ** 2 / (slope ** 2 + 1))
    dx = -slope * dy
    x1, y1 = pc.transform_point(x2 + dx, y2 + dy, epsg)
    x2, y2 = pc.transform_point(x2 - dx, y2 - dy, epsg)
    return [x1, y1, x2, y2]


class Team(models.Model):
    pilot = models.CharField(max_length=200)
    navigator = models.CharField(max_length=200)
    aeroplane = models.ForeignKey(Aeroplane, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return "{} and {} in {}".format(self.pilot, self.navigator, self.aeroplane)


class Contest(models.Model):
    name = models.CharField(max_length=200)
    track = models.ForeignKey(Track, on_delete=models.SET_NULL, null=True)
    start_time = models.DateTimeField()
    finish_time = models.DateTimeField()

    def __str__(self):
        return "{}: {}".format(self.name, self.start_time.isoformat())


class Contestant(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    finished_by_time = models.DateTimeField(null=True)
    ground_speed = models.FloatField(default=70)
    contestant_number = models.IntegerField()
    traccar_device_name = models.CharField(max_length=100)

    def __str__(self):
        return "{}: {} in {}".format(self.contestant_number, self.team, self.contest)
