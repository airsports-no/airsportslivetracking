"""
Regression test for the Django admin Scorecard edit form. Before this fix, Scorecard was
registered bare (admin.site.register(Scorecard)), so its auto-generated admin form was built
from real model fields only - Phase 2 of the scorecard-system review roadmap moved 26
scoring-parameter fields off of real columns onto Scorecard.config-backed properties (see
ConfigField in models/scorecard_and_gate_score.py), so the admin form ended up exposing
`config` as a raw JSON textarea plus all 27 inert `legacy_*` columns, and none of the fields
that actually affect scoring - editing a `legacy_*` field there silently did nothing.
"""

from django.contrib import admin
from django.forms.models import model_to_dict
from django.test import TestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Scorecard
from display.models.scorecard_and_gate_score import SCORECARD_CONFIG_FIELDS


class TestScorecardAdmin(TestCase):
    def setUp(self):
        self.scorecard = get_default_scorecard()

    def test_admin_form_exposes_config_backed_fields_not_legacy_columns(self):
        form_class = admin.site._registry[Scorecard].get_form(None)
        field_names = set(form_class.base_fields.keys())
        for field_name in SCORECARD_CONFIG_FIELDS:
            self.assertIn(field_name, field_names, f"{field_name} should be a real admin form field")
            self.assertNotIn(f"legacy_{field_name}", field_names, f"legacy_{field_name} should not be editable")
        self.assertNotIn("config", field_names)

    def test_admin_form_initial_values_match_the_instance(self):
        form_class = admin.site._registry[Scorecard].get_form(None)
        form = form_class(instance=self.scorecard)
        self.assertEqual(form.initial["backtracking_penalty"], self.scorecard.backtracking_penalty)
        self.assertEqual(form.initial["corridor_grace_time"], self.scorecard.corridor_grace_time)

    def test_admin_add_form_saves_config_defaults_not_none_or_false(self):
        # Regression test: Django's admin add_view constructs the form with no `instance`
        # kwarg at all (only change_view passes one) - __init__ used to only populate
        # `initial` when an instance was truthy, so a blank add-form FloatField saved None
        # and an unchecked BooleanField saved False through ConfigField._set(), silently
        # overriding real defaults like corridor_maximum_penalty_is_per_leg=True for every
        # newly-created scorecard.
        form_class = admin.site._registry[Scorecard].get_form(None)
        blank_form = form_class()
        data = dict(blank_form.initial)
        data.update(model_to_dict(Scorecard(name="Admin Add Regression", shortcut_name="admin-add-regression")))
        data["free_text"] = data.get("free_text") or "x"
        bound_form = form_class(data=data)
        self.assertTrue(bound_form.is_valid(), bound_form.errors)
        new_scorecard = bound_form.save()
        self.assertEqual(200, new_scorecard.circle_radius_min_m)
        self.assertIs(True, new_scorecard.corridor_maximum_penalty_is_per_leg)

    def test_admin_form_save_actually_changes_live_scoring_config(self):
        form_class = admin.site._registry[Scorecard].get_form(None)
        data = model_to_dict(self.scorecard, exclude=["config"])
        data.update(form_class(instance=self.scorecard).initial)
        data["free_text"] = data.get("free_text") or "x"
        data["backtracking_penalty"] = 12345
        form = form_class(data=data, instance=self.scorecard)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.scorecard.refresh_from_db()
        self.assertEqual(12345, self.scorecard.backtracking_penalty)
