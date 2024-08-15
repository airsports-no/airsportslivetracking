import datetime
from typing import Optional

from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import QuerySet

from display.fields.my_pickled_object_field import MyPickledObjectField
from display.models.route import Route
from display.utilities.clone_object import simple_clone
from display.utilities.gate_definitions import FINISHPOINT, GATE_TYPES, SECRETPOINT, STARTINGPOINT, TURNPOINT
from display.utilities.navigation_task_type_definitions import CIMA_PRECISION, NAVIGATION_TASK_TYPES, PRECISION


class Scorecard(models.Model):
    """
    A scorecard is a collection of parameters used to control the scoring of a navigation task. Static scorecards are
    created for various international rules, and the user has the option of modifying certain parameters of the
    scorecard.  When a navigation task is created it is given a reference to the original scorecard, as well as a copy.
    The user can modify the copyand optionally restore to the contents of the original scorecard and start again.
    """

    name = models.CharField(max_length=255, default="default", unique=True)
    shortcut_name = models.CharField(
        max_length=255,
        default="shortcut_default",
        unique=True,
        help_text="Shortcut reference to latest scorecard version, e.g. 'FAI Precision' "
        "currently links to 'FAI Precision 2020'. This is the field that is "
        "used for lookups through the API, but the name is still used "
        "everywhere else",
    )
    valid_from = models.DateTimeField(blank=True, null=True)
    original = models.BooleanField(
        default=True, help_text="Signifies that this has been created manually and is not a copy"
    )
    included_fields = MyPickledObjectField(
        default=list, help_text="List of field names that should be visible in forms"
    )
    free_text = models.TextField(
        help_text="Free text (with HTML) that is included at the bottom of the scorecard box", default=""
    )
    calculator = models.CharField(
        choices=NAVIGATION_TASK_TYPES,
        default=PRECISION,
        max_length=20,
        help_text="Supported calculator types",
    )
    task_type = MyPickledObjectField(default=list, help_text="List of task types supported by the scorecard")
    initial_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Initial score awarded to the contestant it start. If set this will be used for the initial score for each contestant. If it is unset, the initial score will be calculated based on the chosen scorecard. This is typically 0 for most scorecards, and greater than 0 for CIMA scorecards.",
    )
    use_procedure_turns = models.BooleanField(default=True, blank=True)
    backtracking_penalty = models.FloatField(default=200, help_text="The number of points given for backtracking")
    backtracking_bearing_difference = models.FloatField(
        default=90,
        help_text="The bearing difference from the leg direction to initiate backtracking",
    )
    backtracking_grace_time_seconds = models.FloatField(
        default=5,
        help_text="The number of seconds the contestant is allowed to backtrack before backtracking penalty is applied",
    )
    backtracking_maximum_penalty = models.FloatField(
        default=-1, help_text="Negative numbers means the maximum is ignored"
    )
    below_minimum_altitude_penalty = models.FloatField(
        default=500,
        help_text="Penalty for flying below the minimum altitude (not applied automatically)",
    )
    below_minimum_altitude_maximum_penalty = models.FloatField(
        default=500,
        help_text="The maximum penalty that can be accumulated for flying below minimum altitude (not applied automatically)",
    )
    prohibited_zone_penalty = models.FloatField(
        default=200,
        help_text="Penalty for entering prohibited zone such as controlled airspace or other prohibited areas",
    )
    prohibited_zone_grace_time = models.FloatField(
        default=3,
        help_text="The number of seconds the contestant can be within the prohibited zone before getting penalty",
    )
    penalty_zone_grace_time = models.FloatField(
        default=3,
        help_text="The number of seconds the contestant can be within the penalty zone before getting penalty",
    )
    penalty_zone_penalty_per_second = models.FloatField(
        default=3, help_text="The number of points per second beyond the grace time while inside the penalty zone"
    )
    penalty_zone_maximum = models.FloatField(default=100, help_text="Maximum penalty within a single zone")

    ##### ANR Corridor
    corridor_grace_time = models.IntegerField(default=5, help_text="The corridor grace time for ANR tasks")
    corridor_outside_penalty = models.FloatField(
        default=3, help_text="The penalty awarded for leaving the ANR corridor"
    )
    corridor_maximum_penalty = models.FloatField(default=-1, help_text="The maximum penalty for leaving the corridor")

    def __str__(self):
        return self.name

    class Meta:
        ordering = ("-valid_from",)

    def _max_score_for_type(self, route: Route, waypoint_type: str):
        """Helper function to find the maximum score possible for a gate"""
        gate_score = self.gatescore_set.get(gate_type=waypoint_type)
        # A timed gate either has the maximum timing penalty if it is hit, or the miss penalty if it is missed. The
        # maximum penalty for this gate is therefore the maximum of these two.
        return abs(
            max(gate_score.maximum_penalty, gate_score.missed_penalty)
            * len(list(filter(lambda w: w.type == waypoint_type and w.time_check, route.waypoints)))
        ) + abs(
            gate_score.missed_penalty
            * len(
                list(filter(lambda w: w.type == waypoint_type and not w.time_check and w.gate_check, route.waypoints))
            )
        )

    def get_initial_score(self, route: Route) -> float:
        """Calculate the initial score for a route"""
        if self.initial_score is not None:
            return self.initial_score
        if self.calculator == CIMA_PRECISION:
            score = 0
            score += self._max_score_for_type(route, SECRETPOINT)
            score += self._max_score_for_type(route, TURNPOINT)
            score += self._max_score_for_type(route, STARTINGPOINT)
            score += self._max_score_for_type(route, FINISHPOINT)
            return score
        return 0

    def get_score_for_summary(self, score: float, initial_score: float) -> float:
        """Apply any final score scaling for use in the results service"""
        if self.calculator == CIMA_PRECISION:
            return 1000 * score / initial_score
        return score

    @property
    def visible_fields(self) -> list[str]:
        """
        Returns the list of scorecard fields that should be visible in the web GUI.
        """
        return [field for block in self.included_fields for field in block[1:]]

    @property
    def corridor_width(self) -> float:
        """
        The corridor width that has been assigned to the navigation task during the creation.
        """
        return self.navigation_task_override.route.corridor_width

    @classmethod
    def get_originals(cls) -> QuerySet:
        """
        Gets all scorecards that are original, i.e. not a copy of the original
        """
        return cls.objects.filter(original=True)

    def copy(self, name_postfix: str) -> "Scorecard":
        """
        Create a copy of the scorecard that can be modified by the user.
        """
        obj = simple_clone(
            self,
            {
                "name": f"{self.name}_{name_postfix}",
                "shortcut_name": f"{self.shortcut_name}_{name_postfix}",
                "original": False,
            },
        )
        for gate in self.gatescore_set.all():
            simple_clone(gate, {"scorecard": obj})
        return obj

    SCORECARD_CACHE = {}

    def get_gate_scorecard(self, gate_type: str) -> "GateScore":
        """
        Get the scorecard for a specific gate type.
        """
        try:
            return self.SCORECARD_CACHE[(self.pk, gate_type)]
        except KeyError:
            try:
                self.SCORECARD_CACHE[(self.pk, gate_type)] = self.gatescore_set.get(gate_type=gate_type)
                return self.SCORECARD_CACHE[(self.pk, gate_type)]
            except ObjectDoesNotExist:
                raise ValueError(f"Unknown gate type '{gate_type}' or undefined score")

    def calculate_penalty_zone_score(self, enter: datetime.datetime, leave: datetime.datetime):
        """
        Calculate the penalty for entering and then exiting the penalty zone
        """
        difference = round((leave - enter).total_seconds()) - self.penalty_zone_grace_time
        if difference < 0:
            return 0
        if self.penalty_zone_maximum > 0:
            return min(self.penalty_zone_maximum, difference * self.penalty_zone_penalty_per_second)
        if self.penalty_zone_maximum < 0:
            return max(self.penalty_zone_maximum, difference * self.penalty_zone_penalty_per_second)
        return difference * self.penalty_zone_penalty_per_second

    def get_gate_timing_score_for_gate_type(
        self,
        gate_type: str,
        planned_time: datetime.datetime,
        actual_time: Optional[datetime.datetime],
    ) -> float:
        """
        Given the actual and planned times for the gate type, calculate the resulting score.
        """
        gate_score = self.get_gate_scorecard(gate_type)
        return gate_score.calculate_score(planned_time, actual_time)

    def get_missed_penalty_for_gate_type(self, gate_type: str) -> float:
        """
        The number of points given for each second from the target time
        """
        gate_score = self.get_gate_scorecard(gate_type)
        return gate_score.missed_penalty

    def get_penalty_per_second_for_gate_type(self, gate_type: str) -> float:
        """
        The number of points given for each second from the target time
        """
        gate_score = self.get_gate_scorecard(gate_type)
        return gate_score.penalty_per_second

    def get_maximum_timing_penalty_for_gate_type(self, gate_type: str) -> float:
        """
        The maximum penalty that can be awarded for being off time
        """
        gate_score = self.get_gate_scorecard(gate_type)
        return gate_score.maximum_penalty

    def get_graceperiod_before_for_gate_type(self, gate_type: str) -> float:
        """
        The number of seconds the gate can be passed early without giving penalty
        """
        gate_score = self.get_gate_scorecard(gate_type)
        return gate_score.graceperiod_before

    def get_graceperiod_after_for_gate_type(self, gate_type: str) -> float:
        """
        The number of seconds the gate can be passed late without giving penalty
        """
        gate_score = self.get_gate_scorecard(gate_type)
        return gate_score.graceperiod_after

    def get_procedure_turn_penalty_for_gate_type(self, gate_type: str) -> float:
        """
        The penalty for missing a procedure turn
        """
        gate_score = self.get_gate_scorecard(gate_type)
        return gate_score.missed_procedure_turn_penalty

    def get_bad_crossing_extended_gate_penalty_for_gate_type(self, gate_type: str) -> float:
        """
        The penalty for crossing the extended starting line backwards
        """
        gate_score = self.get_gate_scorecard(gate_type)
        return gate_score.bad_crossing_extended_gate_penalty

    def get_extended_gate_width_for_gate_type(self, gate_type: str) -> float:
        """
        The width of the extended gate line
        """
        gate_score = self.get_gate_scorecard(gate_type)
        return gate_score.extended_gate_width

    def get_backtracking_after_steep_gate_grace_period_seconds_for_gate_type(self, gate_type: str) -> float:
        """
        The number of seconds after passing a gate with a steep turn (more than 90 degrees) where backtracking is not calculated
        """
        gate_score = self.get_gate_scorecard(gate_type)
        return gate_score.backtracking_after_steep_gate_grace_period_seconds

    def get_backtracking_before_gate_grace_period_nm_for_gate_type(self, gate_type: str) -> float:
        """
        The number of NM around a gate where backtracking is not calculated
        """
        gate_score = self.get_gate_scorecard(gate_type)
        return gate_score.backtracking_before_gate_grace_period_nm

    def get_backtracking_after_gate_grace_period_nm_for_gate_type(self, gate_type: str) -> float:
        """
        The number of NM around a gate where backtracking is not calculated
        """
        gate_score = self.get_gate_scorecard(gate_type)
        return gate_score.backtracking_after_gate_grace_period_nm


class GateScore(models.Model):
    """
    Describes the scoring parameters for a specific gate type. There can be only one gate score for a given gate type
    and scorecard.
    """

    scorecard = models.ForeignKey("Scorecard", on_delete=models.CASCADE)
    gate_type = models.CharField(choices=GATE_TYPES, max_length=20)
    included_fields = MyPickledObjectField(
        default=list, help_text="List of field names that should be visible in forms"
    )
    extended_gate_width = models.FloatField(
        default=0,
        help_text="For SP it is 2 (1 nm each side), for tp with procedure turn it is 6",
    )
    bad_crossing_extended_gate_penalty = models.FloatField(default=200)
    graceperiod_before = models.FloatField(default=3)
    graceperiod_after = models.FloatField(default=3)
    maximum_penalty = models.FloatField(default=100)
    penalty_per_second = models.FloatField(default=2)
    missed_penalty = models.FloatField(default=100)
    hit_bonus = models.FloatField(default=0)
    bad_course_crossing_penalty = models.FloatField(default=0)
    missed_procedure_turn_penalty = models.FloatField(default=200)
    backtracking_after_steep_gate_grace_period_seconds = models.FloatField(default=0)
    backtracking_before_gate_grace_period_nm = models.FloatField(default=0)
    backtracking_after_gate_grace_period_nm = models.FloatField(default=0.5)

    class Meta:
        unique_together = ("scorecard", "gate_type")
        ordering = ("gate_type",)

    def __str__(self):
        return f"{self.scorecard.name} - {self.get_gate_type_display()}"

    @property
    def visible_fields(self) -> list[str]:
        """
        The list of field names that should be visible in the GUI.
        """
        return [field for block in self.included_fields for field in block[1:]]

    def calculate_score(
        self,
        planned_time: datetime.datetime,
        actual_time: Optional[datetime.datetime],
    ) -> float:
        """
        Given the planned passing time and the actual passing time, calculate the timing penalty for the gate.  If
        actual_time is None, then, the gate is treated as missed.
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
            score = (round(abs(time_difference) - grace_limit)) * self.penalty_per_second
            if self.maximum_penalty > 0:
                return min(self.maximum_penalty, score)
            elif self.maximum_penalty < 0:
                return max(self.maximum_penalty, score)
            return score
