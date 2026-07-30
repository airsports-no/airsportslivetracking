import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from guardian.shortcuts import assign_perm

from display.default_scorecards.create_scorecards import create_scorecards
from display.forms import NavigationTaskForm
from display.models import Contest, EditableRoute, NavigationTask, Scorecard
from display.utilities.cima_task_type_definitions import CIRCLE, DURATION


class TestNavigationTaskFormCimaConfig(TestCase):
    def setUp(self):
        create_scorecards()
        self.user = get_user_model().objects.create(email="navtask-form@example.com")
        self.contest = Contest.objects.create(
            name="Navigation Task Form Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
            created_by=self.user,
        )
        assign_perm("view_contest", self.user, self.contest)
        assign_perm("change_contest", self.user, self.contest)
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("NavigationTaskFormRoute", file.readlines()[1:])
            self.editable_route = editable_route
            self.route = editable_route.create_precision_route(True, self.scorecard)
        self.duration_polygon = [[11.0, 60.0], [11.2, 60.0], [11.2, 60.2], [11.0, 60.2]]

    def test_form_exposes_turnpoint_hunt_config_fields(self):
        form = NavigationTaskForm()
        self.assertIn("compulsory_timing_tolerance_seconds", form.fields)
        self.assertIn("maximum_task_duration_minutes", form.fields)
        self.assertIn("maximum_task_duration_penalty", form.fields)
        self.assertIn("fuel_deadline_penalty", form.fields)

    def test_form_persists_limited_fuel_turnpoint_hunt_task_config(self):
        form = NavigationTaskForm(
            data={
                "name": "Turnpoint Hunt Form Task",
                "start_time": "2026-08-01T09:00",
                "finish_time": "2026-08-01T17:00",
                "display_background_map": True,
                "display_secrets": True,
                "minutes_to_starting_point": 5,
                "planning_time": 45,
                "original_scorecard": self.scorecard.pk,
                "task_subtype": "limited_fuel_turnpoint_hunt",
                "minutes_to_landing": 30,
                "wind_speed": 0,
                "wind_direction": 0,
                "allow_self_management": True,
                "calculation_delay_minutes": 0,
                "compulsory_timing_tolerance_seconds": 8,
                "maximum_task_duration_minutes": 45,
                "maximum_task_duration_penalty": 123,
                "fuel_deadline_penalty": 77,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        navigation_task = form.save(commit=False)
        navigation_task.contest = self.contest
        navigation_task.route = self.route
        navigation_task.editable_route = self.editable_route
        navigation_task.save()
        self.assertEqual(navigation_task.task_subtype, "limited_fuel_turnpoint_hunt")
        self.assertEqual(
            navigation_task.task_config,
            {
                "compulsory_timing_tolerance_seconds": 8,
                "maximum_task_duration_minutes": 45,
                "maximum_task_duration_penalty": 123.0,
                "fuel_deadline_penalty": 77.0,
            },
        )

    def test_form_hides_fuel_penalty_from_plain_turnpoint_hunt_task_config(self):
        form = NavigationTaskForm(
            data={
                "name": "Plain Turnpoint Hunt Form Task",
                "start_time": "2026-08-01T09:00",
                "finish_time": "2026-08-01T17:00",
                "display_background_map": True,
                "display_secrets": True,
                "minutes_to_starting_point": 5,
                "planning_time": 45,
                "original_scorecard": self.scorecard.pk,
                "task_subtype": "turnpoint_hunt",
                "minutes_to_landing": 30,
                "wind_speed": 0,
                "wind_direction": 0,
                "allow_self_management": True,
                "calculation_delay_minutes": 0,
                "compulsory_timing_tolerance_seconds": 9,
                "maximum_task_duration_minutes": 50,
                "maximum_task_duration_penalty": 140,
                "fuel_deadline_penalty": 88,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        navigation_task = form.save(commit=False)
        self.assertEqual(
            navigation_task.task_config,
            {
                "compulsory_timing_tolerance_seconds": 9,
                "maximum_task_duration_minutes": 50,
                "maximum_task_duration_penalty": 140.0,
            },
        )

    def test_form_seeds_existing_task_config_into_initial_values(self):
        navigation_task = NavigationTask.create(
            name="Existing Turnpoint Hunt Task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            task_subtype="limited_fuel_turnpoint_hunt",
            task_config={
                "compulsory_timing_tolerance_seconds": 7,
                "maximum_task_duration_minutes": 44,
                "maximum_task_duration_penalty": 111,
                "fuel_deadline_penalty": 66,
            },
        )
        form = NavigationTaskForm(instance=navigation_task)
        self.assertEqual(form.fields["compulsory_timing_tolerance_seconds"].initial, 7)
        self.assertEqual(form.fields["maximum_task_duration_minutes"].initial, 44)
        self.assertEqual(form.fields["maximum_task_duration_penalty"].initial, 111)
        self.assertEqual(form.fields["fuel_deadline_penalty"].initial, 66)

    def test_duration_form_does_not_persist_turnpoint_hunt_task_config_fields(self):
        form = NavigationTaskForm(
            data={
                "name": "Duration Form Task",
                "start_time": "2026-08-01T09:00",
                "finish_time": "2026-08-01T17:00",
                "display_background_map": True,
                "display_secrets": True,
                "minutes_to_starting_point": 5,
                "planning_time": 45,
                "original_scorecard": self.scorecard.pk,
                "task_subtype": DURATION,
                "minutes_to_landing": 30,
                "wind_speed": 0,
                "wind_direction": 0,
                "allow_self_management": True,
                "calculation_delay_minutes": 0,
                "compulsory_timing_tolerance_seconds": 8,
                "maximum_task_duration_minutes": 45,
                "maximum_task_duration_penalty": 123,
                "fuel_deadline_penalty": 77,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        navigation_task = form.save(commit=False)
        self.assertEqual(navigation_task.task_config, {})

    def test_duration_form_persists_duration_normalization_policy(self):
        form = NavigationTaskForm(
            data={
                "name": "Duration Policy Form Task",
                "start_time": "2026-08-01T09:00",
                "finish_time": "2026-08-01T17:00",
                "display_background_map": True,
                "display_secrets": True,
                "minutes_to_starting_point": 5,
                "planning_time": 45,
                "original_scorecard": self.scorecard.pk,
                "task_subtype": DURATION,
                "minutes_to_landing": 30,
                "wind_speed": 0,
                "wind_direction": 0,
                "allow_self_management": True,
                "calculation_delay_minutes": 0,
                "duration_normalization_policy": "raw_minutes",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        navigation_task = form.save(commit=False)
        self.assertEqual(navigation_task.task_config, {"duration_normalization_policy": "raw_minutes"})

    def test_duration_form_persists_landing_area_polygon(self):
        form = NavigationTaskForm(
            data={
                "name": "Duration Landing Area Form Task",
                "start_time": "2026-08-01T09:00",
                "finish_time": "2026-08-01T17:00",
                "display_background_map": True,
                "display_secrets": True,
                "minutes_to_starting_point": 5,
                "planning_time": 45,
                "original_scorecard": self.scorecard.pk,
                "task_subtype": DURATION,
                "minutes_to_landing": 30,
                "wind_speed": 0,
                "wind_direction": 0,
                "allow_self_management": True,
                "calculation_delay_minutes": 0,
                "duration_landing_area_polygon": "[[11.0, 60.0], [11.2, 60.0], [11.2, 60.2], [11.0, 60.2]]",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        navigation_task = form.save(commit=False)
        self.assertEqual(
            navigation_task.task_config,
            {
                "duration_landing_area_polygon": self.duration_polygon,
            },
        )

    def test_duration_form_seeds_landing_area_polygon_initial_value(self):
        navigation_task = NavigationTask.create(
            name="Existing Duration Landing Area Task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            task_subtype=DURATION,
            task_config={"duration_landing_area_polygon": self.duration_polygon},
        )
        form = NavigationTaskForm(instance=navigation_task)
        self.assertEqual(form.fields["duration_landing_area_polygon"].initial, "[[11.0, 60.0], [11.2, 60.0], [11.2, 60.2], [11.0, 60.2]]")

    def test_duration_form_rejects_invalid_landing_area_polygon_json(self):
        form = NavigationTaskForm(
            data={
                "name": "Duration Invalid Landing Area Task",
                "start_time": "2026-08-01T09:00",
                "finish_time": "2026-08-01T17:00",
                "display_background_map": True,
                "display_secrets": True,
                "minutes_to_starting_point": 5,
                "planning_time": 45,
                "original_scorecard": self.scorecard.pk,
                "task_subtype": DURATION,
                "minutes_to_landing": 30,
                "wind_speed": 0,
                "wind_direction": 0,
                "allow_self_management": True,
                "calculation_delay_minutes": 0,
                "duration_landing_area_polygon": "not-json",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("duration_landing_area_polygon", form.errors)

    def test_duration_form_persists_residual_fuel_required_flag(self):
        form = NavigationTaskForm(
            data={
                "name": "Duration Residual Fuel Task",
                "start_time": "2026-08-01T09:00",
                "finish_time": "2026-08-01T17:00",
                "display_background_map": True,
                "display_secrets": True,
                "minutes_to_starting_point": 5,
                "planning_time": 45,
                "original_scorecard": self.scorecard.pk,
                "task_subtype": DURATION,
                "minutes_to_landing": 30,
                "wind_speed": 0,
                "wind_direction": 0,
                "allow_self_management": True,
                "calculation_delay_minutes": 0,
                "duration_residual_fuel_required": True,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        navigation_task = form.save(commit=False)
        self.assertEqual(navigation_task.task_config, {"duration_residual_fuel_required": True})

    def test_duration_form_seeds_residual_fuel_required_initial_value(self):
        navigation_task = NavigationTask.create(
            name="Existing Duration Residual Fuel Task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            task_subtype=DURATION,
            task_config={"duration_residual_fuel_required": True},
        )
        form = NavigationTaskForm(instance=navigation_task)
        self.assertTrue(form.fields["duration_residual_fuel_required"].initial)

    def test_circle_form_persists_radius_limits(self):
        form = NavigationTaskForm(
            data={
                "name": "Circle Form Task",
                "start_time": "2026-08-01T09:00",
                "finish_time": "2026-08-01T17:00",
                "display_background_map": True,
                "display_secrets": True,
                "minutes_to_starting_point": 5,
                "planning_time": 45,
                "original_scorecard": self.scorecard.pk,
                "task_subtype": CIRCLE,
                "minutes_to_landing": 30,
                "wind_speed": 0,
                "wind_direction": 0,
                "allow_self_management": True,
                "calculation_delay_minutes": 0,
                "circle_radius_min_m": 250,
                "circle_radius_max_m": 800,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        navigation_task = form.save(commit=False)
        self.assertEqual(
            navigation_task.task_config,
            {"circle_radius_min_m": 250.0, "circle_radius_max_m": 800.0},
        )

    def test_circle_form_seeds_radius_limits_initial_values(self):
        navigation_task = NavigationTask.create(
            name="Existing Circle Task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            task_subtype=CIRCLE,
            task_config={"circle_radius_min_m": 210, "circle_radius_max_m": 760},
        )
        form = NavigationTaskForm(instance=navigation_task)
        self.assertEqual(form.fields["circle_radius_min_m"].initial, 210)
        self.assertEqual(form.fields["circle_radius_max_m"].initial, 760)
