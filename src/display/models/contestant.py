import datetime
import logging
import time
from io import BytesIO
from typing import Optional

import numpy as np
import matplotlib.pyplot as plt
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, IntegrityError
from django.db.models import Q, QuerySet
from django.urls import reverse
from django.utils.safestring import mark_safe

from display.calculators.calculator_utilities import round_time_second
from display.fields.my_pickled_object_field import MyPickledObjectField
from display.models.contestant_utility_models import ContestantReceivedPosition
from display.utilities.calculate_gate_times import calculate_and_get_relative_gate_times
from display.utilities.calculator_running_utilities import is_calculator_running
from display.utilities.calculator_termination_utilities import request_termination
from display.utilities.navigation_task_type_definitions import (
    POKER,
    AIRSPORTS,
    AIRSPORT_CHALLENGE,
    ANR_CORRIDOR,
    PRECISION,
    LANDING,
)
from display.utilities.traccar_factory import get_traccar_instance
from display.utilities.track_merger import merge_tracks
from display.utilities.tracking_definitions import (
    TRACCAR,
    TRACKING_SERVICES,
    TRACKING_PILOT_AND_COPILOT,
    TRACKING_DEVICES,
    TRACKING_DEVICE,
    TRACKING_COPILOT,
    TRACKING_PILOT,
)
from display.utilities.wind_utilities import calculate_ground_speed_combined
from traccar_facade import augment_positions_from_traccar

logger = logging.getLogger(__name__)

TRACKING_DEVICE_TIMEOUT = 10


def round_gate_times(times: dict) -> dict:
    return {key: round_time_second(value) for key, value in times.items()}


class Contestant(models.Model):
    """
    The contestant model represents an instance of a team competing in a navigation task. It keeps track of all timing
    information, tracking information, and scoring related to that contestant. There may be multiple contestants for
    any team/navigation task combination, but contestants for teams that share either personnel or aircraft cannot
    overlap in time.
    """

    team = models.ForeignKey("Team", on_delete=models.CASCADE)
    navigation_task = models.ForeignKey("NavigationTask", on_delete=models.CASCADE)
    adaptive_start = models.BooleanField(
        default=False,
        help_text="If true, takeoff time and minutes to starting point is ignored. Start time is set to the closest minute to the time crossing the infinite starting line in the correct direction. This is typically used for a case where it is difficult to control the start time because of external factors such as ATC.",
    )
    takeoff_time = models.DateTimeField(
        help_text="The time the take of gate (if it exists) should be crossed. Otherwise it is the time power should be applied"
    )
    minutes_to_starting_point = models.FloatField(
        default=5,
        help_text="The number of minutes from the take-off time until the starting point",
    )
    finished_by_time = models.DateTimeField(
        help_text="The time it is expected that the navigation task has finished and landed (used among other things for knowing when the tracker is busy). Is also used for the gate time for the landing gate"
    )
    air_speed = models.FloatField(default=70, help_text="The planned airspeed for the contestant")
    track_version = models.IntegerField(
        default=0,
        help_text="Incremented whenever a new track is loaded from scratch either from traccar or from a gpx file.",
    )
    contestant_number = models.PositiveIntegerField(
        help_text="A unique number for the contestant in this navigation task"
    )
    tracking_service = models.CharField(
        default=TRACCAR,
        choices=TRACKING_SERVICES,
        max_length=30,
        help_text="Supported tracking services: {}".format(TRACKING_SERVICES),
    )
    tracking_device = models.CharField(
        default=TRACKING_PILOT_AND_COPILOT,
        choices=TRACKING_DEVICES,
        max_length=30,
        help_text="The device used for tracking the team",
    )
    tracker_device_id = models.CharField(
        max_length=100,
        help_text="ID of physical tracking device that will be brought into the plane. If using the Air Sports Live Tracking app this should be left blank.",
        blank=True,
        null=True,
    )
    tracker_start_time = models.DateTimeField(
        help_text="When the tracker is handed to the contestant, can have no changes to the route (e.g. wind and timing) after this."
    )
    competition_class_longform = models.CharField(
        max_length=100,
        help_text="The class of the contestant, e.g. beginner, professional, et cetera",
        blank=True,
        null=True,
    )
    competition_class_shortform = models.CharField(
        max_length=100,
        help_text="The abbreviated class of the contestant, e.g. beginner, professional, et cetera",
        blank=True,
        null=True,
    )
    predefined_gate_times = MyPickledObjectField(
        default=None,
        null=True,
        blank=True,
        help_text="Dictionary of gates and their starting times (with time zone)",
    )
    wind_speed = models.FloatField(
        default=0,
        help_text="The navigation test wind speed. This is used to calculate gate times if these are not predefined.",
        validators=[MaxValueValidator(40), MinValueValidator(0)],
    )
    wind_direction = models.FloatField(
        default=0,
        help_text="The navigation test wind direction. This is used to calculate gate times if these are not predefined.",
        validators=[MaxValueValidator(360), MinValueValidator(0)],
    )
    annotation_index = models.IntegerField(default=0, help_text="Internal housekeeping for annotation transmission")
    has_been_tracked_by_simulator = models.BooleanField(
        default=False,
        help_text="Is true if any positions for the contestant has been received from the simulator tracking ID",
    )

    class Meta:
        unique_together = ("navigation_task", "contestant_number")
        ordering = ("takeoff_time",)

    @property
    def newest_flight_order_link_uid(self):
        """
        There may be multiple generated flight orders. Get the newest one.
        """
        return self.emailmaplink_set.all().order_by("-created_at").values_list("id", flat=True).first()

    @property
    def planning_time(self) -> datetime.datetime:
        """
        When does the planning time for the contestant start given the planned takeoff time
        """
        return self.takeoff_time - datetime.timedelta(minutes=self.navigation_task.planning_time)

    @property
    def has_flight_order_link(self):
        return self.emailmaplink_set.all().exists()

    @property
    def starting_point_time(self) -> datetime.datetime:
        """
        The calculated passing time for the first waypoint in the track (assumed to be the starting point).
        """
        try:
            return self.gate_times[self.navigation_task.route.waypoints[0].name]
        except (KeyError, IndexError):
            return self.takeoff_time + datetime.timedelta(minutes=self.navigation_task.minutes_to_starting_point)

    @property
    def starting_point_time_local(self) -> datetime.datetime:
        return self.starting_point_time.astimezone(self.navigation_task.contest.time_zone)

    @property
    def tracker_start_time_local(self) -> datetime.datetime:
        return self.tracker_start_time.astimezone(self.navigation_task.contest.time_zone)

    @property
    def takeoff_time_local(self) -> datetime.datetime:
        return self.takeoff_time.astimezone(self.navigation_task.contest.time_zone)

    @property
    def finished_by_time_local(self) -> datetime.datetime:
        return self.finished_by_time.astimezone(self.navigation_task.contest.time_zone)

    def get_final_gate_time(self) -> Optional[datetime.datetime]:
        return self.gate_times.get(self.navigation_task.route.waypoints[-1].name)

    @property
    def final_gate_time_local(self) -> Optional[datetime.datetime]:
        dt = self.get_final_gate_time()
        return dt.astimezone(self.navigation_task.contest.time_zone) if dt else None

    @property
    def landing_time(self) -> datetime.datetime:
        if self.navigation_task.route.landing_gates:
            return self.gate_times[self.navigation_task.route.landing_gates.name]
        return self.gate_times[self.navigation_task.route.waypoints[-1].name] + datetime.timedelta(
            minutes=self.navigation_task.minutes_to_landing
        )

    @property
    def landing_time_after_final_gate(self) -> datetime.datetime:
        return self.gate_times[self.navigation_task.route.waypoints[-1].name] + datetime.timedelta(
            minutes=self.navigation_task.minutes_to_landing
        )

    @property
    def landing_time_after_final_gate_local(self) -> datetime.datetime:
        return self.landing_time_after_final_gate.astimezone(self.navigation_task.contest.time_zone)

    @property
    def has_crossed_starting_line(self) -> bool:
        return self.contestanttrack.calculator_started and self.contestanttrack.current_state != "Waiting..."

    def blocking_request_calculator_termination(self):
        """
        Signals that the calculator process (or job) should terminate immediately and blocks until it is confirmed to be no longer
        running.
        """
        self.request_calculator_termination()
        start = datetime.datetime.now()
        while is_calculator_running(self.pk):
            if datetime.datetime.now() > start + datetime.timedelta(minutes=1):
                raise TimeoutError("Calculator is running even though termination is requested")
            time.sleep(3)
        return

    def request_calculator_termination(self):
        """
        Signals that the calculator process (or job) shall terminate immediately and returns.
        """
        logger.info(f"Signalling manual termination for contestant {self}")
        request_termination(self.pk)

    def save(self, **kwargs):
        self.tracker_device_id = self.tracker_device_id.strip() if self.tracker_device_id else ""
        if self.tracking_service == TRACCAR:
            traccar = get_traccar_instance()
            traccar.get_or_create_device(self.tracker_device_id, self.tracker_device_id)
        super().save(**kwargs)

    @property
    def scorecard_rules(self):
        return []
        # return self.navigation_task.scorecard.scores_display(self)

    def _prohibited_zone_text(self):
        scorecard = self.navigation_task.scorecard
        return f"""Entering a prohibited area gives a penalty of {"{:.04}".format(scorecard.prohibited_zone_penalty)} points."""

    def _penalty_zone_text(self):
        scorecard = self.navigation_task.scorecard
        return f"""Entering a penalty area gives a penalty of {"{:.04}".format(scorecard.penalty_zone_penalty_per_second)} 
points per second after the first {"{:.04}".format(scorecard.penalty_zone_grace_time)} seconds."""

    def _precision_rule_description(self):
        scorecard = self.navigation_task.scorecard
        gate_sizes = [item.width for item in self.navigation_task.route.waypoints]
        return f"""For this task the turning point gate width is between {min(gate_sizes)} and {max(gate_sizes)} nm.
 The penalty for 
crossing the gate at the wrong time is {self.navigation_task.scorecard.get_penalty_per_second_for_gate_type("tp")} 
per second beyond the first {self.navigation_task.scorecard.get_graceperiod_after_for_gate_type("tp")} seconds.
Crossing the extended starting line before start ({self.navigation_task.scorecard.get_extended_gate_width_for_gate_type("sp")} nm) 
gives a penalty of {self.navigation_task.scorecard.get_bad_crossing_extended_gate_penalty_for_gate_type("sp")}.

Flying off track by more than {"{:.0f}".format(scorecard.backtracking_bearing_difference)} degrees for more than 
{scorecard.backtracking_grace_time_seconds} seconds
gives a penalty of {scorecard.backtracking_penalty} points.

{self._prohibited_zone_text()} {self._penalty_zone_text()}
{"The route has a takeoff gate." if self.navigation_task.route.first_takeoff_gate else ""} {"The route has a landing gate." if self.navigation_task.route.first_landing_gate else ""}
"""

    def _poker_rule_description(self):
        return """There are no specific rules for a poker run. Just cross the gates in the correct order to receive your playing cards."""

    def _anr_rule_description(self):
        scorecard = self.navigation_task.scorecard
        text = f"""For this task the corridor width is {"{:.2f}".format(self.navigation_task.route.corridor_width)} nm. 
Flying outside of the corridor more than {scorecard.corridor_grace_time} seconds gives a penalty of 
{"{:.0f}".format(scorecard.corridor_outside_penalty)} point(s) per second."""
        if scorecard.corridor_maximum_penalty != -1:
            text += f"""There is a maximum penalty of {"{:.0f}".format(scorecard.corridor_maximum_penalty)} points for being outside the corridor per leg."""
        text += f"""
{self._prohibited_zone_text()} {self._penalty_zone_text()} {"The route has a takeoff gate." if self.navigation_task.route.first_takeoff_gate else ""} {"The route has a landing gate." if self.navigation_task.route.first_landing_gate else ""}
"""
        return text

    def _air_sports_rule_description(self):
        scorecard = self.navigation_task.scorecard
        gate_sizes = [item.width for item in self.navigation_task.route.waypoints]
        minimum_size = min(gate_sizes)
        maximum_size = max(gate_sizes)
        if maximum_size == minimum_size:
            corridor_width_text = f"For this task the corridor with is {minimum_size} NM."
        else:
            corridor_width_text = (
                f"For this task the corridor width is between {minimum_size} NM and {maximum_size} NM."
            )
        text = f"""
{corridor_width_text} Flying outside of the corridor for more than {scorecard.corridor_grace_time} seconds gives a penalty of 
{"{:.0f}".format(scorecard.corridor_outside_penalty)} point(s) per second. """
        if scorecard.corridor_maximum_penalty != -1:
            text += f"""There is a maximum penalty of {"{:.0f}".format(scorecard.corridor_maximum_penalty)} points for being outside the corridor per leg."""

        text += f"""
There are timed gates on the track. The penalty for crossing the gate at the wrong time is {self.navigation_task.scorecard.get_penalty_per_second_for_gate_type("tp")} point(s) per second beyond the first {self.navigation_task.scorecard.get_graceperiod_after_for_gate_type("tp")} seconds. 
Flying off track by more than {"{:.0f}".format(scorecard.backtracking_bearing_difference)} degrees for more than {scorecard.backtracking_grace_time_seconds} seconds gives a penalty of {scorecard.backtracking_penalty} points. 
{self._prohibited_zone_text()} {self._penalty_zone_text()}
{"The route has a takeoff gate." if self.navigation_task.route.first_takeoff_gate else ""} {"The route has a landing gate." if self.navigation_task.route.first_landing_gate else ""}

"""
        return text

    def get_formatted_rules_description(self):
        """
        Returns a long formatted string that describes the rules for this specific contestant in the navigation task.
        :return:
        """
        if self.navigation_task.scorecard.calculator == PRECISION:
            return self._precision_rule_description()
        if self.navigation_task.scorecard.calculator == ANR_CORRIDOR:
            return self._anr_rule_description()
        if self.navigation_task.scorecard.calculator in (AIRSPORTS, AIRSPORT_CHALLENGE):
            return self._air_sports_rule_description()
        if self.navigation_task.scorecard.calculator == POKER:
            return self._poker_rule_description()
        return "Missing rules"

    def __str__(self):
        return "{} - {}".format(self.contestant_number, self.team)
        # return "{}: {} in {} ({}, {})".format(self.contestant_number, self.team, self.navigation_task.name, self.takeoff_time,
        #                                       self.finished_by_time)

    def calculate_progress(self, latest_time: datetime.datetime, ignore_finished: bool = False) -> float:
        """
        Calculate a number between 0 and 100 to describe the progress of the contestant through the track.  Uses
        expected timing to calculate expected duration and progress.
        """
        if POKER in self.navigation_task.scorecard.task_type:
            return 100 * self.playingcard_set.all().count() / 5
        if LANDING in self.navigation_task.scorecard.task_type:
            # A progress of zero will also leave estimated score blank
            return 0
        route_progress = 100
        if hasattr(self, "contestanttrack"):
            if len(self.navigation_task.route.waypoints) > 0 and (
                not self.contestanttrack.calculator_finished or ignore_finished
            ):
                first_gate = self.navigation_task.route.waypoints[0]
                last_gate = self.navigation_task.route.waypoints[-1]

                first_gate_time = self.gate_times[first_gate.name]
                last_gate_time = self.gate_times[last_gate.name]
                route_duration = (last_gate_time - first_gate_time).total_seconds()
                route_duration_progress = (latest_time - first_gate_time).total_seconds()
                route_progress = 100 * route_duration_progress / route_duration
        return route_progress

    def get_groundspeed(self, bearing) -> float:
        """
        Calculate the ground speed given bearing, configured airspeed, and wind information.
        """
        return calculate_ground_speed_combined(bearing, self.air_speed, self.wind_speed, self.wind_direction)

    def clean(self):
        if not isinstance(self.tracker_start_time, datetime.datetime):
            raise ValidationError("Malformed tracker start time")
        if not isinstance(self.takeoff_time, datetime.datetime):
            raise ValidationError("Malformed takeoff time")
        if not isinstance(self.finished_by_time, datetime.datetime):
            raise ValidationError("Malformed finished by time")
        if self.tracking_device == TRACKING_DEVICE and (
            self.tracker_device_id is None or len(self.tracker_device_id) == 0
        ):
            raise ValidationError(
                f"Tracking device is set to {self.get_tracking_device_display()}, but no tracker device ID is supplied"
            )
        if self.tracking_device == TRACKING_COPILOT and self.team.crew.member2 is None:
            raise ValidationError(
                f"Tracking device is set to {self.get_tracking_device_display()}, but there is no copilot"
            )
        # Validate single-use tracker
        overlapping_trackers = Contestant.objects.filter(
            tracking_service=self.tracking_service,
            tracker_device_id__in=self.get_tracker_ids(),
            tracker_start_time__lte=self.finished_by_time,
            finished_by_time__gte=self.tracker_start_time,
        ).exclude(pk=self.pk)
        if overlapping_trackers.exists():
            intervals = []
            for contestant in overlapping_trackers:
                smallest_end = min(contestant.finished_by_time, self.finished_by_time)
                largest_start = max(contestant.tracker_start_time, self.tracker_start_time)
                intervals.append(
                    (
                        contestant.navigation_task,
                        largest_start.isoformat(),
                        smallest_end.isoformat(),
                    )
                )
            raise ValidationError(
                "The tracker '{}' is in use by other contestants for the intervals: {}".format(
                    self.tracker_device_id, intervals
                )
            )
        # Validate that persons are not part of other contestants for the same interval
        overlapping1 = Contestant.objects.filter(
            Q(team__crew__member1=self.team.crew.member1) | Q(team__crew__member2=self.team.crew.member1),
            tracker_start_time__lte=self.finished_by_time,
            finished_by_time__gte=self.tracker_start_time,
        ).exclude(pk=self.pk)
        if overlapping1.exists():
            intervals = []
            for contestant in overlapping1:
                smallest_end = min(contestant.finished_by_time, self.finished_by_time)
                largest_start = max(contestant.tracker_start_time, self.tracker_start_time)
                intervals.append(
                    (
                        contestant.navigation_task,
                        largest_start,
                        smallest_end,
                    )
                )
            links = []
            for task, start, finish in intervals:
                links.append(f'<a href="{reverse("navigationtask_detail", kwargs={"pk": task.pk})}">{task}</a>')
            start_time = min(item[1] for item in intervals)
            finish_time = max(item[2] for item in intervals)
            if hasattr(self, "navigation_task") and self.navigation_task:
                raise ValidationError(
                    mark_safe(
                        f"The pilot '{self.team.crew.member1}' is competing as a different contestant in the tasks: {', '.join(links)} in the time interval {start_time.astimezone(self.navigation_task.contest.time_zone)} - {finish_time.astimezone(self.navigation_task.contest.time_zone)}"
                    )
                )
            else:
                raise ValidationError(
                    mark_safe(
                        f"The pilot '{self.team.crew.member1}' is competing as a different contestant in the tasks: {', '.join(links)}"
                    )
                )

        if self.team.crew.member2 is not None:
            overlapping2 = Contestant.objects.filter(
                Q(team__crew__member1=self.team.crew.member2) | Q(team__crew__member2=self.team.crew.member2),
                tracker_start_time__lte=self.finished_by_time,
                finished_by_time__gte=self.tracker_start_time,
            ).exclude(pk=self.pk)
            if overlapping2.exists():
                intervals = []
                for contestant in overlapping2:
                    smallest_end = min(contestant.finished_by_time, self.finished_by_time)
                    largest_start = max(contestant.tracker_start_time, self.tracker_start_time)
                    intervals.append(
                        (
                            contestant.navigation_task,
                            largest_start,
                            smallest_end,
                        )
                    )
                links = []
                for task, start, finish in intervals:
                    links.append(f'<a href="{reverse("navigationtask_detail", kwargs={"pk": task.pk})}">{task}</a>')
                start_time = min(item[1] for item in intervals)
                finish_time = max(item[2] for item in intervals)
                raise ValidationError(
                    mark_safe(
                        f"The copilot '{self.team.crew.member2}' is competing as a different contestant in the tasks: {', '.join(links)} in the time interval {start_time.astimezone(self.navigation_task.contest.time_zone)} - {finish_time.astimezone(self.navigation_task.contest.time_zone)}"
                    )
                )
        # Validate maximum tracking time
        if self.finished_by_time - self.tracker_start_time > datetime.timedelta(hours=24):
            raise ValidationError(
                f"The maximum tracking time for {self} (from tracker start time to finished by time) is 24 hours (currently {self.finished_by_time - self.tracker_start_time}). Either start tracking later or finish earlier to solve this."
            )
        # Validate takeoff time after tracker start
        if self.tracker_start_time > self.takeoff_time:
            raise ValidationError(
                "Tracker start time '{}' is after takeoff time '{}' for contestant number {}".format(
                    self.tracker_start_time, self.takeoff_time, self.contestant_number
                )
            )
        if self.takeoff_time > self.finished_by_time:
            raise ValidationError(
                "Takeoff time '{}' is after finished by time '{}' for contestant number {}".format(
                    self.takeoff_time, self.finished_by_time, self.contestant_number
                )
            )
        # Validate no timing changes after calculator start
        if self.pk is not None:
            original = Contestant.objects.get(pk=self.pk)
            if hasattr(original, "contestanttrack") and original.contestanttrack.calculator_started:
                if original.takeoff_time.replace(microsecond=0) != self.takeoff_time.replace(microsecond=0):
                    raise ValidationError(
                        f"Calculator has started for {self}, it is not possible to change takeoff time from {original.takeoff_time} to {self.takeoff_time}"
                    )
                if original.tracker_start_time.replace(microsecond=0) != self.tracker_start_time.replace(microsecond=0):
                    raise ValidationError(
                        f"Calculator has started for {self}, it is not possible to change tracker start time"
                    )
                if original.wind_speed != self.wind_speed:
                    raise ValidationError(f"Calculator has started for {self}, it is not possible to change wind speed")
                if original.wind_direction != self.wind_direction:
                    raise ValidationError(
                        f"Calculator has started for {self}, it is not possible to change wind direction"
                    )
                if original.adaptive_start != self.adaptive_start:
                    raise ValidationError(
                        f"Calculator has started for {self}, it is not possible to change adaptive start"
                    )
                if original.minutes_to_starting_point != self.minutes_to_starting_point:
                    raise ValidationError(
                        f"Calculator has started for {self}, it is not possible to change minutes to starting point"
                    )

    @staticmethod
    def _convert_to_individual_leg_times(
        crossing_times: list[tuple[str, datetime.timedelta]]
    ) -> list[tuple[str, datetime.timedelta]]:
        """
        Calculate the planned duration for each leg.
        """
        if len(crossing_times) == 0:
            return []
        individual_times = [crossing_times[0]]
        for index in range(1, len(crossing_times)):
            individual_times.append((crossing_times[index][0], crossing_times[index][1] - crossing_times[index - 1][1]))
        return individual_times

    def _get_takeoff_and_landing_times(self) -> dict[str, datetime.datetime]:
        crossing_times = {}
        for gate in self.navigation_task.route.takeoff_gates:
            crossing_times[gate.name] = self.takeoff_time
        for gate in self.navigation_task.route.landing_gates:
            crossing_times[gate.name] = self.finished_by_time - datetime.timedelta(minutes=1)
        return crossing_times

    def calculate_missing_gate_times(
        self, predefined_gate_times: dict, start_point_override: Optional[datetime.datetime] = None
    ) -> dict:
        """
        If the gate times have not been provided when the contestant was created, calculate the gay times given the
        start time, route, airspeed, and wind information. Optionally provide a dictionary of pre-calculated gate times
        or an initial starting time.
        """
        if start_point_override:
            previous_crossing_time = start_point_override
        else:
            previous_crossing_time = self.takeoff_time + datetime.timedelta(minutes=self.minutes_to_starting_point)
            if self.adaptive_start:
                previous_crossing_time = self.takeoff_time.astimezone(self.navigation_task.contest.time_zone).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
        crossing_times = {}
        relative_crossing_times = calculate_and_get_relative_gate_times(
            self.navigation_task.route,
            self.air_speed,
            self.wind_speed,
            self.wind_direction,
        )
        leg_times = Contestant._convert_to_individual_leg_times(relative_crossing_times)
        for gate_name, leg_time in leg_times:
            crossing_times[gate_name] = predefined_gate_times.get(gate_name, previous_crossing_time + leg_time)
            previous_crossing_time = crossing_times[gate_name]
        for gate_name, crossing_time in self._get_takeoff_and_landing_times().items():
            crossing_times[gate_name] = predefined_gate_times.get(gate_name, crossing_time)
        return crossing_times

    @property
    def gate_times(self) -> dict:
        """
        Returns the stored gate times.  Calculate any missing times and store the result.
        """
        if not self.predefined_gate_times or not len(self.predefined_gate_times):
            times = round_gate_times(self.calculate_missing_gate_times({}))
            if self.pk is not None:
                Contestant.objects.filter(pk=self.pk).update(predefined_gate_times=times)
            return times
        return self.predefined_gate_times

    @gate_times.setter
    def gate_times(self, value):
        self.predefined_gate_times = self.calculate_missing_gate_times(value)

    def get_gate_time_offset(self, gate_name):
        planned = self.gate_times.get(gate_name)
        if planned is None:
            if len(self.navigation_task.route.takeoff_gates) > 0 and gate_name in (
                gate.name for gate in self.navigation_task.route.takeoff_gates
            ):
                planned = self.takeoff_time
            elif len(self.navigation_task.route.landing_gates) > 0 and gate_name in (
                gate.name for gate in self.navigation_task.route.landing_gates
            ):
                planned = self.finished_by_time
        actual = self.actualgatetime_set.filter(gate=gate_name).first()
        if planned and actual:
            return (actual.time - planned).total_seconds()
        return None

    def get_tracker_ids(self) -> list[str]:
        """
        Return the traccar IDs that are tied to this contestant.
        """
        if self.tracking_device == TRACKING_DEVICE:
            return [self.tracker_device_id]
        if self.tracking_device in (TRACKING_PILOT, TRACKING_PILOT_AND_COPILOT):
            trackers = [self.team.crew.member1.app_tracking_id]
            if self.team.crew.member2 is not None:
                trackers.append(self.team.crew.member2.app_tracking_id)
            return trackers
        if self.tracking_device == TRACKING_COPILOT:
            return [self.team.crew.member2.app_tracking_id]
        logger.error(
            f"Contestant {self.team} for navigation task {self.navigation_task} does not have a tracker ID for tracking device {self.tracking_device}"
        )
        return [""]

    def get_simulator_tracker_ids(self) -> list[str]:
        """
        Return the traccar IDs that are tied to this contestant in simulation mode.
        """
        if self.tracking_device in (TRACKING_PILOT, TRACKING_PILOT_AND_COPILOT):
            trackers = [self.team.crew.member1.simulator_tracking_id]
            if self.team.crew.member2 is not None:
                trackers.append(self.team.crew.member2.simulator_tracking_id)
            return trackers
        if self.tracking_device == TRACKING_COPILOT:
            return [self.team.crew.member2.simulator_tracking_id]
        logger.error(
            f"Contestant {self.team} for navigation task {self.navigation_task} does not have a simulator tracker ID for tracking device {self.tracking_device}"
        )
        return [""]

    @property
    def tracker_id_display(self) -> list[dict]:
        devices = []
        if self.tracking_device == TRACKING_DEVICE:
            devices.append({"tracker": self.tracker_device_id, "has_user": True})
        if self.tracking_device in (TRACKING_PILOT, TRACKING_PILOT_AND_COPILOT) and self.team.crew.member1 is not None:
            devices.append(
                {
                    "tracker": self.team.crew.member1.email,
                    "has_user": get_user_model().objects.filter(email=self.team.crew.member1.email).exists(),
                    "is_active": self.team.crew.member1.is_tracking_active,
                }
            )
        if (
            self.tracking_device in (TRACKING_COPILOT, TRACKING_PILOT_AND_COPILOT)
            and self.team.crew.member2 is not None
        ):
            devices.append(
                {
                    "tracker": self.team.crew.member2.email,
                    "has_user": get_user_model().objects.filter(email=self.team.crew.member2.email).exists(),
                    "is_active": self.team.crew.member2.is_tracking_active,
                }
            )
        return devices

    def generate_position_block_for_contestant(
        self, position_data: dict, device_time: datetime.datetime
    ) -> ContestantReceivedPosition:
        """
        Helper function that constructs a position object from a traccar position message.
        """

        return ContestantReceivedPosition(
            contestant=self,
            time=device_time,
            latitude=float(position_data["latitude"]),
            longitude=float(position_data["longitude"]),
            altitude=float(position_data["altitude"]),
            speed=float(position_data["speed"]),
            course=float(position_data["course"]),
            battery_level=float(position_data["attributes"].get("batteryLevel", -1.0)),
            position_id=position_data["id"],
            device_id=position_data["deviceId"],
            processor_received_time=position_data.get("processor_received_time"),
            calculator_received_time=position_data.get("calculator_received_time"),
            server_time=position_data.get("server_time"),
        )

    @classmethod
    def get_contestant_for_device_at_time(
        cls, device: str, stamp: datetime.datetime
    ) -> tuple[Optional["Contestant"], bool]:
        """
        Retrieves the contestant that owns the tracking device for the time stamp. Returns an extra flag "is_simulator"
        which is true if the contestant is running the simulator tracking ID.
        """
        contestant, is_simulator = cls._try_to_get_tracker_tracking(device, stamp)
        if contestant is None:
            contestant, is_simulator = cls._try_to_get_pilot_tracking(device, stamp)
            if contestant is None:
                contestant, is_simulator = cls._try_to_get_copilot_tracking(device, stamp)
        if contestant:
            # Only allow contestants with validated team members compete
            # if contestant.team.crew.member1 is None or contestant.team.crew.member1.validated:
            #     if contestant.team.crew.member2 is None or contestant.team.crew.member2.validated:
            #         return contestant, is_simulator
            return contestant, is_simulator
        return None, is_simulator

    @classmethod
    def _try_to_get_tracker_tracking(cls, device: str, stamp: datetime.datetime) -> tuple[Optional["Contestant"], bool]:
        """
        Retrieve contestant that matches tracking device at time
        """
        try:
            # Device belongs to contestant from 30 minutes before takeoff
            return (
                cls.objects.get(
                    tracker_device_id=device,
                    tracker_start_time__lte=stamp,
                    tracking_device=TRACKING_DEVICE,
                    finished_by_time__gte=stamp,
                    contestanttrack__calculator_finished=False,
                ),
                False,
            )
        except ObjectDoesNotExist:
            return None, False

    @classmethod
    def _try_to_get_pilot_tracking(cls, device: str, stamp: datetime.datetime) -> tuple[Optional["Contestant"], bool]:
        """
        Retrieve contestant that matches pilot tracking app at time
        """
        try:
            contestant = cls.objects.get(
                Q(team__crew__member1__app_tracking_id=device) | Q(team__crew__member1__simulator_tracking_id=device),
                tracker_start_time__lte=stamp,
                finished_by_time__gte=stamp,
                contestanttrack__calculator_finished=False,
                tracking_device__in=(TRACKING_PILOT, TRACKING_PILOT_AND_COPILOT),
            )
            contestant.team.crew.member1.last_seen = stamp
            contestant.team.crew.member1.save(update_fields=["last_seen"])
            return (
                contestant,
                contestant.team.crew.member1.simulator_tracking_id == device,
            )
        except ObjectDoesNotExist:
            return None, False

    @classmethod
    def _try_to_get_copilot_tracking(cls, device: str, stamp: datetime.datetime) -> tuple[Optional["Contestant"], bool]:
        """
        Retrieve contestant that matches copilot tracking app at time
        """
        try:
            contestant = cls.objects.get(
                Q(team__crew__member2__app_tracking_id=device) | Q(team__crew__member2__simulator_tracking_id=device),
                tracker_start_time__lte=stamp,
                finished_by_time__gte=stamp,
                contestanttrack__calculator_finished=False,
                tracking_device__in=(TRACKING_COPILOT, TRACKING_PILOT_AND_COPILOT),
            )
            contestant.team.crew.member2.last_seen = stamp
            contestant.team.crew.member2.save(update_fields=["last_seen"])
            return (
                contestant,
                contestant.team.crew.member2.simulator_tracking_id == device,
            )
        except ObjectDoesNotExist:
            return None, False

    def is_currently_tracked_by_device(self, device_id: str) -> bool:
        """
        Returns true unless tracking_device is TRACKING_PILOT_AND_COPILOT because the contestant cannot be tracked
        by any other device. In the case where tracking_device is TRACKING_PILOT_AND_COPILOT the function returns true
        if we responded to this device_id the last time, or the was no loss time. Otherwise it will return false.
        """
        if self.tracking_device == TRACKING_PILOT_AND_COPILOT:
            key = f"latest_tracking_device_{self.pk}"
            previously_used_device_id = cache.get(key)
            if previously_used_device_id == device_id or previously_used_device_id is None:
                if previously_used_device_id is None:
                    logger.debug(f"{self}: Setting tracking device to {device_id}")
                cache.set(key, device_id, TRACKING_DEVICE_TIMEOUT)
                return True
            return False
        return True

    def get_traccar_track(self) -> list[dict]:
        """
        Return the full track for the contestant interval from traccar. All available tracking for the contestant is
        merged.
        """
        traccar = get_traccar_instance()
        device_ids = traccar.get_device_ids_for_contestant(self)

        tracks = []
        for device_id in device_ids:
            track = traccar.get_positions_for_device_id(device_id, self.tracker_start_time, self.finished_by_time)
            augment_positions_from_traccar(track)
            tracks.append(track)
        logger.debug(f"Returned {len(tracks)} with lengths {', '.join([str(len(item)) for item in tracks])}")
        return merge_tracks(tracks)

    def get_track(self) -> QuerySet[ContestantReceivedPosition]:
        """
        Get the track for the contestant.  We only want the track that is used for the last calculation. This is always
        stored in the ContestantReceivedPosition objects, which is cleared whenever a calculation is restarted. This
        means that this function will always only return the data that is used for the latest calculation up until
        this time.
        """
        return self.contestantreceivedposition_set.all()

    def get_latest_position(self) -> Optional[ContestantReceivedPosition]:
        try:
            return self.get_track()[-1]
        except IndexError:
            return None

    def record_actual_gate_time(self, gate_name: str, passing_time: datetime.datetime):
        """
        Record the time of a gate passing to the database.
        """
        from display.models import ActualGateTime

        try:
            ActualGateTime.objects.create(gate=gate_name, time=passing_time, contestant=self)
        except IntegrityError:
            logger.exception(f"Contestant has already passed gate {gate_name}")

    def record_score_by_gate(self, gate_name: str, score: float):
        """
        Recall the cumulative score at a gate
        """
        from display.models import GateCumulativeScore

        gate_score, _ = GateCumulativeScore.objects.get_or_create(gate=gate_name, contestant=self)
        gate_score.points += score
        gate_score.save()

    def reset_track_and_score(self):
        """
        Reset all scoring to start again
        """
        from display.models import PlayingCard

        PlayingCard.clear_cards(self)
        self.scorelogentry_set.all().delete()
        self.trackannotation_set.all().delete()
        self.gatecumulativescore_set.all().delete()
        self.actualgatetime_set.all().delete()
        self.contestanttrack.reset()

    def generate_processing_statistics(self) -> bytes:
        """
        Generate a matplotlib chart showing the processing statistics for the contestants. Returns the binary (png)
        image.
        """
        from display.models import ContestantReceivedPosition

        stored_positions = ContestantReceivedPosition.objects.filter(contestant=self)
        total_delay = []
        transmission_delay = []
        processor_queueing_delay = []
        calculator_queueing_delay = []
        calculation_delay = []
        elapsed = []
        start_time = None
        for position in stored_positions:
            if start_time is None:
                start_time = position.time
            elapsed.append((position.time - start_time).total_seconds())
            if position.websocket_transmitted_time:
                total_delay.append((position.websocket_transmitted_time - position.time).total_seconds())
            else:
                total_delay.append(np.nan)
            if position.server_time:
                transmission_delay.append((position.server_time - position.time).total_seconds())
            else:
                transmission_delay.append(np.nan)
            if position.websocket_transmitted_time and position.calculator_received_time:
                calculation_delay.append(
                    (position.websocket_transmitted_time - position.calculator_received_time).total_seconds()
                )
            else:
                calculation_delay.append(np.nan)
            if position.server_time and position.processor_received_time:
                processor_queueing_delay.append(
                    (position.processor_received_time - position.server_time).total_seconds()
                )
            else:
                processor_queueing_delay.append(np.nan)
            if position.processor_received_time and position.calculator_received_time:
                calculator_queueing_delay.append(
                    (position.calculator_received_time - position.processor_received_time).total_seconds()
                )
            else:
                calculator_queueing_delay.append(np.nan)
        plt.figure()
        (total_delay_line,) = plt.plot(elapsed, total_delay, label="Total delay")
        (transmission_delay_line,) = plt.plot(elapsed, transmission_delay, label="Transmission delay")
        (processor_queueing_delay_line,) = plt.plot(elapsed, processor_queueing_delay, label="Processor queue delay")
        (calculator_queueing_delay_line,) = plt.plot(elapsed, calculator_queueing_delay, label="Calculator queue delay")
        (calculation_delay_line,) = plt.plot(elapsed, calculation_delay, label="Calculation delay")
        plt.legend(
            handles=[
                total_delay_line,
                transmission_delay_line,
                processor_queueing_delay_line,
                calculator_queueing_delay_line,
                calculation_delay_line,
            ]
        )
        plt.ylabel("Delay (s)")
        plt.xlabel("Time since start (s)")
        plt.title(f"Processing delays for {self}")
        figdata = BytesIO()
        plt.savefig(figdata, format="png")
        plt.close()
        figdata.seek(0)
        return figdata
