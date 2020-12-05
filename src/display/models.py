import datetime
import math
from plistlib import Dict
from typing import List
import cartopy.crs as ccrs
from django.core.exceptions import ObjectDoesNotExist

from django.db import models

# Create your models here.
from solo.models import SingletonModel

from display.my_pickled_object_field import MyPickledObjectField
from display.waypoint import Waypoint
from display.wind_utilities import calculate_ground_speed_combined


def user_directory_path(instance, filename):
    return "aeroplane_{0}/{1}".format(instance.registration, filename)


class TraccarCredentials(SingletonModel):
    server_name = models.CharField(max_length=100)
    protocol = models.CharField(max_length=10, default="http")
    address = models.CharField(max_length=100, default="traccar:8082")
    token = models.CharField(max_length=100)

    def __str__(self):
        return "Traccar credentials: {}".format(self.address)

    class Meta:
        verbose_name = "Traccar credentials"


class Aeroplane(models.Model):
    registration = models.CharField(max_length=20)

    def __str__(self):
        return self.registration


class Track(models.Model):
    name = models.CharField(max_length=200)
    waypoints = MyPickledObjectField(default=list)
    starting_line = MyPickledObjectField(default=list)

    def __str__(self):
        return self.name

    @classmethod
    def create(cls, name: str, waypoints: List[Dict]) -> "Track":
        waypoints = cls.add_gate_data(waypoints)
        starting_line = cls.create_starting_line(waypoints)
        object = cls(name=name, waypoints=waypoints, starting_line=starting_line)
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
                                                                             gates[index + 1]["width"] * 1852)
            gates[index + 1]["gate_line_infinite"] = create_perpendicular_line_at_end(gates[index]["longitude"],
                                                                                      gates[index]["latitude"],
                                                                                      gates[index + 1]["longitude"],
                                                                                      gates[index + 1]["latitude"],
                                                                                      40 * 1852)

        gates[0]["gate_line"] = create_perpendicular_line_at_end(gates[1]["longitude"],
                                                                 gates[1]["latitude"],
                                                                 gates[0]["longitude"],
                                                                 gates[0]["latitude"],
                                                                 gates[0]["width"] * 1852)
        gates[0]["gate_line_infinite"] = create_perpendicular_line_at_end(gates[1]["longitude"],
                                                                          gates[1]["latitude"],
                                                                          gates[0]["longitude"],
                                                                          gates[0]["latitude"],
                                                                          40 * 1852)

        return waypoints

    @staticmethod
    def create_starting_line(gates) -> Dict:
        return gates[0]



def get_next_turning_point(waypoints: List, gate_name: str) -> Waypoint:
    found_current = False
    for gate in waypoints:
        if found_current:
            return gate
        if gate.name == gate_name:
            found_current = True


def bearing_difference(bearing1, bearing2) -> float:
    return (bearing2 - bearing1 + 540) % 360 - 180


def is_procedure_turn(bearing1, bearing2) -> bool:
    """
    Return True if the turn is more than 90 degrees

    :param bearing1: degrees
    :param bearing2: degrees
    :return:
    """
    return abs(bearing_difference(bearing1, bearing2)) > 90


def create_perpendicular_line_at_end(x1, y1, x2, y2, length):
    pc = ccrs.PlateCarree()
    epsg = ccrs.epsg(3857)
    x1, y1 = epsg.transform_point(x1, y1, pc)
    x2, y2 = epsg.transform_point(x2, y2, pc)
    slope = (y2 - y1) / (x2 - x1)
    dy = math.sqrt((length / 2) ** 2 / (slope ** 2 + 1))
    dx = -slope * dy
    x1, y1 = pc.transform_point(x2 + dx, y2 + dy, epsg)
    x2, y2 = pc.transform_point(x2 - dx, y2 - dy, epsg)
    return [[x1, y1], [x2, y2]]


class Team(models.Model):
    pilot = models.CharField(max_length=200)
    navigator = models.CharField(max_length=200, blank=True)
    aeroplane = models.ForeignKey(Aeroplane, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        if len(self.navigator) > 0:
            return "{} and {} in {}".format(self.pilot, self.navigator, self.aeroplane)
        return "{} in {}".format(self.pilot, self.aeroplane)


class Contest(models.Model):
    PRECISION = 0
    ANR = 1
    CONTEST_TYPES = (
        (PRECISION, "Precision"),
        (ANR, "ANR")
    )

    name = models.CharField(max_length=200)
    contest_type = models.IntegerField(choices=CONTEST_TYPES, default=PRECISION)
    track = models.ForeignKey(Track, on_delete=models.SET_NULL, null=True)
    server_address = models.CharField(max_length=200, blank=True)
    server_token = models.CharField(max_length=200, blank=True)
    start_time = models.DateTimeField()
    finish_time = models.DateTimeField()
    wind_speed = models.FloatField(default=0)
    wind_direction = models.FloatField(default=0)

    def __str__(self):
        return "{}: {}".format(self.name, self.start_time.isoformat())


class Scorecard(models.Model):
    name = models.CharField(max_length=100, default="default", unique=True)
    missed_gate = models.FloatField(default=100)
    gate_timing_per_second = models.FloatField(default=3)
    gate_perfect_limit_seconds = models.FloatField(default=2)
    maximum_gate_score = models.FloatField(default=100)
    backtracking = models.FloatField(default=200)
    missed_procedure_turn = models.FloatField(default=200)
    below_minimum_altitude = models.FloatField(default=500)
    takeoff_time_limit_seconds = models.FloatField(default=60)
    missed_takeoff_gate = models.FloatField(default=100)

    def __str__(self):
        return self.name


class Contestant(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE)
    takeoff_time = models.DateTimeField()
    minutes_to_starting_point = models.FloatField(default=5)
    finished_by_time = models.DateTimeField(null=True)
    air_speed = models.FloatField(default=70)
    contestant_number = models.IntegerField()
    traccar_device_name = models.CharField(max_length=100)
    scorecard = models.ForeignKey(Scorecard, on_delete=models.PROTECT, null=True)

    class Meta:
        unique_together = ("contest", "contestant_number")

    def __str__(self):
        return "{}: {} in {} ({}, {})".format(self.contestant_number, self.team, self.contest.name, self.takeoff_time,
                                              self.finished_by_time)

    def get_groundspeed(self, bearing) -> float:
        return calculate_ground_speed_combined(bearing, self.air_speed, self.contest.wind_speed,
                                               self.contest.wind_direction)

    @property
    def gate_times(self) -> Dict:
        crossing_times = {}
        gates = self.contest.track.waypoints
        crossing_time = self.takeoff_time + datetime.timedelta(minutes=self.minutes_to_starting_point)
        crossing_times[gates[0].name] = crossing_time
        for index in range(len(gates)-1):  # type: Waypoint
            gate = gates[index]
            next_gate = gates[index + 1]
            ground_speed = self.get_groundspeed(gate.bearing_next)
            crossing_time += datetime.timedelta(
                hours=(gate.distance_next / 1852) / ground_speed)
            crossing_times[next_gate.name] = crossing_time
            if next_gate.is_procedure_turn:
                crossing_time += datetime.timedelta(minutes=1)
        return crossing_times

    @classmethod
    def get_contestant_for_device_at_time(cls, device: str, stamp: datetime.datetime):
        try:
            # Device belongs to contestant from 30 minutes before takeoff
            return cls.objects.get(traccar_device_name=device, takeoff_time__lte=stamp + datetime.timedelta(minutes=30),
                                   finished_by_time__gte=stamp)
        except ObjectDoesNotExist:
            return None


CONTESTANT_CACHE_KEY = "contestant"


class ContestantTrack(models.Model):
    contestant = models.OneToOneField(Contestant, on_delete=models.CASCADE)
    score_log = MyPickledObjectField(default=list)
    score_per_gate = MyPickledObjectField(default=dict)
    score = models.FloatField(default=0)
    current_state = models.CharField(max_length=200, default="Waiting...")
    current_leg = models.CharField(max_length=100, default="")
    last_gate = models.CharField(max_length=100, default="")
    last_gate_time_offset = models.FloatField(default=0)
    past_starting_gate = models.BooleanField(default=False)
    past_finish_gate = models.BooleanField(default=False)
    calculator_finished = models.BooleanField(default=False)

    def update_last_gate(self, gate_name, time_difference):
        self.last_gate = gate_name
        self.last_gate_time_offset = time_difference
        self.save()

    def update_score(self, score_per_gate, score, score_log):
        self.score = score
        self.score_per_gate = score_per_gate
        self.score_log = score_log
        self.save()

    def updates_current_state(self, state: str):
        if self.current_state != state:
            self.current_state = state
            self.save()

    def update_current_leg(self, current_leg: str):
        if self.current_leg != current_leg:
            self.current_leg = current_leg
            self.save()

    def set_calculator_finished(self):
        self.calculator_finished = True
        self.save()
