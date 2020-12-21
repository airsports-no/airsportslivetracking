import datetime
import math
from plistlib import Dict
from typing import List, Optional
import cartopy.crs as ccrs
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist

from django.db import models

# Create your models here.
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django_countries.fields import CountryField
from rest_framework.exceptions import ValidationError
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
    colour = models.CharField(max_length=40, blank=True)
    type = models.CharField(max_length=50, blank=True)
    picture = models.ImageField(upload_to='images/aircraft/', null=True, blank=True)

    def __str__(self):
        return self.registration


class Route(models.Model):
    name = models.CharField(max_length=200)
    waypoints = MyPickledObjectField(default=list)
    takeoff_gate = MyPickledObjectField(default=None, null=True)
    landing_gate = MyPickledObjectField(default=None, null=True)

    def __str__(self):
        return self.name

    @classmethod
    def create(cls, name: str, waypoints: List[Dict]) -> "Route":
        waypoints = cls.add_gate_data(waypoints)
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


class CharNullField(models.CharField):
    description = "CharField that stores NULL"

    def get_db_prep_value(self, value, connection=None, prepared=False):
        value = super(CharNullField, self).get_db_prep_value(value, connection, prepared)
        if value == "":
            return None
        else:
            return value


class Person(models.Model):
    first_name = models.CharField(max_length=200)
    last_name = models.CharField(max_length=200)
    email = CharNullField(max_length=60, blank=True, null=True)
    phone = CharNullField(max_length=30, blank=True, null=True)
    picture = models.ImageField(upload_to='images/people/', null=True, blank=True)
    biography = models.TextField(blank=True)
    country = CountryField(blank=True)

    @property
    def country_flag_url(self):
        if self.country:
            return self.country.flag
        return None

    def __str__(self):
        return "{} {}".format(self.first_name, self.last_name)

    @classmethod
    def get_or_create(cls, first_name: Optional[str], last_name: Optional[str], phone: Optional[str],
                      email: Optional[str]) -> Optional["Person"]:
        possible_person = None
        if phone is not None and len(phone) > 0:
            possible_person = Person.objects.filter(phone=phone)
        if (not possible_person or possible_person.count() == 0) and email is not None and len(email) > 0:
            possible_person = Person.objects.filter(email__iexact=email)
        if not possible_person or possible_person.count() == 0:
            if first_name is not None and len(first_name) > 0 and last_name is not None and len(last_name) > 0:
                possible_person = Person.objects.filter(first_name__iexact=first_name,
                                                        last_name__iexact=last_name).first()
                if possible_person is None:
                    return Person.objects.get_or_create(
                        defaults={"phone": phone,
                                  "email": phone},
                        first_name__iexact=first_name,
                        last_name__iexact=last_name)[0]
                return possible_person
            return None
        return possible_person.first()


class Crew(models.Model):
    member1 = models.ForeignKey(Person, on_delete=models.PROTECT, related_name="crewmember_one")
    member2 = models.ForeignKey(Person, on_delete=models.PROTECT, null=True, blank=True, related_name="crewmember_two")

    def __str__(self):
        if self.member2:
            return "{} and {}".format(self.member1, self.member2)
        return "{}".format(self.member1)


class Club(models.Model):
    name = models.CharField(max_length=200)
    country = CountryField(blank=True)
    logo = models.ImageField(upload_to='images/clubs/', null=True, blank=True)

    class Meta:
        unique_together = ("name", "country")

    def __str__(self):
        return self.name

    @property
    def country_flag_url(self):
        if self.country:
            return self.country.flag
        return None


class Team(models.Model):
    aeroplane = models.ForeignKey(Aeroplane, on_delete=models.PROTECT)
    crew = models.ForeignKey(Crew, on_delete=models.PROTECT)
    logo = models.ImageField(upload_to='images/teams/', null=True, blank=True)
    country = CountryField(blank=True)
    club = models.ForeignKey(Club, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return "{} in {}".format(self.crew, self.aeroplane)

    @property
    def country_flag_url(self):
        if self.country:
            return self.country.flag
        return None


class Contest(models.Model):
    DESCENDING = "desc"
    ASCENDING = "asc"
    SORTING_DIRECTION = (
        (DESCENDING, "Descending"),
        (ASCENDING, "Ascending")
    )
    summary_score_sorting_direction = models.CharField(default=ASCENDING, choices=SORTING_DIRECTION,
                                                       help_text="Whether the lowest (ascending) or highest (ascending) score is the best result",
                                                       max_length=50)
    name = models.CharField(max_length=100, unique=True)
    start_time = models.DateTimeField(
        help_text="The start time of the contest. Used for sorting. All navigation tasks should ideally be within this time interval.")
    finish_time = models.DateTimeField(
        help_text="The finish time of the contest. Used for sorting. All navigation tasks should ideally be within this time interval.")

    is_public = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ("-start_time", "-finish_time")


class NavigationTask(models.Model):
    PRECISION = 0
    ANR = 1
    NAVIGATION_TASK_TYPES = (
        (PRECISION, "Precision"),
        # (ANR, "ANR")
    )

    name = models.CharField(max_length=200)
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE)
    calculator_type = models.IntegerField(choices=NAVIGATION_TASK_TYPES, default=PRECISION,
                                          help_text="Supported navigation test calculator types. Different calculators might require different scorecard types, but currently we only support a single calculator.  Value map: {}".format(
                                              NAVIGATION_TASK_TYPES))
    route = models.OneToOneField(Route, on_delete=models.PROTECT)
    start_time = models.DateTimeField(
        help_text="The start time of the navigation test. Not really important, but nice to have")
    finish_time = models.DateTimeField(
        help_text="The finish time of the navigation test. Not really important, but nice to have")
    is_public = models.BooleanField(default=False,
                                    help_text="The navigation test is only viewable by unauthenticated users or users without object permissions if this is True")

    class Meta:
        ordering = ("start_time", "finish_time")

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
    TRACCAR = "traccar"
    TRACKING_SERVICES = (
        (TRACCAR, "Traccar"),
    )
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    navigation_task = models.ForeignKey(NavigationTask, on_delete=models.CASCADE)
    takeoff_time = models.DateTimeField(
        help_text="The time the take of gate (if it exists) should be crossed. Otherwise it is the time power should be applied")
    minutes_to_starting_point = models.FloatField(default=5,
                                                  help_text="The number of minutes from the take-off time until the starting point")
    finished_by_time = models.DateTimeField(
        help_text="The time it is expected that the navigation task has finished and landed (used among other things for knowing when the tracker is busy). Is also used for the gate time for the landing gate")
    air_speed = models.FloatField(default=70, help_text="The planned airspeed for the contestant")
    contestant_number = models.PositiveIntegerField(
        help_text="A unique number for the contestant in this navigation task")
    tracking_service = models.CharField(default=TRACCAR, choices=TRACKING_SERVICES, max_length=30,
                                        help_text="Supported tracking services: {}".format(TRACKING_SERVICES))
    traccar_device_name = models.CharField(max_length=100,
                                           help_text="ID of physical tracking device that will be brought into the plane")
    tracker_start_time = models.DateTimeField(
        help_text="When the tracker is handed to the contestant, can have no changes to the route (e.g. wind and timing) after this.")
    scorecard = models.ForeignKey(Scorecard, on_delete=models.PROTECT,
                                  help_text="Reference to an existing scorecard name. Currently existing scorecards: {}".format(
                                      lambda: ", ".join([str(item) for item in Scorecard.objects.all()])))
    predefined_gate_times = MyPickledObjectField(default=None, null=True, blank=True,
                                                 help_text="Dictionary of gates and their starting times (with time zone)")
    wind_speed = models.FloatField(default=0,
                                   help_text="The navigation test wind speed. This is used to calculate gate times if these are not predefined.")
    wind_direction = models.FloatField(default=0,
                                       help_text="The navigation test wind direction. This is used to calculate gate times if these are not predefined.")

    class Meta:
        unique_together = ("navigation_task", "contestant_number")

    def __str__(self):
        return "{} - {}".format(self.contestant_number, self.team)
        # return "{}: {} in {} ({}, {})".format(self.contestant_number, self.team, self.navigation_task.name, self.takeoff_time,
        #                                       self.finished_by_time)

    def get_groundspeed(self, bearing) -> float:
        return calculate_ground_speed_combined(bearing, self.air_speed, self.wind_speed,
                                               self.wind_direction)

    def clean(self):
        # Validate single-use tracker
        overlapping_trackers = Contestant.objects.filter(tracking_service=self.tracking_service,
                                                         traccar_device_name=self.traccar_device_name,
                                                         tracker_start_time__lte=self.finished_by_time,
                                                         finished_by_time__gte=self.tracker_start_time).exclude(
            pk=self.pk)
        if overlapping_trackers.count() > 0:
            intervals = []
            for contestant in overlapping_trackers:
                smallest_end = min(contestant.finished_by_time, self.finished_by_time)
                largest_start = max(contestant.tracker_start_time, self.tracker_start_time)
                intervals.append((largest_start.isoformat(), smallest_end.isoformat()))
            raise ValidationError(
                "The tracker '{}' is in use by other contestants for the intervals: {}".format(self.traccar_device_name,
                                                                                               intervals))
        # Validate takeoff time after tracker start
        if self.tracker_start_time > self.takeoff_time:
            raise ValidationError("Tracker start time '{}' is after takeoff time '{}' for contestant number {}".format(
                self.tracker_start_time, self.takeoff_time, self.contestant_number))

    @property
    def gate_times(self) -> Dict:
        if self.predefined_gate_times is not None and len(self.predefined_gate_times) > 0:
            return self.predefined_gate_times
        gates = self.navigation_task.route.waypoints
        if len(gates) == 0:
            return {}
        crossing_times = {}
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

    def get_gate_time_offset(self, gate_name):
        planned = self.gate_times.get(gate_name)
        actual = self.contestanttrack.gate_actual_times.get(gate_name)
        if planned and actual:
            return (actual - planned).total_seconds()
        return None

    @gate_times.setter
    def gate_times(self, value):
        self.predefined_gate_times = value

    @classmethod
    def get_contestant_for_device_at_time(cls, device: str, stamp: datetime.datetime):
        try:
            # Device belongs to contestant from 30 minutes before takeoff
            return cls.objects.get(traccar_device_name=device, tracker_start_time__lte=stamp,
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
    gate_actual_times = MyPickledObjectField(default=dict)

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

    def update_gate_time(self, gate_name: str, passing_time: datetime.datetime):
        self.gate_actual_times[gate_name] = passing_time
        self.save()


########## Scoring portal models ##########
class Task(models.Model):
    """
    Models a generic task for which we want to store scores
    """
    DESCENDING = "desc"
    ASCENDING = "asc"
    SORTING_DIRECTION = (
        (DESCENDING, "Descending"),
        (ASCENDING, "Ascending")
    )
    summary_score_sorting_direction = models.CharField(default=ASCENDING, choices=SORTING_DIRECTION,
                                                       help_text="Whether the lowest (ascending) or highest (ascending) score is the best result",
                                                       max_length=50)
    name = models.CharField(max_length=100)
    heading = models.CharField(max_length=100)
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE)
    default_sorting = models.ForeignKey("TaskTest", related_name="default_sort", null=True, on_delete=models.SET_NULL)

    class Meta:
        unique_together = ("name", "contest")


class TaskTest(models.Model):
    """
    Models and individual test (e.g. landing one, landing two, or landing three that is part of a task. It includes
    the configuration for how the score is displayed for the test.
    """
    DESCENDING = "desc"
    ASCENDING = "asc"
    SORTING_DIRECTION = (
        (DESCENDING, "Descending"),
        (ASCENDING, "Ascending")
    )
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    heading = models.CharField(max_length=100)
    sorting = models.CharField(default=ASCENDING, choices=SORTING_DIRECTION,
                               help_text="Whether the lowest (ascending) or highest (ascending) score is the best result",
                               max_length=50)
    index = models.IntegerField(
        help_text="The index of the task when displayed as columns in a table. Indexes are sorted in ascending order to determine column order")

    class Meta:
        unique_together = ("name", "task")


class TaskSummary(models.Model):
    """
    Summary score for all tests inside a task for a team
    """
    team = models.ForeignKey(Team, on_delete=models.PROTECT)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    points = models.FloatField()


class ContestSummary(models.Model):
    """
    Summary score for the entire contest for a team
    """
    team = models.ForeignKey(Team, on_delete=models.PROTECT)
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE)
    points = models.FloatField()


class TeamTestScore(models.Model):
    """
    Represents the score a team received for a test
    """
    team = models.ForeignKey(Team, on_delete=models.PROTECT)
    task_test = models.ForeignKey(TaskTest, on_delete=models.CASCADE)
    points = models.FloatField()

    class Meta:
        unique_together = ("team", "task_test")


@receiver(post_save, sender=Contestant)
def create_contestant_track_if_not_exists(sender, instance: Contestant, **kwargs):
    ContestantTrack.objects.get_or_create(contestant=instance)


@receiver(pre_save, sender=Contestant)
def validate_contestant(sender, instance: Contestant, **kwargs):
    instance.clean()


@receiver(post_delete, sender=NavigationTask)
def remove_route_from_deleted_navigation_task(sender, instance: NavigationTask, **kwargs):
    instance.route.delete()


@receiver(post_delete, sender=Contestant)
def remove_track_from_influx(sender, instance: NavigationTask, **kwargs):
    from influx_facade import InfluxFacade
    influx = InfluxFacade()
    influx.clear_data_for_contestant(instance.pk)
