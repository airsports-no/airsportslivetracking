import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from display.default_scorecards.create_scorecards import create_scorecards
from display.forms import NavigationTaskForm, ScorecardForm
from display.models import Contest, EditableRoute, NavigationTask, Scorecard
from display.models.scorecard_and_gate_score import SCORECARD_CONFIG_FIELDS
from display.utilities.cima_task_type_definitions import ANR_CATALOGUE, CIRCLE, DURATION, LIMITED_FUEL_TURNPOINT_HUNT
from display.views import _extract_values_from_form


class TestNavigationTaskFormScorecardRefactor(TestCase):
    def setUp(self):
        create_scorecards()
        self.user = get_user_model().objects.create(email="scorecard-refactor@example.com")
        self.contest = Contest.objects.create(
            name="Scorecard Refactor Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
            created_by=self.user,
        )
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("ScorecardRefactorRoute", file.readlines()[1:])
            self.editable_route = editable_route
            self.route = editable_route.create_precision_route(True, self.scorecard)

    def test_navigation_task_form_no_longer_exposes_task_specific_runtime_fields(self):
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

    def test_scorecard_form_exposes_turnpoint_hunt_runtime_fields_for_turnpoint_hunt_task(self):
        navigation_task = NavigationTask.create(
            name="Turnpoint Hunt Task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            task_subtype=LIMITED_FUEL_TURNPOINT_HUNT,
        )
        form = ScorecardForm(instance=navigation_task.scorecard)
        self.assertIn("compulsory_timing_tolerance_seconds", form.fields)
        self.assertIn("maximum_task_duration_minutes", form.fields)
        self.assertIn("maximum_task_duration_penalty", form.fields)
        self.assertIn("fuel_deadline_penalty", form.fields)

    def test_scorecard_form_exposes_duration_runtime_fields_for_duration_task(self):
        navigation_task = NavigationTask.create(
            name="Duration Task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            task_subtype=DURATION,
        )
        form = ScorecardForm(instance=navigation_task.scorecard)
        self.assertIn("duration_normalization_policy", form.fields)
        self.assertIn("duration_residual_fuel_required", form.fields)
        self.assertNotIn("duration_landing_area_polygon", form.fields)

    def test_scorecard_form_exposes_circle_runtime_fields_for_circle_task(self):
        navigation_task = NavigationTask.create(
            name="Circle Task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            task_subtype=CIRCLE,
        )
        form = ScorecardForm(instance=navigation_task.scorecard)
        self.assertIn("circle_radius_min_m", form.fields)
        self.assertIn("circle_radius_max_m", form.fields)

    def test_scorecard_form_exposes_anr_auxiliary_route_penalties_for_anr_catalogue_task(self):
        navigation_task = NavigationTask.create(
            name="ANR Catalogue Task",
            contest=self.contest,
            route=self.route,
            original_scorecard=Scorecard.get_originals().get(shortcut_name="FAI ANR"),
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            task_subtype=ANR_CATALOGUE,
        )
        form = ScorecardForm(instance=navigation_task.scorecard)
        self.assertIn("anr_route_to_sp_penalty", form.fields)
        self.assertIn("anr_route_from_fp_penalty", form.fields)

    def test_scorecard_form_fields_have_labels_not_none(self):
        # Regression test: the 26 SCORECARD_CONFIG_FIELDS are declared explicitly on
        # ScorecardForm (not auto-generated by ModelForm, since they're config-backed
        # properties, not real model fields) - ModelForm's usual auto-labeling
        # (fields_for_model() -> capfirst(verbose_name)) never runs for them, leaving
        # field.label as None. That's invisible in a normal template render (BoundField
        # falls back to a pretty name), but the scorecard detail page's
        # _extract_values_from_form() (views.py) reads field.label directly, so every one
        # of these rows rendered as "None: <value>" on the live scorecard page.
        navigation_task = NavigationTask.create(
            name="Label Regression Task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
        )
        form = ScorecardForm(instance=navigation_task.scorecard)
        for field_name in SCORECARD_CONFIG_FIELDS:
            self.assertIsNotNone(form.fields[field_name].label, f"{field_name} should have a non-None label")

    def test_scorecard_form_does_not_duplicate_the_subtype_block_on_repeated_construction(self):
        # Regression test: __init__ runs on every construction, including every POST to the
        # scorecard-override page - self.instance.included_fields.append(...) used to run
        # unconditionally, so re-editing a scorecard for a task with one of these subtypes
        # added another copy of the matching block every time.
        navigation_task = NavigationTask.create(
            name="Dedup Regression Task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            task_subtype=CIRCLE,
        )
        # First "request": construct the form and save, as the override view does on a POST.
        form1 = ScorecardForm(instance=navigation_task.scorecard)
        form1.instance.save()

        # Second "request": a fresh fetch (a new HTTP request would re-query from scratch),
        # so the already-persisted block from the first save is loaded from the DB this time.
        second_instance = Scorecard.objects.get(pk=navigation_task.scorecard.pk)
        form2 = ScorecardForm(instance=second_instance)
        form2.instance.save()

        final = Scorecard.objects.get(pk=navigation_task.scorecard.pk)
        circle_blocks = [block for block in final.included_fields if block[0] == "Circle configuration"]
        self.assertEqual(
            1, len(circle_blocks), f"expected exactly one Circle configuration block, got: {circle_blocks}"
        )

    def test_scorecard_detail_page_extracted_values_have_no_none_labels(self):
        navigation_task = NavigationTask.create(
            name="Label Regression Task 2",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
        )
        form = ScorecardForm(instance=navigation_task.scorecard)
        content = _extract_values_from_form(form)
        self.assertTrue(content, "extracted content should not be empty")
        for block in content:
            for field in block["values"]:
                self.assertIsNotNone(field["label"], f"value {field['value']!r} has a None label")
