import dataclasses
import datetime
import uuid
from typing import Optional

from django.core.cache import cache
from django.db import models
from django.db.models import QuerySet

from display.fields.my_pickled_object_field import MyPickledObjectField
from display.utilities.clone_object import simple_clone
from display.utilities.gate_definitions import GATE_TYPES
from display.utilities.navigation_task_type_definitions import NAVIGATION_TASK_TYPES, PRECISION

DURATION_NORMALIZATION_POLICIES = (("", "---------"), ("raw_minutes", "Raw minutes"))

_GATE_TYPE_DISPLAY_NAMES = dict(GATE_TYPES)

# The 26 scoring-parameter fields Phase 2 of the scorecard-system review roadmap moved off of
# real Scorecard columns and onto ConfigField (ie. Scorecard.config-backed) attributes -
# shared by anything that needs to enumerate them (ScorecardForm below, and mirrored by hand
# in serialisers.py's ScorecardNestedSerialiser, whose explicit per-field DRF types can't be
# generated from a plain name list). Kept in sync with SCORECARD_CONFIG_FIELDS in migration
# 0172_scorecard_populate_config.py by hand - migrations must stay self-contained/frozen, so
# that one can't import this constant.
SCORECARD_CONFIG_FIELDS = [
    "backtracking_penalty",
    "backtracking_bearing_difference",
    "backtracking_grace_time_seconds",
    "backtracking_maximum_penalty",
    "prohibited_zone_penalty",
    "prohibited_zone_grace_time",
    "prohibited_zone_maximum",
    "penalty_zone_grace_time",
    "penalty_zone_penalty_per_second",
    "penalty_zone_maximum",
    "corridor_grace_time",
    "corridor_outside_penalty",
    "corridor_maximum_penalty",
    "corridor_maximum_penalty_is_per_leg",
    "anr_route_to_sp_penalty",
    "anr_route_from_fp_penalty",
    "compulsory_timing_tolerance_seconds",
    "maximum_task_duration_minutes",
    "maximum_task_duration_penalty",
    "fuel_deadline_penalty",
    "duration_normalization_policy",
    "duration_residual_fuel_required",
    "circle_radius_min_m",
    "circle_radius_max_m",
    "speed_keeping_tolerance_kt",
    "speed_keeping_penalty_per_kt",
]


class ConfigField(property):
    """
    A "field" backed by Scorecard.config[name] instead of a real database column (Phase 2 of
    the scorecard-system review roadmap - see the roadmap doc, saved outside the repo, for
    full context). Every call site that reads/writes `scorecard.some_field` directly keeps
    working unchanged - this descriptor is what makes that possible without rewriting the
    ~30 direct-attribute-access call sites across calculators, task_information.py,
    contestant.py, navigation_task.py, etc.

    Subclasses `property` (rather than being a plain descriptor) deliberately, and constructs
    itself with real `fget`/`fset` functions (rather than overriding `__get__`/`__set__`
    directly) for two independent reasons both rooted in Django/DRF only special-casing
    genuine `property` behavior, not descriptors in general:

    - `Model.__init__` routes unrecognized keyword arguments through `setattr` only for
      `isinstance(..., property)` class attributes - without that, plain
      `Scorecard(backtracking_penalty=200, ...)` would raise `TypeError`.
    - `QuerySet.get_or_create`/`update_or_create` (used throughout
      `default_scorecards/*.py`) go further: they specifically check
      `getattr(model, param).fset` is truthy before accepting a non-column keyword, so a real
      `fset` function - not just an overridden `__set__` - is required, or every
      `Scorecard.objects.update_or_create(..., defaults={"backtracking_penalty": 200, ...})`
      seed call raises `FieldError: Invalid field name(s)`.

    `__set_name__` (Python's descriptor protocol) fills in `self.name` from the class
    attribute name once, at class-definition time - `_get`/`_set` read it at call time, after
    every field has been named, so the field name only needs to be written once per field (as
    the attribute name), not repeated as a string.
    """

    def __init__(self, default):
        self.default = default
        self.name = None
        super().__init__(self._get, self._set)

    def __set_name__(self, owner, name):
        self.name = name

    def _get(self, instance):
        return instance.config.get(self.name, self.default)

    def _set(self, instance, value):
        instance.config[self.name] = value


@dataclasses.dataclass(frozen=True)
class GateScoreValue:
    """
    A read-only view of one gate's scoring config, backed by
    Scorecard.config["gates"][gate_type] (Phase 2 - GateScore is no longer a database table;
    see the roadmap doc). Same field names, same calculate_score()/visible_fields behavior the
    GateScore model used to have, so every Scorecard.get_*_for_gate_type() delegator and every
    direct `scorecard.get_gate_scorecard(gate_type).<field>` read site keeps working unchanged.

    `bad_course_crossing_penalty` was dropped during the migration - confirmed fully dead
    (zero read sites anywhere in the codebase outside the old model definition).
    """

    gate_type: str
    extended_gate_width: float = 0
    bad_crossing_extended_gate_penalty: float = 200
    graceperiod_before: float = 3
    graceperiod_after: float = 3
    maximum_penalty: float = 100
    penalty_per_second: float = 2
    missed_penalty: float = 100
    missed_procedure_turn_penalty: float = 200
    backtracking_after_steep_gate_grace_period_seconds: float = 0
    backtracking_before_gate_grace_period_nm: float = 0
    backtracking_after_gate_grace_period_nm: float = 0.5
    included_fields: list = dataclasses.field(default_factory=list)

    @classmethod
    def from_dict(cls, gate_type: str, data: dict) -> "GateScoreValue":
        return cls(
            gate_type=gate_type,
            extended_gate_width=data.get("extended_gate_width", 0),
            bad_crossing_extended_gate_penalty=data.get("bad_crossing_extended_gate_penalty", 200),
            graceperiod_before=data.get("graceperiod_before", 3),
            graceperiod_after=data.get("graceperiod_after", 3),
            maximum_penalty=data.get("maximum_penalty", 100),
            penalty_per_second=data.get("penalty_per_second", 2),
            missed_penalty=data.get("missed_penalty", 100),
            missed_procedure_turn_penalty=data.get("missed_procedure_turn_penalty", 200),
            backtracking_after_steep_gate_grace_period_seconds=data.get(
                "backtracking_after_steep_gate_grace_period_seconds", 0
            ),
            backtracking_before_gate_grace_period_nm=data.get("backtracking_before_gate_grace_period_nm", 0),
            backtracking_after_gate_grace_period_nm=data.get("backtracking_after_gate_grace_period_nm", 0.5),
            included_fields=data.get("included_fields", []),
        )

    def to_dict(self) -> dict:
        return {
            "extended_gate_width": self.extended_gate_width,
            "bad_crossing_extended_gate_penalty": self.bad_crossing_extended_gate_penalty,
            "graceperiod_before": self.graceperiod_before,
            "graceperiod_after": self.graceperiod_after,
            "maximum_penalty": self.maximum_penalty,
            "penalty_per_second": self.penalty_per_second,
            "missed_penalty": self.missed_penalty,
            "missed_procedure_turn_penalty": self.missed_procedure_turn_penalty,
            "backtracking_after_steep_gate_grace_period_seconds": (
                self.backtracking_after_steep_gate_grace_period_seconds
            ),
            "backtracking_before_gate_grace_period_nm": self.backtracking_before_gate_grace_period_nm,
            "backtracking_after_gate_grace_period_nm": self.backtracking_after_gate_grace_period_nm,
            "included_fields": self.included_fields,
        }

    def get_gate_type_display(self) -> str:
        return _GATE_TYPE_DISPLAY_NAMES.get(self.gate_type, self.gate_type)

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
    score_sorting_direction = models.CharField(
        choices=(("asc", "Ascending"), ("desc", "Descending")),
        default="asc",
        max_length=4,
        help_text="The direction to sort the scores in the scoreboard",
    )
    initial_score = models.FloatField(
        default=0,
        help_text="Initial score awarded to the contestant it start. This is typically 0, but if the penalties are negative, this can be set to some positive initial value.",
    )
    use_procedure_turns = models.BooleanField(default=True, blank=True)

    # Everything below used to be individual columns (plus a separate GateScore table for
    # per-gate-type config). Phase 2 of the scorecard-system review roadmap moved them into
    # this one JSON blob - see ConfigField's docstring above for how existing
    # `scorecard.some_field` call sites keep working unchanged. The pre-migration columns
    # were renamed to legacy_* (not dropped) by the same migration, as a rollback/verification
    # path - see migration 0173_scorecard_config_rename_legacy_columns.
    #
    # below_minimum_altitude_penalty / below_minimum_altitude_maximum_penalty were dropped
    # entirely rather than migrated - confirmed fully dead (zero read sites anywhere; their
    # own help_text said "not applied automatically").
    config = models.JSONField(default=dict)

    backtracking_penalty = ConfigField(200)
    backtracking_bearing_difference = ConfigField(90)
    backtracking_grace_time_seconds = ConfigField(5)
    backtracking_maximum_penalty = ConfigField(-1)
    prohibited_zone_penalty = ConfigField(200)
    prohibited_zone_grace_time = ConfigField(3)
    prohibited_zone_maximum = ConfigField(0)
    penalty_zone_grace_time = ConfigField(3)
    penalty_zone_penalty_per_second = ConfigField(3)
    penalty_zone_maximum = ConfigField(100)

    ##### ANR Corridor
    corridor_grace_time = ConfigField(5)
    corridor_outside_penalty = ConfigField(3)
    corridor_maximum_penalty = ConfigField(-1)
    corridor_maximum_penalty_is_per_leg = ConfigField(True)
    anr_route_to_sp_penalty = ConfigField(200)
    anr_route_from_fp_penalty = ConfigField(200)

    compulsory_timing_tolerance_seconds = ConfigField(10)
    maximum_task_duration_minutes = ConfigField(None)
    maximum_task_duration_penalty = ConfigField(100)
    fuel_deadline_penalty = ConfigField(100)
    duration_normalization_policy = ConfigField("")
    duration_residual_fuel_required = ConfigField(False)
    circle_radius_min_m = ConfigField(200)
    circle_radius_max_m = ConfigField(750)
    speed_keeping_tolerance_kt = ConfigField(5)
    speed_keeping_penalty_per_kt = ConfigField(1)

    # Renamed out of the way (not dropped) by migration 0173, at the same time these
    # ConfigFields/the included_fields property above took over the un-prefixed attribute
    # names - Django doesn't allow a model field and a same-named property/descriptor to
    # coexist. These columns still hold pre-migration data as a rollback/verification
    # snapshot; nothing reads or writes them anymore. Scheduled for real removal in a later,
    # separate cleanup migration (Phase 2e) once the JSON-backed config has been live for a
    # while. Do not read/write these - use the un-prefixed name (routed through `config`).
    legacy_backtracking_penalty = models.FloatField(
        default=200, help_text="The number of points given for backtracking"
    )
    legacy_backtracking_bearing_difference = models.FloatField(
        default=90,
        help_text="The bearing difference from the leg direction to initiate backtracking",
    )
    legacy_backtracking_grace_time_seconds = models.FloatField(
        default=5,
        help_text="The number of seconds the contestant is allowed to backtrack before backtracking penalty is applied",
    )
    legacy_backtracking_maximum_penalty = models.FloatField(
        default=-1, help_text="Negative numbers means the maximum is ignored"
    )
    legacy_prohibited_zone_penalty = models.FloatField(
        default=200,
        help_text="Penalty for entering prohibited zone such as controlled airspace or other prohibited areas",
    )
    legacy_prohibited_zone_grace_time = models.FloatField(
        default=3,
        help_text="The number of seconds the contestant can be within the prohibited zone before getting penalty",
    )
    legacy_prohibited_zone_maximum = models.FloatField(
        default=0,
        help_text="The maximum score that can be given for entering prohibited zones. Zero means the maximum is ignored",
    )
    legacy_penalty_zone_grace_time = models.FloatField(
        default=3,
        help_text="The number of seconds the contestant can be within the penalty zone before getting penalty",
    )
    legacy_penalty_zone_penalty_per_second = models.FloatField(
        default=3, help_text="The number of points per second beyond the grace time while inside the penalty zone"
    )
    legacy_penalty_zone_maximum = models.FloatField(default=100, help_text="Maximum penalty within a single zone")
    legacy_corridor_grace_time = models.IntegerField(default=5, help_text="The corridor grace time for ANR tasks")
    legacy_corridor_outside_penalty = models.FloatField(
        default=3, help_text="The penalty awarded for leaving the ANR corridor"
    )
    legacy_corridor_maximum_penalty = models.FloatField(
        default=-1, help_text="The maximum penalty for leaving the corridor"
    )
    legacy_corridor_maximum_penalty_is_per_leg = models.BooleanField(
        default=True, help_text="If true, the maximum corridor penalty is reset for each leg"
    )
    legacy_anr_route_to_sp_penalty = models.FloatField(
        default=200,
        help_text="Penalty for not following the auxiliary route to the start point in ANR catalogue tasks",
    )
    legacy_anr_route_from_fp_penalty = models.FloatField(
        default=200,
        help_text="Penalty for not following the auxiliary route from the finish point in ANR catalogue tasks",
    )
    legacy_compulsory_timing_tolerance_seconds = models.IntegerField(default=10)
    legacy_maximum_task_duration_minutes = models.IntegerField(null=True, blank=True)
    legacy_maximum_task_duration_penalty = models.FloatField(default=100)
    legacy_fuel_deadline_penalty = models.FloatField(default=100)
    legacy_duration_normalization_policy = models.CharField(
        max_length=40, blank=True, default="", choices=DURATION_NORMALIZATION_POLICIES
    )
    legacy_duration_residual_fuel_required = models.BooleanField(default=False)
    legacy_circle_radius_min_m = models.FloatField(default=200)
    legacy_circle_radius_max_m = models.FloatField(default=750)
    legacy_speed_keeping_tolerance_kt = models.FloatField(
        default=5,
        help_text="Allowed deviation (in knots) from the declared speed on a known-circuit leg before a speed-keeping penalty applies",
    )
    legacy_speed_keeping_penalty_per_kt = models.FloatField(
        default=1,
        help_text="Penalty per knot of speed deviation beyond the tolerance on a known-circuit leg",
    )
    legacy_included_fields = MyPickledObjectField(
        default=list, help_text="List of field names that should be visible in forms"
    )

    def __str__(self):
        return self.name

    class Meta:
        ordering = ("-valid_from",)

    @property
    def included_fields(self) -> list:
        """
        List of field names that should be visible in forms. Hand-written (not a ConfigField)
        because the default is a mutable list - ConfigField's shared-default would alias the
        same list object across every scorecard that has never set one.
        """
        return self.config.get("included_fields", [])

    @included_fields.setter
    def included_fields(self, value: list) -> None:
        self.config["included_fields"] = value

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
        # `config["gates"]` (including per-gate scoring config) already travelled for free as
        # part of the single-row clone above - simple_clone() re-fetches the whole row,
        # config JSONField included. But GateScore is still what ScorecardNestedSerialiser's
        # `gatescore_set` field, navigation_task_gatescore_override_view, and
        # navigation_task_view_detailed_score read from (see those files - rewriting them to
        # stop depends on GateScore is deferred to a later phase), so a copy needs its own
        # real GateScore rows too, not just config - otherwise every organizer-facing
        # gate-scoring read/edit on a freshly-copied scorecard would silently see no gates.
        for gate in self.gatescore_set.all():
            simple_clone(gate, {"scorecard": obj})
        return obj

    # Process-local: safe because every entry is stamped with the version token below (a
    # value from the shared Redis cache, rewritten by bump_gate_scorecard_cache_version in
    # display/signals.py whenever a Scorecard is saved) and get_gate_scorecard
    # replaces (not accumulates) the entry for a given (pk, gate_type) on a version
    # mismatch - so this stays bounded to one entry per (scorecard, gate_type) actually
    # looked up, not one per edit-since-process-start.
    SCORECARD_CACHE = {}

    def _gate_scorecard_cache_version(self) -> str:
        return cache.get_or_set(f"gate_scorecard_version_{self.pk}", lambda: uuid.uuid4().hex, timeout=None)

    def get_gate_scorecard(self, gate_type: str) -> "GateScoreValue":
        """
        Get the scorecard for a specific gate type.
        """
        cache_key = (self.pk, gate_type)
        current_version = self._gate_scorecard_cache_version()
        cached = self.SCORECARD_CACHE.get(cache_key)
        if cached is not None and cached[0] == current_version:
            return cached[1]
        data = self.config.get("gates", {}).get(gate_type)
        if data is None:
            raise ValueError(f"Unknown gate type '{gate_type}' or undefined score")
        gate_score = GateScoreValue.from_dict(gate_type, data)
        self.SCORECARD_CACHE[cache_key] = (current_version, gate_score)
        return gate_score

    def gate_scores(self) -> list["GateScoreValue"]:
        """
        Every configured gate's scoring config, sorted by gate_type - replaces
        `self.gatescore_set.all().order_by("gate_type")` now that gate config lives in
        config["gates"] instead of a real table.
        """
        gates = self.config.get("gates", {})
        return [GateScoreValue.from_dict(gate_type, data) for gate_type, data in sorted(gates.items())]

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


GATE_SCORE_SYNC_FIELDS = [
    "extended_gate_width",
    "bad_crossing_extended_gate_penalty",
    "graceperiod_before",
    "graceperiod_after",
    "maximum_penalty",
    "penalty_per_second",
    "missed_penalty",
    "missed_procedure_turn_penalty",
    "backtracking_after_steep_gate_grace_period_seconds",
    "backtracking_before_gate_grace_period_nm",
    "backtracking_after_gate_grace_period_nm",
]


class GateScore(models.Model):
    """
    Legacy as of Phase 2 of the scorecard-system review roadmap: actual scoring now reads
    exclusively from Scorecard.config["gates"][gate_type] (see GateScoreValue above), not
    this table. Existing writers (the 11 default_scorecards/*.py seed files,
    ScorecardNestedSerialiser.update(), GateScoreForm) are intentionally left untouched here
    in 2a rather than rewritten - a post_save/post_delete signal pair
    (sync_gate_score_to_scorecard_config in signals.py) transparently mirrors every write into
    the owning Scorecard's config (and bumps its cache-version token via the normal Scorecard
    post_save signal), so those existing call sites keep actually affecting live scoring with
    no code changes of their own. Without this mirroring, any of them would silently write to
    an inert table - see the Phase 2 roadmap doc's "single most dangerous item" callout.
    Rewriting those call sites to stop using this table entirely, and dropping the table for
    real, is deferred to a later cleanup phase once config has been live for a while.
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
