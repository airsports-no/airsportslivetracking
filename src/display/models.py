import datetime
import math
from plistlib import Dict
from typing import List, Optional
import cartopy.crs as ccrs
from django.contrib.auth.models import User
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
    colour = models.CharField(max_length=40)
    type = models.CharField(max_length=50)

    def __str__(self):
        return self.registration


class Track(models.Model):
    name = models.CharField(max_length=200)
    waypoints = MyPickledObjectField(default=list)
    starting_line = MyPickledObjectField(default=list)
    takeoff_gate = MyPickledObjectField(default=None, null=True)
    landing_gate = MyPickledObjectField(default=None, null=True)

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


class Crew(models.Model):
    pilot = models.CharField(max_length=200)
    navigator = models.CharField(max_length=200, blank=True)

    def __str__(self):
        if len(self.navigator) > 0:
            return "{} and {} in {}".format(self.pilot, self.navigator, self.aeroplane)
        return "{} in {}".format(self.pilot, self.aeroplane)


class Team(models.Model):
    aeroplane = models.ForeignKey(Aeroplane, on_delete=models.SET_NULL, null=True)
    crew = models.ForeignKey(Crew, on_delete=models.SET_NULL, null=True)


class Contest(models.Model):
    PRECISION = 0
    ANR = 1
    CONTEST_TYPES = (
        (PRECISION, "Precision"),
        # (ANR, "ANR")
    )

    name = models.CharField(max_length=200)
    contest_calculator_type = models.IntegerField(choices=CONTEST_TYPES, default=PRECISION,
                                                  help_text="Supported contest calculator types. Different calculators might require different scorecard types, but currently we only support a single calculator.  Value map: {}".format(
                                                      CONTEST_TYPES))
    track = models.ForeignKey(Track, on_delete=models.SET_NULL, null=True)
    start_time = models.DateTimeField(help_text="The start time of the contest. Not really important, but nice to have")
    finish_time = models.DateTimeField(
        help_text="The finish time of the contest. Not really important, but nice to have")
    wind_speed = models.FloatField(default=0,
                                   help_text="The contest wind speed. This is used to calculate gate times if these are not predefined.")
    wind_direction = models.FloatField(default=0,
                                       help_text="The contest wind direction. This is used to calculate gate times if these are not predefined.")
    is_public = models.BooleanField(default=False,
                                    help_text="The contest is only viewable by unauthenticated users or users without object permissions if this is True")

    class Meta:
        permissions = (
            ("publish_contest", "Publish contest"),
        )

    def __str__(self):
        return "{}: {}".format(self.name, self.start_time.isoformat())


class Scorecard(models.Model):
    name = models.CharField(max_length=100, default="default", unique=True)
    backtracking_penalty = models.FloatField(default=200)
    backtracking_bearing_difference = models.FloatField(default=90)
    backtracking_grace_time_seconds = models.FloatField(default=5)
    below_minimum_altitude_penalty = models.FloatField(default=500)

    takeoff_gate_score = models.OneToOneField("GateScore", on_delete=models.CASCADE, null=True, blank=True,
                                              related_name="takeoff")
    landing_gate_score = models.OneToOneField("GateScore", on_delete=models.CASCADE, null=True, blank=True,
                                              related_name="landing")
    turning_point_gate_score = models.OneToOneField("GateScore", on_delete=models.CASCADE, null=True, blank=True,
                                                    related_name="turning_point")
    starting_point_gate_score = models.OneToOneField("GateScore", on_delete=models.CASCADE, null=True, blank=True,
                                                     related_name="starting")
    finish_point_gate_score = models.OneToOneField("GateScore", on_delete=models.CASCADE, null=True, blank=True,
                                                   related_name="finish")
    secret_gate_score = models.OneToOneField("GateScore", on_delete=models.CASCADE, null=True, blank=True,
                                             related_name="secret")

    def __str__(self):
        return self.name

    def get_gate_scorecard(self, gate_type: str) -> "GateScore":
        if gate_type == "tp":
            gate_score = self.turning_point_gate_score
        elif gate_type == "sp":
            gate_score = self.starting_point_gate_score
        elif gate_type == "fp":
            gate_score = self.finish_point_gate_score
        elif gate_type == "secret":
            gate_score = self.secret_gate_score
        elif gate_type == "to":
            gate_score = self.takeoff_gate_score
        elif gate_type == "ldg":
            gate_score = self.landing_gate_score
        else:
            raise ValueError("Unknown gate type '{}'".format(gate_type))
        if gate_score is None:
            raise ValueError("Undefined gate score for '{}'".format(gate_type))
        return gate_score

    def get_gate_timing_score_for_gate_type(self, gate_type: str, planned_time: datetime.datetime,
                                            actual_time: Optional[datetime.datetime]) -> float:
        gate_score = self.get_gate_scorecard(gate_type)
        return gate_score.calculate_score(planned_time, actual_time)

    def get_procedure_turn_penalty_for_gate_type(self, gate_type: str) -> float:
        gate_score = self.get_gate_scorecard(gate_type)
        return gate_score.missed_procedure_turn_penalty

    def get_bad_crossing_extended_gate_penalty_for_gate_type(self, gate_type: str) -> float:
        gate_score = self.get_gate_scorecard(gate_type)
        return gate_score.bad_crossing_extended_gate_penalty

    def get_extended_gate_width_for_gate_type(self, gate_type: str) -> float:
        gate_score = self.get_gate_scorecard(gate_type)
        return gate_score.extended_gate_width


class GateScore(models.Model):
    extended_gate_width = models.FloatField(default=0,
                                            help_text="For SP it is 2 (1 nm each side), for tp with procedure turn it is 6")
    bad_crossing_extended_gate_penalty = models.FloatField(default=200)
    graceperiod_before = models.FloatField(default=3)
    graceperiod_after = models.FloatField(default=3)
    maximum_penalty = models.FloatField(default=100)
    penalty_per_second = models.FloatField(default=2)
    missed_penalty = models.FloatField(default=100)
    missed_procedure_turn_penalty = models.FloatField(default=200)

    def calculate_score(self, planned_time: datetime.datetime, actual_time: Optional[datetime.datetime]) -> float:
        """

        :param planned_time:
        :param actual_time: If None the gate is missed
        :return:
        """
        if actual_time is None:
            return self.missed_penalty
        time_difference = (actual_time - planned_time).total_seconds()
        if -self.graceperiod_before < time_difference < self.graceperiod_after:
            return 0
        else:
            if time_difference > 0:
                grace_limit = self.graceperiod_after
            else:
                grace_limit = self.graceperiod_before
            return min(self.maximum_penalty,
                       (round(abs(time_difference) - grace_limit)) * self.penalty_per_second)


class Contestant(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE)
    takeoff_time = models.DateTimeField(
        help_text="The time the take of gate (if it exists) should be crossed. Otherwise it is the time power should be applied")
    minutes_to_starting_point = models.FloatField(default=5,
                                                  help_text="The number of minutes from the take-off time until the starting point")
    finished_by_time = models.DateTimeField(null=True,
                                            help_text="The time it is expected that the contest has finished and landed (used among other things for knowing when the tracker is busy). Is also used for the gate time for the landing gate")
    air_speed = models.FloatField(default=70, help_text="The planned airspeed for the contestant")
    contestant_number = models.PositiveIntegerField(help_text="A unique number for the contestant in this contest")
    traccar_device_name = models.CharField(max_length=100,
                                           help_text="ID of physical tracking device that will be brought into the plane")
    scorecard = models.ForeignKey(Scorecard, on_delete=models.PROTECT, null=True,
                                  help_text="Reference to an existing scorecard name. Currently existing scorecards: {}".format(
                                      lambda: ", ".join([str(item) for item in Scorecard.objects.all()])))
    predefined_gate_times = MyPickledObjectField(default=None, null=True, blank=True,
                                                 help_text="Dictionary of gates and their starting times (with time zone)")

    class Meta:
        unique_together = ("contest", "contestant_number")

    def __str__(self):
        return "{} - {}".format(self.contestant_number, self.team)
        # return "{}: {} in {} ({}, {})".format(self.contestant_number, self.team, self.contest.name, self.takeoff_time,
        #                                       self.finished_by_time)

    def get_groundspeed(self, bearing) -> float:
        return calculate_ground_speed_combined(bearing, self.air_speed, self.contest.wind_speed,
                                               self.contest.wind_direction)

    @property
    def gate_times(self) -> Dict:
        if self.predefined_gate_times is not None and len(self.predefined_gate_times) > 0:
            return self.predefined_gate_times
        crossing_times = {}
        gates = self.contest.track.waypoints
        crossing_time = self.takeoff_time + datetime.timedelta(minutes=self.minutes_to_starting_point)
        crossing_times[gates[0].name] = crossing_time
        for index in range(len(gates) - 1):  # type: Waypoint
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
