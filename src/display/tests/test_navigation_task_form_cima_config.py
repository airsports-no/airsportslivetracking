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
        self.scorecard_id = self.scorecard.pk
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("NavigationTaskFormRoute", file.readlines()[1:])
            self.editable_route = editable_route
            self.route = editable_route.create_precision_route(True, self.scorecard)

    def _build_form(self, task_subtype, **extra_data):
        data = {
            "name": f"{task_subtype} Form Task",
            "start_time": "2026-08-01T09:00",
            "finish_time": "2026-08-01T17:00",
            "display_background_map": True,
            "display_secrets": True,
            "minutes_to_starting_point": 5,
            "planning_time": 45,
            "original_scorecard": self.scorecard_id,
            "task_subtype": task_subtype,
            "minutes_to_landing": 30,
            "wind_speed": 0,
            "wind_direction": 0,
            "allow_self_management": True,
            "calculation_delay_minutes": 0,
        }
        data.update(extra_data)
        return NavigationTaskForm(data=data)

    def test_navigation_task_form_exposes_only_generic_navigation_task_fields(self):
        form = NavigationTaskForm()
        self.assertNotIn("compulsory_timing_tolerance_seconds", form.fields)
        self.assertNotIn("maximum_task_duration_minutes", form.fields)
        self.assertNotIn("maximum_task_duration_penalty", form.fields)
        self.assertNotIn("fuel_deadline_penalty", form.fields)
        self.assertNotIn("duration_normalization_policy", form.fields)
        self.assertNotIn("duration_landing_area_polygon", form.fields)
        self.assertNotIn("duration_residual_fuel_required", form.fields)
        self.assertNotIn("circle_radius_min_m", form.fields)
        self.assertNotIn("circle_radius_max_m", form.fields)

    def test_turnpoint_hunt_runtime_values_posted_to_navigation_task_form_are_ignored(self):
        form = self._build_form(
            "limited_fuel_turnpoint_hunt",
            compulsory_timing_tolerance_seconds=8,
            maximum_task_duration_minutes=45,
            maximum_task_duration_penalty=123,
            fuel_deadline_penalty=77,
        )
        self.assertTrue(form.is_valid(), form.errors)
        navigation_task = form.save(commit=False)
        self.assertEqual(navigation_task.task_subtype, "limited_fuel_turnpoint_hunt")
        self.assertEqual(navigation_task.task_config, {})

    def test_duration_runtime_values_posted_to_navigation_task_form_are_ignored(self):
        form = self._build_form(
            DURATION,
            duration_normalization_policy="raw_minutes",
            duration_landing_area_polygon="[[11.0, 60.0], [11.2, 60.0], [11.2, 60.2], [11.0, 60.2]]",
            duration_residual_fuel_required=True,
        )
        self.assertTrue(form.is_valid(), form.errors)
        navigation_task = form.save(commit=False)
        self.assertEqual(navigation_task.task_subtype, DURATION)
        self.assertEqual(navigation_task.task_config, {})

    def test_circle_runtime_values_posted_to_navigation_task_form_are_ignored(self):
        form = self._build_form(
            CIRCLE,
            circle_radius_min_m=250,
            circle_radius_max_m=800,
        )
        self.assertTrue(form.is_valid(), form.errors)
        navigation_task = form.save(commit=False)
        self.assertEqual(navigation_task.task_subtype, CIRCLE)
        self.assertEqual(navigation_task.task_config, {})

    def test_existing_task_specific_config_is_not_seeded_back_into_navigation_task_form(self):
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
        self.assertNotIn("circle_radius_min_m", form.fields)
        self.assertNotIn("circle_radius_max_m", form.fields)

    def test_navigation_task_form_still_persists_generic_fields_for_cima_task(self):
        form = self._build_form(CIRCLE)
        self.assertTrue(form.is_valid(), form.errors)
        navigation_task = form.save(commit=False)
        navigation_task.contest = self.contest
        navigation_task.route = self.route
        navigation_task.editable_route = self.editable_route
        navigation_task.save()
        self.assertEqual(navigation_task.name, "circle Form Task")
        self.assertEqual(navigation_task.task_subtype, CIRCLE)
        self.assertEqual(navigation_task.task_config, {})
