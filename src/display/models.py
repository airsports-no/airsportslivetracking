import datetime
import logging
import random
from plistlib import Dict
from random import choice
from string import ascii_uppercase, digits, ascii_lowercase
from typing import List, Optional, Tuple

import eval7 as eval7
from django import core
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.core.validators import MaxValueValidator, MinValueValidator

from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django_use_email_as_username.models import BaseUser, BaseUserManager
from guardian.mixins import GuardianUserMixin
from multiselectfield import MultiSelectField
from timezone_field import TimeZoneField
# Create your models here.
from django.db.models.signals import post_save, pre_save, post_delete, pre_delete
from django.dispatch import receiver
from django_countries.fields import CountryField
from phonenumber_field.modelfields import PhoneNumberField
from rest_framework.exceptions import ValidationError
from solo.models import SingletonModel

from display.calculate_gate_times import calculate_and_get_relative_gate_times
from display.coordinate_utilities import bearing_difference
from display.my_pickled_object_field import MyPickledObjectField
from display.poker_cards import PLAYING_CARDS
from display.waypoint import Waypoint
from display.wind_utilities import calculate_ground_speed_combined
from display.traccar_factory import get_traccar_instance
from live_tracking_map.settings import SERVER_ROOT

from phonenumbers.phonenumber import PhoneNumber

TRACCAR = "traccar"
TRACKING_SERVICES = (
    (TRACCAR, "Traccar"),
)

logger = logging.getLogger(__name__)


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


class MyUser(BaseUser, GuardianUserMixin):
    username = models.CharField(max_length=50, default="not_applicable")
    objects = BaseUserManager()


class Aeroplane(models.Model):
    registration = models.CharField(max_length=20)
    colour = models.CharField(max_length=40, blank=True)
    type = models.CharField(max_length=50, blank=True)
    picture = models.ImageField(upload_to='images/aircraft/', null=True, blank=True)

    def __str__(self):
        return self.registration


class Route(models.Model):
    name = models.CharField(max_length=200)
    use_procedure_turns = models.BooleanField(default=True, blank=True)
    rounded_corners = models.BooleanField(default=False, blank=True)
    waypoints = MyPickledObjectField(default=list)
    takeoff_gate = MyPickledObjectField(default=None, null=True)
    landing_gate = MyPickledObjectField(default=None, null=True)

    def clean(self):
        for index in range(len(self.waypoints) - 1):
            waypoint = self.waypoints[index]  # type: Waypoint
            if waypoint.distance_next < 1852 and self.rounded_corners:
                raise ValidationError(
                    f"Distance from {waypoint.name} to {self.waypoints[index + 1].name} should be greater than 1 NM when using rounded corners. Perhaps there is an error in your route file.")
            if waypoint.distance_next < 1852 / 2 and self.waypoints[index + 1].type != "secret" and waypoint.type != "secret":
                raise ValidationError(
                    f"Distance from {waypoint.name} to {self.waypoints[index + 1].name} should be greater than 0.5 NM"
                )

    def __str__(self):
        return self.name


class Prohibited(models.Model):
    name = models.CharField(max_length=200)
    route = models.ForeignKey(Route, on_delete=models.CASCADE)
    path = MyPickledObjectField(default=list)
    type = models.CharField(max_length=100, blank=True, default="")


def get_next_turning_point(waypoints: List, gate_name: str) -> Waypoint:
    found_current = False
    for gate in waypoints:
        if found_current:
            return gate
        if gate.name == gate_name:
            found_current = True


def is_procedure_turn(bearing1, bearing2) -> bool:
    """
    Return True if the turn is more than 90 degrees

    :param bearing1: degrees
    :param bearing2: degrees
    :return:
    """
    return abs(bearing_difference(bearing1, bearing2)) > 90


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
    email = models.EmailField()
    phone = PhoneNumberField(blank=True, null=True)
    creation_time = models.DateTimeField(auto_now_add=True,
                                         help_text="Used to figure out when a not validated personal and user should be deleted")
    validated = models.BooleanField(default=True,
                                    help_text="Usually true, but set to false for persons created automatically during "
                                              "app API login. This is used to signify that the user profile must be "
                                              "updatedfocus of. If this remains false for more than a few days, the person "
                                              "object and corresponding user will be deleted from the system.  This "
                                              "must therefore be set to True when submitting an updated profile from "
                                              "the app.")
    app_tracking_id = models.CharField(max_length=28, editable=False,
                                       help_text="An automatically generated tracking ID which is distributed to the tracking app")
    simulator_tracking_id = models.CharField(max_length=28, editable=False,
                                             help_text="An automatically generated tracking ID which is distributed to the simulator integration. Persons or contestants identified by this field should not be displayed on the global map.")
    app_aircraft_registration = models.CharField(max_length=100, default="", blank=True,
                                                 help_text="The display name of person positions on the global tracking map (should be an aircraft registration")
    picture = models.ImageField(upload_to='images/people/', null=True, blank=True)
    biography = models.TextField(blank=True)
    country = CountryField(blank=True)

    @property
    def phone_country_prefix(self):
        phone = self.phone  # type: PhoneNumber
        return phone.country_code if phone else ""

    @property
    def phone_national_number(self):
        phone = self.phone  # type: PhoneNumber
        return phone.national_number if phone else ""

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
                    return Person.objects.create(
                        phone=phone,
                        email=email,
                        first_name=first_name,
                        last_name=last_name
                    )
                return possible_person
            return None
        return possible_person.first()

    def validate(self):
        if Person.objects.filter(email=self.email).exclude(pk=self.pk).exists():
            raise ValidationError("A person with this email already exists")


class Crew(models.Model):
    member1 = models.ForeignKey(Person, on_delete=models.PROTECT, related_name="crewmember_one")
    member2 = models.ForeignKey(Person, on_delete=models.PROTECT, null=True, blank=True, related_name="crewmember_two")

    def validate(self):
        if Crew.objects.filter(member1=self.member1, member2=self.member2).exclude(pk=self.pk).exists():
            raise ValidationError("A crew with this email already exists")

    def __str__(self):
        if self.member2:
            return "{} and {}".format(self.member1, self.member2)
        return "{}".format(self.member1)


class Club(models.Model):
    name = models.CharField(max_length=200)
    country = CountryField(blank=True)
    logo = models.ImageField(upload_to='images/clubs/', null=True, blank=True)

    # class Meta:
    #     unique_together = ("name", "country")

    def validate(self):
        if Club.objects.filter(name=self.name).exclude(pk=self.pk).exists():
            raise ValidationError("A club with this email already exists")

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


class ContestTeam(models.Model):
    contest = models.ForeignKey("Contest", on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    air_speed = models.FloatField(default=70, help_text="The planned airspeed for the contestant")
    tracking_service = models.CharField(default=TRACCAR, choices=TRACKING_SERVICES, max_length=30,
                                        help_text="Supported tracking services: {}".format(TRACKING_SERVICES))
    tracker_device_id = models.CharField(max_length=100,
                                         help_text="ID of physical tracking device that will be brought into the plane",
                                         blank=True)

    class Meta:
        unique_together = ("contest", "team")

    def __str__(self):
        return str(self.team)

    def get_tracker_id(self) -> str:
        if self.tracker_device_id is not None and len(self.tracker_device_id) > 0:
            return self.tracker_device_id
        if self.team.crew.member1.app_tracking_id is not None and len(self.team.crew.member1.app_tracking_id) > 0:
            return self.team.crew.member1.app_tracking_id
        if self.team.crew.member2 is not None and self.team.crew.member2.app_tracking_id is not None and len(
                self.team.crew.member2.app_tracking_id) > 0:
            return self.team.crew.member2.app_tracking_id
        logger.error(f"ContestTeam {self.team} for contest {self.contest} does not have a tracker ID")
        return ""


class Contest(models.Model):
    DESCENDING = "desc"
    ASCENDING = "asc"
    SORTING_DIRECTION = (
        (DESCENDING, "Descending"),
        (ASCENDING, "Ascending")
    )
    summary_score_sorting_direction = models.CharField(default=ASCENDING, choices=SORTING_DIRECTION,
                                                       help_text="Whether the lowest (ascending) or highest (ascending) score is the best result",
                                                       max_length=50, blank=True)
    name = models.CharField(max_length=100, unique=True)
    time_zone = TimeZoneField()
    latitude = models.FloatField(default=0, help_text="Approximate location of contest, used for global map display",
                                 blank=True)
    longitude = models.FloatField(default=0, help_text="Approximate location of contest, used for global map display",
                                  blank=True)
    start_time = models.DateTimeField(
        help_text="The start time of the contest. Used for sorting. All navigation tasks should ideally be within this time interval.")
    finish_time = models.DateTimeField(
        help_text="The finish time of the contest. Used for sorting. All navigation tasks should ideally be within this time interval.")
    contest_teams = models.ManyToManyField(Team, blank=True, through=ContestTeam)
    is_public = models.BooleanField(default=False)
    contest_website = models.CharField(help_text="URL to contest website", blank=True, default="", max_length=300)
    header_image = models.ImageField(upload_to='images/contests/', null=True, blank=True,
                                     help_text="Nice image that is shown on top of the event information on the map.")
    logo = models.ImageField(upload_to='images/contestlogos/', null=True, blank=True,
                             help_text="Quadratic logo that is shown next to the event in the event list")

    def __str__(self):
        return self.name

    class Meta:
        ordering = ("-start_time", "-finish_time")

    def update_position_if_not_set(self, latitude, longitude):
        if self.latitude == 0 and self.longitude == 0:
            self.latitude = latitude
            self.longitude = longitude
            self.save()


class NavigationTask(models.Model):
    PRECISION = 'precision'
    ANR_CORRIDOR = 'anr_corridor'
    POKER = 'poker'
    LANDING = "landing"
    NAVIGATION_TASK_TYPES = (
        (PRECISION, "Precision"),
        (ANR_CORRIDOR, "ANR Corridor"),
        (POKER, "Poker run"),
        (LANDING, "Landing")
    )
    name = models.CharField(max_length=200)
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE)
    route = models.OneToOneField(Route, on_delete=models.PROTECT)
    scorecard = models.ForeignKey("Scorecard", on_delete=models.PROTECT,
                                  help_text="Reference to an existing scorecard name. Currently existing scorecards: {}".format(
                                      lambda: ", ".join([str(item) for item in Scorecard.objects.all()])))
    track_score_override = models.ForeignKey("TrackScoreOverride", on_delete=models.SET_NULL, null=True, blank=True)
    gate_score_override = models.ManyToManyField("GateScoreOverride", blank=True)
    start_time = models.DateTimeField(
        help_text="The start time of the navigation test. Not really important, but nice to have")
    finish_time = models.DateTimeField(
        help_text="The finish time of the navigation test. Not really important, but nice to have")
    is_public = models.BooleanField(default=False,
                                    help_text="The navigation test is only viewable by unauthenticated users or users without object permissions if this is True")
    wind_speed = models.FloatField(default=0,
                                   help_text="The navigation test wind speed. This is used to calculate gate times if these are not predefined.",
                                   validators=[
                                       MaxValueValidator(360), MinValueValidator(0)
                                   ])
    wind_direction = models.FloatField(default=0,
                                       help_text="The navigation test wind direction. This is used to calculate gate times if these are not predefined.",
                                       validators=[
                                           MaxValueValidator(40), MinValueValidator(0)
                                       ])
    minutes_to_starting_point = models.FloatField(default=5,
                                                  help_text="The number of minutes from the take-off time until the starting point")
    minutes_to_landing = models.FloatField(default=30,
                                           help_text="The number of minutes from the finish point to the contestant should have landed")

    @property
    def is_poker_run(self) -> bool:
        return self.POKER in self.scorecard.task_type

    @property
    def tracking_link(self) -> str:
        return SERVER_ROOT + reverse("frontend_view_map", kwargs={"pk": self.pk})

    class Meta:
        ordering = ("start_time", "finish_time")

    def __str__(self):
        return "{}: {}".format(self.name, self.start_time.isoformat())


class Scorecard(models.Model):
    PRECISION = "precision"
    ANR_CORRIDOR = "anr_corridor"
    POKER = "poker"
    LANDING = "landing"
    CALCULATORS = (
        (PRECISION, "Precision"),
        (ANR_CORRIDOR, "ANR Corridor"),
        (POKER, "Poker run"),
        (LANDING, "Landing")
    )

    name = models.CharField(max_length=100, default="default", unique=True)
    calculator = models.CharField(choices=CALCULATORS, default=PRECISION, max_length=20,
                                  help_text="Supported calculator types")
    task_type = MultiSelectField(choices=NavigationTask.NAVIGATION_TASK_TYPES, default=list)
    use_procedure_turns = models.BooleanField(default=True, blank=True)
    backtracking_penalty = models.FloatField(default=200)
    backtracking_bearing_difference = models.FloatField(default=90)
    backtracking_grace_time_seconds = models.FloatField(default=5)
    backtracking_maximum_penalty = models.FloatField(default=-1,
                                                     help_text="Negative numbers means the maximum is ignored")
    below_minimum_altitude_penalty = models.FloatField(default=500)
    below_minimum_altitude_maximum_penalty = models.FloatField(default=500)

    takeoff_gate_score = models.ForeignKey("GateScore", on_delete=models.SET_NULL, null=True, blank=True,
                                           related_name="takeoff")
    landing_gate_score = models.ForeignKey("GateScore", on_delete=models.SET_NULL, null=True, blank=True,
                                           related_name="landing")
    turning_point_gate_score = models.ForeignKey("GateScore", on_delete=models.SET_NULL, null=True, blank=True,
                                                 related_name="turning_point")
    starting_point_gate_score = models.ForeignKey("GateScore", on_delete=models.SET_NULL, null=True, blank=True,
                                                  related_name="starting")
    finish_point_gate_score = models.ForeignKey("GateScore", on_delete=models.SET_NULL, null=True, blank=True,
                                                related_name="finish")
    secret_gate_score = models.ForeignKey("GateScore", on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name="secret")

    prohibited_zone_penalty = models.FloatField(default=200,
                                                help_text="Penalty for entering prohibited zone such as controlled airspace or other prohibited areas")

    ##### ANR Corridor
    corridor_width = models.FloatField(default=0.3, help_text="The corridor width for ANR tasks")
    corridor_grace_time = models.IntegerField(default=5, help_text="The corridor grace time for ANR tasks")
    corridor_outside_penalty = models.FloatField(default=3,
                                                 help_text="The penalty awarded for leaving the ANR corridor")
    corridor_maximum_penalty = models.FloatField(default=-1, help_text="The maximum penalty for leaving the corridor")

    def __str__(self):
        return self.name

    def get_gate_scorecard(self, gate_type: str) -> "GateScore":
        if gate_type == "tp":
            gate_score = self.turning_point_gate_score
        elif gate_type in ("sp", "isp"):
            gate_score = self.starting_point_gate_score
        elif gate_type in ("fp", "ifp"):
            gate_score = self.finish_point_gate_score
        elif gate_type == "secret":
            gate_score = self.secret_gate_score
        elif gate_type in ("to", "ito"):
            gate_score = self.takeoff_gate_score
        elif gate_type in ("ldg", "ildg"):
            gate_score = self.landing_gate_score
        else:
            raise ValueError("Unknown gate type '{}'".format(gate_type))
        if gate_score is None:
            raise ValueError("Undefined gate score for '{}'".format(gate_type))
        return gate_score

    def get_gate_score_override(self, gate_type: str, contestant: "Contestant"):
        return contestant.get_gate_score_override(gate_type)

    def get_backtracking_penalty(self, contestant: "Contestant"):
        if contestant:
            override = contestant.get_track_score_override()
            if override:
                if override.bad_course_penalty is not None:
                    return override.bad_course_penalty
        return self.backtracking_penalty

    def get_maximum_backtracking_penalty(self, contestant: "Contestant"):
        if contestant:
            override = contestant.get_track_score_override()
            if override:
                if override.bad_course_maximum_penalty is not None:
                    return override.bad_course_maximum_penalty
        return self.backtracking_maximum_penalty

    def get_backtracking_grace_time_seconds(self, contestant: "Contestant"):
        if contestant:
            override = contestant.get_track_score_override()
            if override:
                if override.bad_course_grace_time is not None:
                    return override.bad_course_grace_time
        return self.backtracking_grace_time_seconds

    def get_prohibited_zone_penalty(self, contestant: "Contestant"):
        if contestant:
            override = contestant.get_track_score_override()
            if override:
                if override.prohibited_zone_penalty is not None:
                    return override.prohibited_zone_penalty
        return self.prohibited_zone_penalty

    def get_gate_timing_score_for_gate_type(self, gate_type: str, contestant: "Contestant",
                                            planned_time: datetime.datetime,
                                            actual_time: Optional[datetime.datetime]) -> float:
        gate_score = self.get_gate_scorecard(gate_type)
        return gate_score.calculate_score(planned_time, actual_time,
                                          self.get_gate_score_override(gate_type, contestant))

    def get_maximum_timing_penalty_for_gate_type(self, gate_type: str,
                                                 contestant: "Contestant") -> float:
        gate_score = self.get_gate_scorecard(gate_type)
        return gate_score.get_maximum_penalty(self.get_gate_score_override(gate_type, contestant))

    def get_procedure_turn_penalty_for_gate_type(self, gate_type: str,
                                                 contestant: "Contestant") -> float:
        gate_score = self.get_gate_scorecard(gate_type)
        return gate_score.get_missed_procedure_turn_penalty(self.get_gate_score_override(gate_type, contestant))

    def get_bad_crossing_extended_gate_penalty_for_gate_type(self, gate_type: str,
                                                             contestant: "Contestant") -> float:
        gate_score = self.get_gate_scorecard(gate_type)
        return gate_score.get_bad_crossing_extended_gate_penalty(self.get_gate_score_override(gate_type, contestant))

    def get_extended_gate_width_for_gate_type(self, gate_type: str,
                                              contestant: "Contestant") -> float:
        gate_score = self.get_gate_scorecard(gate_type)
        return gate_score.extended_gate_width

    def get_backtracking_after_steep_gate_grace_period_seconds(self, gate_type: str,
                                                               contestant: "Contestant") -> float:
        gate_score = self.get_gate_scorecard(gate_type)
        return gate_score.backtracking_after_steep_gate_grace_period_seconds

    def get_backtracking_after_gate_grace_period_nm(self, gate_type: str,
                                                    contestant: "Contestant") -> float:
        gate_score = self.get_gate_scorecard(gate_type)
        return gate_score.backtracking_after_gate_grace_period_nm

    ### ANR Corridor
    def get_corridor_width(self, contestant: "Contestant"):
        if contestant:
            override = contestant.get_track_score_override()
            if override:
                if override.corridor_width is not None:
                    return override.corridor_width
        return self.corridor_width

    def get_corridor_grace_time(self, contestant: "Contestant"):
        if contestant:
            override = contestant.get_track_score_override()
            if override:
                if override.corridor_grace_time is not None:
                    return override.corridor_grace_time
        return self.corridor_grace_time

    def get_corridor_outside_penalty(self, contestant: "Contestant"):
        if contestant:
            override = contestant.get_track_score_override()
            if override:
                if override.corridor_outside_penalty is not None:
                    return override.corridor_outside_penalty
        return self.corridor_outside_penalty

    def get_corridor_outside_maximum_penalty(self, contestant: "Contestant"):
        if contestant:
            override = contestant.get_track_score_override()
            if override:
                if override.corridor_maximum_penalty is not None:
                    return override.corridor_maximum_penalty
        return self.corridor_maximum_penalty


class GateScore(models.Model):
    name = models.CharField(max_length=100, default="")
    extended_gate_width = models.FloatField(default=0,
                                            help_text="For SP it is 2 (1 nm each side), for tp with procedure turn it is 6")
    bad_crossing_extended_gate_penalty = models.FloatField(default=200)
    graceperiod_before = models.FloatField(default=3)
    graceperiod_after = models.FloatField(default=3)
    maximum_penalty = models.FloatField(default=100)
    penalty_per_second = models.FloatField(default=2)
    missed_penalty = models.FloatField(default=100)
    bad_course_crossing_penalty = models.FloatField(default=0)
    missed_procedure_turn_penalty = models.FloatField(default=200)
    backtracking_after_steep_gate_grace_period_seconds = models.FloatField(default=0)
    backtracking_after_gate_grace_period_nm = models.FloatField(default=0.5)

    def get_missed_penalty(self, score_override: Optional["GateScoreOverride"]):
        if score_override and score_override.checkpoint_not_found is not None:
            return score_override.checkpoint_not_found
        return self.missed_penalty

    def get_graceperiod_before(self, score_override: Optional["GateScoreOverride"]):
        if score_override and score_override.checkpoint_grace_period_before is not None:
            return score_override.checkpoint_grace_period_before
        return self.graceperiod_before

    def get_graceperiod_after(self, score_override: Optional["GateScoreOverride"]):
        if score_override and score_override.checkpoint_grace_period_after is not None:
            return score_override.checkpoint_grace_period_after
        return self.graceperiod_after

    def get_maximum_penalty(self, score_override: Optional["GateScoreOverride"]):
        if score_override and score_override.checkpoint_maximum_penalty is not None:
            return score_override.checkpoint_maximum_penalty
        return self.maximum_penalty

    def get_bad_course_crossing_penalty(self, score_override: Optional["GateScoreOverride"]):
        if score_override and score_override.bad_course_penalty is not None:
            return score_override.bad_course_penalty
        return self.bad_course_crossing_penalty

    def get_bad_crossing_extended_gate_penalty(self, score_override: Optional["GateScoreOverride"]):
        if score_override and score_override.bad_crossing_extended_gate_penalty is not None:
            return score_override.bad_crossing_extended_gate_penalty
        return self.bad_crossing_extended_gate_penalty

    def get_missed_procedure_turn_penalty(self, score_override: Optional["GateScoreOverride"]):
        if score_override and score_override.missing_procedure_turn_penalty is not None:
            return score_override.missing_procedure_turn_penalty
        return self.missed_procedure_turn_penalty

    def get_penalty_per_second(self, score_override: Optional["GateScoreOverride"]):
        if score_override and score_override.checkpoint_penalty_per_second is not None:
            return score_override.checkpoint_penalty_per_second
        return self.penalty_per_second

    def calculate_score(self, planned_time: datetime.datetime, actual_time: Optional[datetime.datetime],
                        score_override: Optional["GateScoreOverride"]) -> float:
        """

        :param planned_time:
        :param actual_time: If None the gate is missed
        :return:
        """
        if actual_time is None:
            return self.get_missed_penalty(score_override)
        time_difference = (actual_time - planned_time).total_seconds()
        if -self.get_graceperiod_before(score_override) < time_difference < self.get_graceperiod_after(score_override):
            return 0
        else:
            if time_difference > 0:
                grace_limit = self.get_graceperiod_after(score_override)
            else:
                grace_limit = self.get_graceperiod_before(score_override)
            score = (round(abs(time_difference) - grace_limit)) * self.get_penalty_per_second(score_override)
            if self.get_maximum_penalty(score_override) >= 0:
                return min(self.get_maximum_penalty(score_override), score)
            return score


class TrackScoreOverride(models.Model):
    bad_course_grace_time = models.FloatField(default=None, blank=True, null=True,
                                              help_text="The number of seconds a bad course can be tolerated before generating a penalty")
    bad_course_penalty = models.FloatField(default=None, blank=True, null=True,
                                           help_text="A amount of points awarded for a bad course")
    bad_course_maximum_penalty = models.FloatField(default=None, blank=True, null=True,
                                                   help_text="A amount of points awarded for a bad course")
    prohibited_zone_penalty = models.FloatField(default=200,
                                                help_text="Penalty for entering prohibited zone such as controlled airspace or other prohibited areas")
    ### ANR Corridor
    corridor_width = models.FloatField(default=None, blank=True, null=True,
                                       help_text="The width of the ANR corridor")
    corridor_grace_time = models.FloatField(default=None, blank=True, null=True,
                                            help_text="The grace time of the ANR corridor")
    corridor_outside_penalty = models.FloatField(default=None, blank=True, null=True,
                                                 help_text="The penalty awarded for leaving the ANR corridor")
    corridor_maximum_penalty = models.FloatField(default=None, blank=True, null=True,
                                                 help_text="The maximum penalty for leaving the corridor")

    def __str__(self):
        return "Track score override for {}".format(self.navigationtask_set.first())


class GateScoreOverride(models.Model):
    for_gate_types = MyPickledObjectField(default=list,
                                          help_text="List of gates types (eg. tp, secret, sp) that should be overridden (all lower case)")
    checkpoint_grace_period_before = models.FloatField(default=None, blank=True, null=True,
                                                       help_text="The time before a checkpoint that no penalties are awarded")
    checkpoint_grace_period_after = models.FloatField(default=None, blank=True, null=True,
                                                      help_text="The time after a checkpoint that no penalties are awarded")
    checkpoint_penalty_per_second = models.FloatField(default=None, blank=True, null=True,
                                                      help_text="The number of points awarded per second outside of the grace period")
    checkpoint_maximum_penalty = models.FloatField(default=None, blank=True, null=True,
                                                   help_text="The maximum number of penalty points awarded for checkpoint timing")
    checkpoint_not_found = models.FloatField(default=None, blank=True, null=True,
                                             help_text="The penalty for missing a checkpoint")
    missing_procedure_turn_penalty = models.FloatField(default=None, blank=True, null=True,
                                                       help_text="The penalty for missing a procedure turn")
    bad_course_penalty = models.FloatField(default=None, blank=True, null=True,
                                           help_text="A amount of points awarded for crossing the gate in the wrong direction (e.g. for landing or takeoff)")
    bad_crossing_extended_gate_penalty = models.FloatField(default=None, blank=True, null=True,
                                                           help_text="The penalty awarded when crossing the extended gate in the wrong direction (typically used for start gate)")

    def __str__(self):
        return "Gate score override for {}".format(self.navigationtask_set.first())


class Contestant(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    navigation_task = models.ForeignKey(NavigationTask, on_delete=models.CASCADE)
    adaptive_start = models.BooleanField(default=False,
                                         help_text="If true, takeoff time and minutes to starting point is ignored. Start time is set to the closest minute to the time crossing the starting line. This is typically used for a case where it is difficult to control the start time because of external factors such as ATC.")
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
    tracker_device_id = models.CharField(max_length=100,
                                         help_text="ID of physical tracking device that will be brought into the plane",
                                         blank=True)
    tracker_start_time = models.DateTimeField(
        help_text="When the tracker is handed to the contestant, can have no changes to the route (e.g. wind and timing) after this.")
    competition_class_longform = models.CharField(max_length=100,
                                                  help_text="The class of the contestant, e.g. beginner, professional, et cetera",
                                                  blank=True, null=True)
    competition_class_shortform = models.CharField(max_length=100,
                                                   help_text="The abbreviated class of the contestant, e.g. beginner, professional, et cetera",
                                                   blank=True, null=True)
    track_score_override = models.ForeignKey(TrackScoreOverride, on_delete=models.SET_NULL, null=True, blank=True)
    calculator_started = models.BooleanField(default=False,
                                             help_text="Set to true when the calculator has started. After this point it is not permitted to change the contestant")
    gate_score_override = models.ManyToManyField(GateScoreOverride,blank=True)
    predefined_gate_times = MyPickledObjectField(default=None, null=True, blank=True,
                                                 help_text="Dictionary of gates and their starting times (with time zone)")
    wind_speed = models.FloatField(default=0,
                                   help_text="The navigation test wind speed. This is used to calculate gate times if these are not predefined.",
                                   validators=[
                                       MaxValueValidator(40), MinValueValidator(0)
                                   ])
    wind_direction = models.FloatField(default=0,
                                       help_text="The navigation test wind direction. This is used to calculate gate times if these are not predefined.",
                                       validators=[
                                           MaxValueValidator(360), MinValueValidator(0)
                                       ])
    annotation_index = models.IntegerField(default=0, help_text="Internal housekeeping for annotation transmission")

    class Meta:
        unique_together = ("navigation_task", "contestant_number")
        ordering = ("takeoff_time",)

    def save(self, **kwargs):
        self.tracker_device_id = self.tracker_device_id.strip()
        if self.tracking_service == TRACCAR:
            traccar = get_traccar_instance()
            traccar.get_or_create_device(self.tracker_device_id, self.tracker_device_id)
        super().save(**kwargs)

    def __str__(self):
        return "{} - {}".format(self.contestant_number, self.team)
        # return "{}: {} in {} ({}, {})".format(self.contestant_number, self.team, self.navigation_task.name, self.takeoff_time,
        #                                       self.finished_by_time)

    def calculate_progress(self, latest_time: datetime) -> float:
        if NavigationTask.POKER in self.navigation_task.scorecard.task_type:
            return 100 * self.contestanttrack.playingcard_set.all().count() / 5
        if NavigationTask.LANDING in self.navigation_task.scorecard.task_type:
            # A progress of zero will also leave estimated score blank
            return 0
        route_progress = 100
        if len(self.navigation_task.route.waypoints) > 0 and not self.contestanttrack.calculator_finished:
            first_gate = self.navigation_task.route.waypoints[0]
            last_gate = self.navigation_task.route.waypoints[-1]

            first_gate_time = self.gate_times[first_gate.name]
            last_gate_time = self.gate_times[last_gate.name]
            route_duration = (last_gate_time - first_gate_time).total_seconds()
            route_duration_progress = (latest_time - first_gate_time).total_seconds()
            route_progress = 100 * route_duration_progress / route_duration
        return route_progress

    def get_groundspeed(self, bearing) -> float:
        return calculate_ground_speed_combined(bearing, self.air_speed, self.wind_speed,
                                               self.wind_direction)

    def clean(self):
        # Validate single-use tracker
        overlapping_trackers = Contestant.objects.filter(tracking_service=self.tracking_service,
                                                         tracker_device_id=self.get_tracker_id(),
                                                         tracker_start_time__lte=self.finished_by_time,
                                                         finished_by_time__gte=self.tracker_start_time).exclude(
            pk=self.pk)
        if overlapping_trackers.exists():
            intervals = []
            for contestant in overlapping_trackers:
                smallest_end = min(contestant.finished_by_time, self.finished_by_time)
                largest_start = max(contestant.tracker_start_time, self.tracker_start_time)
                intervals.append((largest_start.isoformat(), smallest_end.isoformat()))
            raise ValidationError(
                "The tracker '{}' is in use by other contestants for the intervals: {}".format(self.tracker_device_id,
                                                                                               intervals))
        # Validate that persons are not part of other contestants for the same interval
        overlapping1 = Contestant.objects.filter(
            Q(team__crew__member1=self.team.crew.member1) | Q(team__crew__member2=self.team.crew.member1),
            tracker_start_time__lte=self.finished_by_time,
            finished_by_time__gte=self.tracker_start_time).exclude(pk=self.pk)
        if overlapping1.exists():
            intervals = []
            for contestant in overlapping1:
                smallest_end = min(contestant.finished_by_time, self.finished_by_time)
                largest_start = max(contestant.tracker_start_time, self.tracker_start_time)
                intervals.append((largest_start.isoformat(), smallest_end.isoformat()))
            raise ValidationError(
                f"The pilot '{self.team.crew.member1}' is competing as a different contestant for the intervals: {intervals}")

        if self.team.crew.member2 is not None:
            overlapping2 = Contestant.objects.filter(
                Q(team__crew__member1=self.team.crew.member2) | Q(team__crew__member2=self.team.crew.member2),
                tracker_start_time__lte=self.finished_by_time,
                finished_by_time__gte=self.tracker_start_time).exclude(pk=self.pk)
            if overlapping2.exists():
                intervals = []
                for contestant in overlapping2:
                    smallest_end = min(contestant.finished_by_time, self.finished_by_time)
                    largest_start = max(contestant.tracker_start_time, self.tracker_start_time)
                    intervals.append((largest_start.isoformat(), smallest_end.isoformat()))
                raise ValidationError(
                    f"The copilot '{self.team.crew.member2}' is competing as a different contestant for the intervals: {intervals}")

        # Validate takeoff time after tracker start
        if self.tracker_start_time > self.takeoff_time:
            raise ValidationError("Tracker start time '{}' is after takeoff time '{}' for contestant number {}".format(
                self.tracker_start_time, self.takeoff_time, self.contestant_number))
        # Validate no timing changes after calculator start
        if self.pk is not None:
            original = Contestant.objects.get(pk=self.pk)
            if original.calculator_started:
                if original.takeoff_time != self.takeoff_time:
                    raise ValidationError(
                        f"Calculator has started for {self}, it is not possible to change takeoff time")
                if original.tracker_start_time != self.tracker_start_time:
                    raise ValidationError(
                        f"Calculator has started for {self}, it is not possible to change tracker start time")
                if original.wind_speed != self.wind_speed:
                    raise ValidationError(f"Calculator has started for {self}, it is not possible to change wind speed")
                if original.wind_direction != self.wind_direction:
                    raise ValidationError(
                        f"Calculator has started for {self}, it is not possible to change wind direction")
                if original.adaptive_start != self.adaptive_start:
                    raise ValidationError(
                        f"Calculator has started for {self}, it is not possible to change adaptive start")
                if original.minutes_to_starting_point != self.minutes_to_starting_point:
                    raise ValidationError(
                        f"Calculator has started for {self}, it is not possible to change minutes to starting point")

    def calculate_and_get_gate_times(self, start_point_override: Optional[datetime.datetime] = None) -> Dict:
        gates = self.navigation_task.route.waypoints  # type: List[Waypoint]
        if len(gates) == 0:
            return {}
        crossing_times = {}
        relative_crossing_times = calculate_and_get_relative_gate_times(self.navigation_task.route, self.air_speed,
                                                                        self.wind_speed, self.wind_direction)

        if start_point_override is not None:
            crossing_time = start_point_override
        else:
            crossing_time = self.takeoff_time + datetime.timedelta(minutes=self.minutes_to_starting_point)
        for gate, relative in relative_crossing_times:
            crossing_times[gate] = crossing_time + relative
        if self.navigation_task.route.takeoff_gate is not None and self.navigation_task.route.takeoff_gate.name not in crossing_times:
            crossing_times[self.navigation_task.route.takeoff_gate.name] = self.takeoff_time
        if self.navigation_task.route.landing_gate is not None and self.navigation_task.route.landing_gate.name not in crossing_times:
            crossing_times[
                self.navigation_task.route.landing_gate.name] = self.finished_by_time + datetime.timedelta(
                minutes=1)
        return crossing_times

    @property
    def gate_times(self) -> Dict:
        if self.predefined_gate_times is not None and len(self.predefined_gate_times) > 0:
            if self.navigation_task.route.takeoff_gate is not None and self.navigation_task.route.takeoff_gate.name not in self.predefined_gate_times:
                self.predefined_gate_times[self.navigation_task.route.takeoff_gate.name] = self.takeoff_time
            if self.navigation_task.route.landing_gate is not None and self.navigation_task.route.landing_gate.name not in self.predefined_gate_times:
                self.predefined_gate_times[
                    self.navigation_task.route.landing_gate.name] = self.finished_by_time + datetime.timedelta(
                    minutes=1)
            return self.predefined_gate_times
        zero_time = None
        if self.adaptive_start:
            zero_time = self.takeoff_time.astimezone(self.navigation_task.contest.time_zone).replace(hour=0, minute=0,
                                                                                                     second=0,
                                                                                                     microsecond=0)
        return self.calculate_and_get_gate_times(zero_time)

    @gate_times.setter
    def gate_times(self, value):
        self.predefined_gate_times = value

    def get_gate_time_offset(self, gate_name):
        planned = self.gate_times.get(gate_name)
        if planned is None:
            if gate_name == self.navigation_task.route.takeoff_gate.name:
                planned = self.takeoff_time
            elif gate_name == self.navigation_task.route.landing_gate.name:
                planned = self.finished_by_time
        actual = self.contestanttrack.gate_actual_times.get(gate_name)
        if planned and actual:
            return (actual - planned).total_seconds()
        return None

    def get_track_score_override(self) -> Optional[TrackScoreOverride]:
        if self.track_score_override is not None:
            return self.track_score_override
        return self.navigation_task.track_score_override

    def get_gate_score_override(self, gate_type: str) -> Optional[GateScoreOverride]:
        for item in self.gate_score_override.all():
            if gate_type in item.for_gate_types:
                return item
        for item in self.navigation_task.gate_score_override.all():
            if gate_type in item.for_gate_types:
                return item
        return None

    def get_tracker_id(self) -> str:
        if self.tracker_device_id is not None and len(self.tracker_device_id) > 0:
            return self.tracker_device_id
        if self.team.crew.member1.app_tracking_id is not None and len(self.team.crew.member1.app_tracking_id) > 0:
            return self.team.crew.member1.app_tracking_id
        if self.team.crew.member2 is not None and self.team.crew.member2.app_tracking_id is not None and len(
                self.team.crew.member2.app_tracking_id) > 0:
            return self.team.crew.member2.app_tracking_id
        logger.error(f"Contestant {self.team} for navigation task {self.navigation_task} does not have a tracker ID")
        return ""

    @classmethod
    def get_contestant_for_device_at_time(cls, device: str, stamp: datetime.datetime):
        try:
            # Device belongs to contestant from 30 minutes before takeoff
            contestant = cls.objects.get(tracker_device_id=device, tracker_start_time__lte=stamp,
                                         finished_by_time__gte=stamp, contestanttrack__calculator_finished=False)
        except ObjectDoesNotExist:
            try:
                contestant = cls.objects.get(Q(team__crew__member1__app_tracking_id=device) | Q(
                    team__crew__member1__simulator_tracking_id=device), tracker_start_time__lte=stamp,
                                             finished_by_time__gte=stamp, contestanttrack__calculator_finished=False)
            except ObjectDoesNotExist:
                try:
                    contestant = cls.objects.get(Q(team__crew__member2__app_tracking_id=device) | Q(
                        team__crew__member2__simulator_tracking_id=device), tracker_start_time__lte=stamp,
                                                 finished_by_time__gte=stamp,
                                                 contestanttrack__calculator_finished=False)
                except ObjectDoesNotExist:
                    return None
        # Only allow contestants with validated team members compete
        if contestant.team.crew.member1 is None or contestant.team.crew.member1.validated:
            if contestant.team.crew.member2 is None or contestant.team.crew.member2.validated:
                return contestant
        return None

    def get_latest_position(self) -> Optional[Dict]:
        from influx_facade import InfluxFacade
        influx = InfluxFacade()
        result_set = influx.get_latest_position_for_contestant(self.pk)
        position_data = list(result_set.get_points(tags={"contestant": str(self.pk)}))
        try:
            return position_data[0]
        except IndexError:
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


########### POKER
class PlayingCard(models.Model):
    contestant_track = models.ForeignKey(ContestantTrack, on_delete=models.CASCADE)
    card = models.CharField(max_length=2, choices=PLAYING_CARDS)

    @classmethod
    def get_random_unique_card(cls, contestant: Contestant) -> str:
        cards = [item[0] for item in PLAYING_CARDS]
        existing_cards = contestant.contestanttrack.playingcard_set.all().values_list("card", flat=True)
        available_cards = set(cards) - set(existing_cards)
        if len(available_cards) == 0:
            raise ValueError(
                f"There are no available cards to choose for the contestant, he/she already has {len(existing_cards)}.")
        random_card = random.choice(list(available_cards))
        while contestant.contestanttrack.playingcard_set.filter(card=random_card).exists():
            random_card = random.choice([item[0] for item in PLAYING_CARDS])
        return random_card

    @classmethod
    def evaluate_hand(cls, contestant: Contestant) -> Tuple[int, str]:
        hand = [eval7.Card(s.card) for s in cls.objects.filter(contestant_track=contestant.contestanttrack)]
        score = eval7.evaluate(hand)
        return score, eval7.handtype(score)

    @classmethod
    def maximum_score(cls) -> int:
        return 135004160

    @classmethod
    def get_relative_score(cls, contestant: Contestant) -> Tuple[float, str]:
        score, hand_type = cls.evaluate_hand(contestant)
        return 100 * score / cls.maximum_score(), hand_type

    @classmethod
    def add_contestant_card(cls, contestant: Contestant, card: str, waypoint: str):
        from influx_facade import InfluxFacade
        influx = InfluxFacade()
        poker_card = cls.objects.create(contestant_track=contestant.contestanttrack, card=card)
        relative_score, hand_description = cls.get_relative_score(contestant)
        score_per_gate = contestant.contestanttrack.score_per_gate
        score_per_gate[waypoint] = relative_score
        internal_message = {
            "gate": waypoint,
            "message": "Received card {}, current hand is {}".format(poker_card.get_card_display(), hand_description),
            "points": relative_score,
            "planned": None,
            "actual": None,
            "offset_string": None
        }
        string = "{}: {}".format(waypoint, internal_message["message"])
        internal_message["string"] = string
        contestant.contestanttrack.update_score(score_per_gate, relative_score,
                                                contestant.contestanttrack.score_log + [internal_message])
        pos = contestant.get_latest_position()
        longitude = 0
        latitude = 0
        if pos:
            latitude = pos["latitude"]
            longitude = pos["longitude"]
        influx.add_annotation(contestant, latitude, longitude, string, "information",
                              datetime.datetime.now(datetime.timezone.utc))


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

    class Meta:
        unique_together = ("team", "task")


class ContestSummary(models.Model):
    """
    Summary score for the entire contest for a team
    """
    team = models.ForeignKey(Team, on_delete=models.PROTECT)
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE)
    points = models.FloatField()

    class Meta:
        unique_together = ("team", "contest")


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


@receiver(pre_save, sender=Crew)
def validate_crew(sender, instance: Crew, **kwargs):
    instance.validate()


@receiver(pre_save, sender=Club)
def validate_club(sender, instance: Club, **kwargs):
    instance.validate()


@receiver(pre_save, sender=Route)
def validate_route(sender, instance: Route, **kwargs):
    instance.clean()


@receiver(post_delete, sender=NavigationTask)
def remove_route_from_deleted_navigation_task(sender, instance: NavigationTask, **kwargs):
    instance.route.delete()


@receiver(post_delete, sender=Contestant)
def remove_track_from_influx(sender, instance: NavigationTask, **kwargs):
    from influx_facade import InfluxFacade
    influx = InfluxFacade()
    influx.clear_data_for_contestant(instance.pk)


def generate_random_string(length) -> str:
    return "".join(choice(ascii_uppercase + ascii_lowercase + digits) for i in range(length))


@receiver(pre_save, sender=Person)
def register_personal_tracker(sender, instance: Person, **kwargs):
    instance.validate()
    if instance.pk is None:
        try:
            original = Person.objects.get(pk=instance.pk)
            original_tracking_id = original.app_tracking_id
            simulator_original_tracking_id = original.simulator_tracking_id
        except ObjectDoesNotExist:
            original_tracking_id = None
            simulator_original_tracking_id = None
        traccar = get_traccar_instance()
        app_random_string = "SHOULD_NOT_BE_HERE"
        simulator_random_string = "SHOULD_NOT_BE_HERE"
        existing = True
        while existing:
            app_random_string = generate_random_string(28)
            simulator_random_string = generate_random_string(28)
            logger.info(f"Generated random string {app_random_string} for person {instance}")
            existing = Person.objects.filter(
                Q(app_tracking_id=app_random_string) | Q(simulator_tracking_id=simulator_random_string)).exists()
        instance.app_tracking_id = app_random_string
        instance.simulator_tracking_id = simulator_random_string
        logger.info(f"Assigned random string {instance.app_tracking_id} to person {instance}")
        device, created = traccar.get_or_create_device(str(instance), instance.app_tracking_id)
        logger.info(f"Traccar device {device} was created: {created}")
        if created and original_tracking_id is not None and original_tracking_id != instance.app_tracking_id:
            original_device = traccar.get_device(original_tracking_id)
            if original_device is not None:
                logger.info(f"Clearing original device {original_device}")
                traccar.delete_device(original_device["id"])
        device, created = traccar.get_or_create_device(str(instance) + " simulator",
                                                       instance.simulator_tracking_id)
        logger.info(f"Traccar device {device} was created: {created}")
        if created and simulator_original_tracking_id is not None and simulator_original_tracking_id != instance.simulator_tracking_id:
            original_device = traccar.get_device(simulator_original_tracking_id)
            if original_device is not None:
                logger.info(f"Clearing original device {original_device}")
                traccar.delete_device(original_device["id"])
    else:
        original = Person.objects.get(pk=instance.pk)
        # Update traccar device names
        if str(original) != str(instance):
            traccar = get_traccar_instance()
            traccar.update_device_name(str(instance), instance.app_tracking_id)
            traccar.update_device_name(str(instance) + " simulator", instance.simulator_tracking_id)


@receiver(pre_delete, sender=Person)
def delete_personal_tracker(sender, instance: Person, **kwargs):
    if instance.app_tracking_id is not None:
        traccar = get_traccar_instance()
        original_device = traccar.get_device(instance.app_tracking_id)
        if original_device is not None:
            traccar.delete_device(original_device["id"])
    if instance.simulator_tracking_id is not None:
        traccar = get_traccar_instance()
        original_device = traccar.get_device(instance.simulator_tracking_id)
        if original_device is not None:
            traccar.delete_device(original_device["id"])


@receiver(post_save, sender=MyUser)
def create_random_password_for_user(sender, instance: MyUser, **kwargs):
    if not instance.has_usable_password():
        instance.set_password(MyUser.objects.make_random_password(length=20))
        instance.save()
