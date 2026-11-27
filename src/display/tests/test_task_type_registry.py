"""
The task type registry (display.utilities.task_types) is the single source of truth. These tests pin the values the
old per-module tables had, so an edit of the registry that changes behaviour is caught.
"""

from django.test import SimpleTestCase

from display.utilities.task_types import (
    DEFAULT_SCORECARD_SHORTCUT_NAMES,
    FAMILY_CHOICES,
    RULE_SET_ANNEX_9,
    RULE_SET_CIMA_ANNEX_4,
    RULE_SET_LEGACY,
    RULE_SETS,
    TASK_TYPE_REGISTRY,
    TASK_TYPE_SCORECARD_SHORTCUT_NAMES,
    UNSPECIFIED_TASK_TYPE,
    UnknownTaskType,
    default_task_type_for_family,
    find_task_type,
    get_calculators_for_task,
    get_task_type,
    stored_task_type,
    task_type_for,
    task_types_in_rule_set,
)

# Field order of the first definition table: key, display_name, coarse_family, requires_contestant_configuration,
# declaration_schema_key, scoring_modules, scorecard_shortcut_name. (The table below also still holds the required and
# forbidden primitives the registry had before routes had structured requirements; they are dropped from it, and the
# route requirements are tested in test_route_requirements.py.)
_DEFINITION_FIELDS = (
    "key",
    "display_name",
    "coarse_family",
    "requires_contestant_configuration",
    "declaration_schema_key",
    "scoring_modules",
    "scorecard_shortcut_name",
)


_PREVIOUS_DEFINITIONS_WITH_PRIMITIVES = {
    "legacy_precision": (
        "legacy_precision",
        "Legacy precision navigation",
        "precision",
        False,
        ("route_path", "route_waypoint"),
        (),
        None,
        (),
        None,
    ),
    "legacy_anr_corridor": (
        "legacy_anr_corridor",
        "Legacy ANR corridor",
        "anr_corridor",
        False,
        ("route_path", "route_waypoint"),
        ("dummy_waypoint", "unknown_leg"),
        None,
        (),
        None,
    ),
    "legacy_airsports": (
        "legacy_airsports",
        "Legacy Air Sports Race",
        "airsports",
        False,
        ("route_path", "route_waypoint"),
        ("dummy_waypoint", "unknown_leg"),
        None,
        (),
        None,
    ),
    "legacy_airsport_challenge": (
        "legacy_airsport_challenge",
        "Legacy Air Sport Challenge",
        "airsportchallenge",
        False,
        ("route_path", "route_waypoint"),
        ("dummy_waypoint", "unknown_leg"),
        None,
        (),
        None,
    ),
    "legacy_poker": (
        "legacy_poker",
        "Legacy poker run",
        "poker",
        False,
        ("route_path", "route_waypoint"),
        (),
        None,
        (),
        None,
    ),
    "legacy_landing": ("legacy_landing", "Legacy landing", "landing", False, ("landing_gate",), (), None, (), None),
    "curve_navigation_time_estimation": (
        "curve_navigation_time_estimation",
        "2.A1 Curve navigation with time estimation",
        "precision",
        True,
        ("route_path", "route_waypoint"),
        (),
        "curve_navigation_time_estimation",
        ("visible_time_gates", "hidden_gate_sequence", "backtracking"),
        "CIMA Precision",
    ),
    "precision_navigation": (
        "precision_navigation",
        "2.A2 Precision navigation",
        "precision",
        True,
        ("route_path", "route_waypoint"),
        (),
        "precision_navigation",
        ("visible_eta", "hidden_gate_sequence", "backtracking"),
        "CIMA Precision",
    ),
    "contract_navigation_time_controls": (
        "contract_navigation_time_controls",
        "2.A3 Contract navigation with time controls",
        "precision",
        True,
        ("route_path", "route_waypoint", "catalogue_turnpoint"),
        (),
        "contract_navigation_time_controls",
        ("declared_sequence", "mandatory_time_points", "backtracking"),
        "CIMA Precision",
    ),
    "known_circuit": (
        "known_circuit",
        "2.A4 Navigation over a known circuit",
        "precision",
        True,
        ("route_path", "route_waypoint"),
        (),
        None,
        ("observation_evidence", "hidden_gate_sequence", "backtracking"),
        "CIMA Precision",
    ),
    "unknown_legs": (
        "unknown_legs",
        "2.A5 Navigation with unknown legs",
        "precision",
        False,
        ("route_path", "route_waypoint", "unknown_leg"),
        (),
        None,
        ("unknown_leg_sequence", "observation_evidence", "backtracking"),
        "CIMA Precision",
    ),
    "turnpoint_hunt": (
        "turnpoint_hunt",
        "2.A6 Turnpoint hunt",
        "precision",
        True,
        ("catalogue_turnpoint", "known_time_gate"),
        (),
        "turnpoint_hunt",
        ("predicted_sequence", "compulsory_timing_gates", "observation_evidence"),
        "CIMA Precision",
    ),
    "circle": (
        "circle",
        "2.A7 Circle",
        "precision",
        False,
        ("circle_center_marker", "circle_start_marker", "circle_entry_marker", "circle_exit_marker"),
        (),
        None,
        ("circle_entry", "circle_radius", "circle_direction", "altitude_spread"),
        "CIMA Precision",
    ),
    "anr_catalogue": (
        "anr_catalogue",
        "2.A8 Precision navigation Air Nav Race (ANR)",
        "anr_corridor",
        False,
        ("route_path", "route_waypoint"),
        (),
        None,
        ("route_to_sp", "route_from_fp", "takeoff_timing", "quarantine"),
        "CIMA ANR",
    ),
    "limited_fuel_turnpoint_hunt": (
        "limited_fuel_turnpoint_hunt",
        "2.B2 Limited fuel turnpoint hunt",
        "precision",
        True,
        ("catalogue_turnpoint", "known_time_gate"),
        (),
        "limited_fuel_turnpoint_hunt",
        ("all_gate_crossings", "compulsory_timing_gates", "observation_evidence", "fuel_compliance"),
        "CIMA Precision",
    ),
    "duration": ("duration", "2.B3 Duration", "precision", False, (), (), None, (), None),
}
PREVIOUS_DEFINITIONS = {
    key: values[:4] + values[6:] for key, values in _PREVIOUS_DEFINITIONS_WITH_PRIMITIVES.items()
}
PREVIOUS_NO_BACKBONE = ("circle", "turnpoint_hunt", "limited_fuel_turnpoint_hunt", "duration")
PREVIOUS_ABSOLUTE_TIME = {
    "turnpoint_hunt": "compulsory_point_times",
    "limited_fuel_turnpoint_hunt": "compulsory_point_times",
    "precision_navigation": "known_time_gate_predictions",
    "curve_navigation_time_estimation": "known_time_gate_predictions",
    "known_circuit": "turnpoint_time_overrides",
}
PREVIOUS_LEGACY_DEFAULTS = {
    "precision": "legacy_precision",
    "anr_corridor": "legacy_anr_corridor",
    "airsports": "legacy_airsports",
    "airsportchallenge": "legacy_airsport_challenge",
    "poker": "legacy_poker",
    "landing": "legacy_landing",
}
# The scoring model of each task type (display.services.task_scoring): (model, qmax policy, where Q starts, the fixed
# starting quality, the absolute reference). Every other task type uses the penalty model.
EXPECTED_QUALITY_SCORING = {
    "curve_navigation_time_estimation": ("quality", "best_in_task", "gate_deficit", None, None),
    "precision_navigation": ("quality", "best_in_task", "gate_deficit", None, None),
    "contract_navigation_time_controls": ("quality", "best_in_task", "gate_deficit", None, None),
    "known_circuit": ("quality", "best_in_task", "gate_deficit", None, None),
    "unknown_legs": ("quality", "best_in_task", "gate_deficit", None, None),
    "turnpoint_hunt": ("quality", "best_in_task", "achievement", None, None),
    "limited_fuel_turnpoint_hunt": ("quality", "best_in_task", "achievement", None, None),
    "duration": ("quality", "best_in_task", "achievement", None, None),
    "circle": ("quality", "absolute", "fixed", 250, None),
    "anr_catalogue": ("quality", "absolute", "fixed", 2000, 2000),
}
PREVIOUS_DECLARATION_REQUIRED = {
    "contract_navigation_time_controls",
    "precision_navigation",
    "curve_navigation_time_estimation",
    "turnpoint_hunt",
}
PREVIOUS_SUBTYPE_SHORTCUTS = {"CIMA Precision", "CIMA ANR"}


def _pipeline(task_type_key):
    return TASK_TYPE_REGISTRY[task_type_key].get_calculators()


def _contestant(family, subtype=None):
    from unittest.mock import MagicMock

    contestant = MagicMock()
    contestant.navigation_task.scorecard.calculator = family
    contestant.navigation_task.task_subtype = subtype
    return contestant


def _task(family, subtype=None):
    return _contestant(family, subtype).navigation_task


class TestRegistryResolvesStoredValues(SimpleTestCase):
    def test_every_previous_subtype_resolves(self):
        for key in PREVIOUS_DEFINITIONS:
            self.assertEqual(get_task_type(key).key, key)

    def test_every_family_resolves_to_a_default_task_type(self):
        for family, _label in FAMILY_CHOICES:
            definition = default_task_type_for_family(family)
            self.assertIsNotNone(definition, family)
            self.assertEqual(definition.coarse_family, family)

    def test_unknown_key(self):
        with self.assertRaises(UnknownTaskType):
            get_task_type("nonsense")
        self.assertIsNone(find_task_type("nonsense"))
        self.assertIsNone(find_task_type(None))

    def test_registry_has_nothing_beyond_the_previous_subtypes(self):
        self.assertEqual(set(TASK_TYPE_REGISTRY), set(PREVIOUS_DEFINITIONS))

    def test_every_task_type_is_in_exactly_one_rule_set(self):
        seen = []
        for rule_set in RULE_SETS.values():
            seen.extend(item.key for item in task_types_in_rule_set(rule_set))
        self.assertEqual(sorted(seen), sorted(TASK_TYPE_REGISTRY))
        for definition in TASK_TYPE_REGISTRY.values():
            self.assertIn(definition.rule_set.key, RULE_SETS)

    def test_rule_set_membership(self):
        self.assertEqual(
            {item.coarse_family for item in task_types_in_rule_set(RULE_SET_ANNEX_9)},
            {"airsports", "airsportchallenge"},
        )
        self.assertEqual(
            {item.catalogue_code for item in task_types_in_rule_set(RULE_SET_CIMA_ANNEX_4)},
            {"2.A1", "2.A2", "2.A3", "2.A4", "2.A5", "2.A6", "2.A7", "2.A8", "2.B2", "2.B3"},
        )
        self.assertTrue(all(item.catalogue_code is None for item in task_types_in_rule_set(RULE_SET_LEGACY)))

    def test_task_type_for_uses_stored_subtype_or_family_default(self):
        from unittest.mock import MagicMock

        task = MagicMock()
        task.effective_task_subtype = "circle"
        self.assertEqual(task_type_for(task).key, "circle")
        task.effective_task_subtype = None
        self.assertIsNone(task_type_for(task))


class TestRegistryHoldsPreviousContents(SimpleTestCase):
    def test_subtype_definitions(self):
        self.assertEqual(
            {key: tuple(getattr(d, f) for f in _DEFINITION_FIELDS) for key, d in TASK_TYPE_REGISTRY.items()},
            PREVIOUS_DEFINITIONS,
        )
        self.assertEqual(list(TASK_TYPE_REGISTRY), list(PREVIOUS_DEFINITIONS))

    def test_no_backbone(self):
        self.assertEqual({key for key, d in TASK_TYPE_REGISTRY.items() if not d.has_backbone}, set(PREVIOUS_NO_BACKBONE))

    def test_absolute_time(self):
        self.assertEqual(
            {
                key: d.absolute_time_declaration_key
                for key, d in TASK_TYPE_REGISTRY.items()
                if d.absolute_time_declaration_key is not None
            },
            PREVIOUS_ABSOLUTE_TIME,
        )

    def test_declaration_required(self):
        self.assertEqual({key for key, d in TASK_TYPE_REGISTRY.items() if d.declaration_required}, PREVIOUS_DECLARATION_REQUIRED)

    def test_legacy_defaults(self):
        self.assertEqual({d.coarse_family: d.key for d in TASK_TYPE_REGISTRY.values() if d.default_for_family}, PREVIOUS_LEGACY_DEFAULTS)

    def test_legacy_task_types_are_the_ones_with_legacy_keys(self):
        self.assertEqual({key for key, d in TASK_TYPE_REGISTRY.items() if d.is_legacy}, set(PREVIOUS_LEGACY_DEFAULTS.values()))
        for key, definition in TASK_TYPE_REGISTRY.items():
            self.assertEqual(definition.is_legacy, key.startswith("legacy_"), key)

    def test_scoring_model_defaults(self):
        self.assertEqual(
            {
                key: (d.scoring_model, d.qmax_policy, d.quality_start, d.fixed_quality, d.absolute_reference)
                for key, d in TASK_TYPE_REGISTRY.items()
                if d.scoring_model == "quality"
            },
            EXPECTED_QUALITY_SCORING,
        )
        for key, definition in TASK_TYPE_REGISTRY.items():
            if key not in EXPECTED_QUALITY_SCORING:
                self.assertEqual("penalties", definition.scoring_model, key)

    def test_subtype_scorecard_shortcut_names(self):
        self.assertEqual(set(TASK_TYPE_SCORECARD_SHORTCUT_NAMES), PREVIOUS_SUBTYPE_SHORTCUTS)

    def test_default_scorecard_shortcut_names(self):
        self.assertEqual(DEFAULT_SCORECARD_SHORTCUT_NAMES, {"airsports": "Air Sports Race 2025"})

    def test_navigation_task_types(self):
        self.assertEqual(
            FAMILY_CHOICES,
            (
                ("precision", "Precision"),
                ("anr_corridor", "ANR Corridor"),
                ("airsports", "Air Sports Race"),
                ("airsportchallenge", "Air Sport Challenge"),
                ("poker", "Poker run"),
                ("landing", "Landing"),
            ),
        )

    def test_behaviour_flags(self):
        def having(field):
            return {key for key, d in TASK_TYPE_REGISTRY.items() if getattr(d, field)}

        self.assertEqual(
            having("repeated_hidden_gate_crossing_invalidates"),
            {"curve_navigation_time_estimation", "precision_navigation", "known_circuit", "unknown_legs"},
        )
        cima_backtracking_types = {
            "curve_navigation_time_estimation",
            "precision_navigation",
            "contract_navigation_time_controls",
            "known_circuit",
            "unknown_legs",
        }
        self.assertEqual(
            {key for key, d in TASK_TYPE_REGISTRY.items() if d.backtracking_penalty_percentage},
            cima_backtracking_types,
        )
        self.assertEqual(having("backtracking_within_corridor"), cima_backtracking_types)
        self.assertEqual(having("scores_turnpoint_hunt_targets"), {"turnpoint_hunt", "limited_fuel_turnpoint_hunt"})
        self.assertEqual(having("has_fuel_deadline"), {"limited_fuel_turnpoint_hunt"})
        self.assertEqual(having("scores_speed_keeping"), {"known_circuit"})
        self.assertEqual(having("has_post_mp_rule"), {"contract_navigation_time_controls"})
        self.assertEqual(having("gate_times_from_declared_period"), {"contract_navigation_time_controls"})
        self.assertEqual(having("general_map_shows_backbone_only"), {"contract_navigation_time_controls"})
        self.assertEqual(having("has_auxiliary_route_checks"), {"anr_catalogue"})
        self.assertEqual(having("scores_takeoff_timing"), {"anr_catalogue"})
        self.assertEqual(having("has_unknown_legs"), {"unknown_legs"})
        self.assertEqual(having("observation_photos_award_points"), {"known_circuit", "unknown_legs"})
        self.assertEqual(having("scores_circle"), {"circle"})
        self.assertEqual(having("scores_duration"), {"duration"})
        self.assertEqual(
            {key for key, d in TASK_TYPE_REGISTRY.items() if not d.has_backtracking_detection},
            # The turnpoint hunts have no backtracking penalty in the catalogue (2.A6, 2.B2).
            {"circle", "legacy_landing", "legacy_poker", "turnpoint_hunt", "limited_fuel_turnpoint_hunt"},
        )
        self.assertEqual(having("free_order_gate_matching"), {"limited_fuel_turnpoint_hunt"})

    def test_contestant_strategies(self):
        self.assertEqual(
            {key: d.contestant_compiler_strategy.rsplit(".", 1)[1] for key, d in TASK_TYPE_REGISTRY.items() if d.contestant_compiler_strategy},
            {
                "curve_navigation_time_estimation": "CurveOrPrecisionNavigationStrategy",
                "precision_navigation": "CurveOrPrecisionNavigationStrategy",
                "contract_navigation_time_controls": "ContractNavigationStrategy",
                "turnpoint_hunt": "TurnpointHuntStrategy",
                "limited_fuel_turnpoint_hunt": "TurnpointHuntStrategy",
                "duration": "DurationStrategy",
                "circle": "CircleStrategy",
                "known_circuit": "KnownCircuitStrategy",
                "unknown_legs": "UnknownLegsStrategy",
            },
        )
        for definition in TASK_TYPE_REGISTRY.values():
            if definition.contestant_compiler_strategy:
                from django.utils.module_loading import import_string

                import_string(definition.contestant_compiler_strategy)

    def test_gate_types_without_backbone_exist_exactly_for_task_types_without_backbone(self):
        for key, definition in TASK_TYPE_REGISTRY.items():
            self.assertEqual(bool(definition.gate_types_without_backbone), not definition.has_backbone, key)

    def test_unspecified_task_type_does_nothing_special(self):
        self.assertIsNone(find_task_type(UNSPECIFIED_TASK_TYPE.key))
        for task in (_task("precision"), _task("precision", ""), _task("precision", "nonsense")):
            self.assertIs(stored_task_type(task), UNSPECIFIED_TASK_TYPE)
        self.assertEqual(stored_task_type(_task("precision", "circle")).key, "circle")
        self.assertTrue(UNSPECIFIED_TASK_TYPE.has_backbone)
        self.assertFalse(UNSPECIFIED_TASK_TYPE.declaration_required)
        self.assertEqual("penalties", UNSPECIFIED_TASK_TYPE.scoring_model)


class TestCalculatorPipelines(SimpleTestCase):
    def _classes(self, *names):
        from display.calculators.anr_corridor_calculator import AnrCorridorCalculator
        from display.calculators.backtracking_and_procedure_turns import BacktrackingAndProcedureTurnsCalculator
        from display.calculators.circle_calculator import CircleCalculator
        from display.calculators.duration_calculator import DurationCalculator
        from display.calculators.gate_calculator import GateCalculator
        from display.calculators.landing_pattern_calculator import LandingPatternCalculator
        from display.calculators.penalty_zone_calculator import PenaltyZoneCalculator
        from display.calculators.poker_calculator import PokerCalculator
        from display.calculators.prohibited_zone_calculator import ProhibitedZoneCalculator
        from display.calculators.speed_inferred_takeoff_landing_calculator import (
            SpeedInferredTakeoffLandingCalculator,
        )
        from display.calculators.takeoff_and_landing_gate_calculator import TakeoffAndLandingGateCalculator

        return [
            {
                "Anr": AnrCorridorCalculator,
                "Backtracking": BacktrackingAndProcedureTurnsCalculator,
                "Circle": CircleCalculator,
                "Duration": DurationCalculator,
                "Gate": GateCalculator,
                "Landing": LandingPatternCalculator,
                "PenaltyZone": PenaltyZoneCalculator,
                "Poker": PokerCalculator,
                "ProhibitedZone": ProhibitedZoneCalculator,
                "SpeedInferred": SpeedInferredTakeoffLandingCalculator,
                "TakeoffLanding": TakeoffAndLandingGateCalculator,
            }[name]
            for name in names
        ]

    def test_precision(self):
        expected = self._classes("Gate", "TakeoffLanding", "Backtracking", "ProhibitedZone", "PenaltyZone")
        self.assertEqual(_pipeline("legacy_precision"), expected)
        self.assertEqual(get_calculators_for_task(_task("precision")), expected)
        for key in (
            "curve_navigation_time_estimation",
            "precision_navigation",
            "contract_navigation_time_controls",
            "known_circuit",
            "unknown_legs",
        ):
            self.assertEqual(_pipeline(key), expected, key)
            self.assertEqual(get_calculators_for_task(_task("precision", key)), expected)

    def test_turnpoint_hunts_have_no_backtracking_calculator(self):
        # The catalogue has no backtracking penalty for 2.A6 and 2.B2.
        expected = self._classes("Gate", "TakeoffLanding", "ProhibitedZone", "PenaltyZone")
        for key in ("turnpoint_hunt", "limited_fuel_turnpoint_hunt"):
            self.assertEqual(_pipeline(key), expected, key)
            self.assertEqual(get_calculators_for_task(_task("precision", key)), expected)

    def test_circle(self):
        expected = self._classes("Gate", "Circle", "TakeoffLanding", "ProhibitedZone", "PenaltyZone")
        self.assertEqual(_pipeline("circle"), expected)
        self.assertEqual(get_calculators_for_task(_task("precision", "circle")), expected)

    def test_duration(self):
        expected = self._classes(
            "Gate", "TakeoffLanding", "SpeedInferred", "Duration", "Backtracking", "ProhibitedZone", "PenaltyZone"
        )
        self.assertEqual(_pipeline("duration"), expected)
        self.assertEqual(get_calculators_for_task(_task("precision", "duration")), expected)

    def test_anr_style(self):
        expected = self._classes("Gate", "TakeoffLanding", "Backtracking", "Anr", "ProhibitedZone", "PenaltyZone")
        for key, family in (
            ("legacy_anr_corridor", "anr_corridor"),
            ("anr_catalogue", "anr_corridor"),
            ("legacy_airsports", "airsports"),
            ("legacy_airsport_challenge", "airsportchallenge"),
        ):
            self.assertEqual(_pipeline(key), expected, key)
            self.assertEqual(get_calculators_for_task(_task(family)), expected)

    def test_landing_and_poker(self):
        self.assertEqual(_pipeline("legacy_landing"), self._classes("Landing"))
        self.assertEqual(_pipeline("legacy_poker"), self._classes("Poker", "ProhibitedZone", "PenaltyZone"))
        self.assertEqual(get_calculators_for_task(_task("landing")), self._classes("Landing"))

    def test_default_builder_for_unknown_family(self):
        self.assertEqual(get_calculators_for_task(_task("something")), self._classes("Gate"))

    def test_subtype_of_another_family_is_ignored(self):
        expected = self._classes("Gate", "TakeoffLanding", "Backtracking", "ProhibitedZone", "PenaltyZone")
        self.assertEqual(get_calculators_for_task(_task("precision", "anr_catalogue")), expected)
