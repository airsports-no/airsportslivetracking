from datetime import datetime

from django.test import TestCase

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import CompiledNavigationTask, Contest, NavigationTask, Route, Scorecard
from display.utilities.cima_task_type_definitions import (
    ANR_CATALOGUE,
    CURVE_NAVIGATION_TIME_ESTIMATION,
    DURATION,
    LEGACY_ANR_CORRIDOR,
    LEGACY_PRECISION,
    get_default_task_subtype_for_family,
    get_task_subtype_definition,
    validate_subtype_family_compatibility,
)
from display.utilities.task_information import build_navigation_task_information, build_navigation_task_rules_latex


class TestCimaTaskSubtypes(TestCase):
    def setUp(self):
        create_scorecards()
        self.contest = Contest.objects.create(
            name="Subtype test contest",
            start_time=datetime.utcnow(),
            finish_time=datetime.utcnow(),
            time_zone="Europe/Oslo",
        )
        self.route = Route.objects.create(name="Subtype route", waypoints=[], takeoff_gates=[], landing_gates=[])

    def test_get_task_subtype_definition_returns_precision_mapping(self):
        definition = get_task_subtype_definition(CURVE_NAVIGATION_TIME_ESTIMATION)
        self.assertEqual(definition.coarse_family, "precision")
        self.assertTrue(definition.requires_contestant_configuration)

    def test_validate_subtype_family_compatibility_allows_blank(self):
        validate_subtype_family_compatibility(None, "precision")
        validate_subtype_family_compatibility("", "precision")

    def test_validate_subtype_family_compatibility_rejects_mismatch(self):
        with self.assertRaises(ValueError):
            validate_subtype_family_compatibility(ANR_CATALOGUE, "precision")

    def test_navigation_task_can_store_subtype_and_config(self):
        scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        task = NavigationTask.create(
            name="Subtype task",
            contest=self.contest,
            route=self.route,
            original_scorecard=scorecard,
            start_time=datetime.utcnow(),
            finish_time=datetime.utcnow(),
            task_subtype=CURVE_NAVIGATION_TIME_ESTIMATION,
            task_config={"source": "test"},
        )
        self.assertEqual(task.task_subtype, CURVE_NAVIGATION_TIME_ESTIMATION)
        self.assertEqual(task.task_config, {"source": "test"})
        self.assertEqual(task.coarse_task_family, "precision")
        self.assertEqual(task.subtype_definition.key, CURVE_NAVIGATION_TIME_ESTIMATION)

    def test_duration_subtype_definition_maps_to_precision_family(self):
        definition = get_task_subtype_definition(DURATION)
        self.assertEqual(definition.coarse_family, "precision")
        self.assertFalse(definition.requires_contestant_configuration)

    def test_default_legacy_subtype_for_precision_family_is_available(self):
        self.assertEqual(get_default_task_subtype_for_family("precision"), LEGACY_PRECISION)

    def test_default_legacy_subtype_for_anr_family_is_available(self):
        self.assertEqual(get_default_task_subtype_for_family("anr_corridor"), LEGACY_ANR_CORRIDOR)

    def test_legacy_precision_task_gets_default_subtype_definition(self):
        scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        task = NavigationTask.create(
            name="Legacy precision task",
            contest=self.contest,
            route=self.route,
            original_scorecard=scorecard,
            start_time=datetime.utcnow(),
            finish_time=datetime.utcnow(),
        )
        self.assertEqual(task.task_subtype, None)
        self.assertEqual(task.subtype_definition.key, LEGACY_PRECISION)
        self.assertFalse(task.requires_contestant_task_configuration())

    def test_legacy_anr_task_gets_default_subtype_definition(self):
        scorecard = Scorecard.get_originals().get(shortcut_name="FAI ANR")
        task = NavigationTask.create(
            name="Legacy ANR task",
            contest=self.contest,
            route=self.route,
            original_scorecard=scorecard,
            start_time=datetime.utcnow(),
            finish_time=datetime.utcnow(),
        )
        self.assertEqual(task.task_subtype, None)
        self.assertEqual(task.subtype_definition.key, LEGACY_ANR_CORRIDOR)
        self.assertFalse(task.requires_contestant_task_configuration())

    def test_legacy_precision_scorecard_already_uses_max_score_minus_penalties_semantics(self):
        scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        self.assertEqual(scorecard.score_sorting_direction, "asc")
        self.assertEqual(scorecard.initial_score, 0)

    def test_task_compiler_uses_default_legacy_precision_subtype_when_task_subtype_blank(self):
        from display.services.task_compiler import TaskCompiler

        scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        task = NavigationTask.create(
            name="Compiled legacy precision task",
            contest=self.contest,
            route=self.route,
            original_scorecard=scorecard,
            start_time=datetime.utcnow(),
            finish_time=datetime.utcnow(),
        )

        compiled = TaskCompiler(task).compile(force=True)

        self.assertIsInstance(compiled, CompiledNavigationTask)
        self.assertEqual(compiled.task_subtype, LEGACY_PRECISION)
        self.assertEqual(compiled.compiled_payload["task_subtype"], LEGACY_PRECISION)

    def test_task_compiler_uses_default_legacy_anr_subtype_when_task_subtype_blank(self):
        from display.services.task_compiler import TaskCompiler

        scorecard = Scorecard.get_originals().get(shortcut_name="FAI ANR")
        task = NavigationTask.create(
            name="Compiled legacy ANR task",
            contest=self.contest,
            route=self.route,
            original_scorecard=scorecard,
            start_time=datetime.utcnow(),
            finish_time=datetime.utcnow(),
        )

        compiled = TaskCompiler(task).compile(force=True)

        self.assertIsInstance(compiled, CompiledNavigationTask)
        self.assertEqual(compiled.task_subtype, LEGACY_ANR_CORRIDOR)
        self.assertEqual(compiled.compiled_payload["task_subtype"], LEGACY_ANR_CORRIDOR)

    def test_build_navigation_task_information_includes_subtype_labels(self):
        scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        task = NavigationTask.create(
            name="Circle info task",
            contest=self.contest,
            route=self.route,
            original_scorecard=scorecard,
            start_time=datetime.utcnow(),
            finish_time=datetime.utcnow(),
            task_subtype="circle",
            task_config={"circle_radius_min_m": 250, "circle_radius_max_m": 800},
        )

        info = build_navigation_task_information(task)

        self.assertEqual(info["family_display_name"], "Precision navigation")
        self.assertEqual(info["subtype_display_name"], "2.A7 Circle")
        self.assertIn("Configured radius band is 250 m to 800 m.", info["overrides"])

    def test_build_navigation_task_rules_latex_contains_task_family_and_subtype(self):
        scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        task = NavigationTask.create(
            name="Circle rules task",
            contest=self.contest,
            route=self.route,
            original_scorecard=scorecard,
            start_time=datetime.utcnow(),
            finish_time=datetime.utcnow(),
            task_subtype="circle",
            task_config={"circle_radius_min_m": 250, "circle_radius_max_m": 800},
        )

        latex = build_navigation_task_rules_latex(task)

        self.assertIn("Task family: Precision navigation", latex)
        self.assertIn("Task subtype: 2.A7 Circle", latex)
        self.assertIn("Configured radius band is 250 m to 800 m.", latex)
