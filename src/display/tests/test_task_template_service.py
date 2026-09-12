"""
Regression coverage for the task-template/route-compatibility helpers after their move out of
display.forms_wizards/display.views_wizards into display.services.task_templates and
display.services.route_compatibility (see the wizard-to-SPA migration plan). The wizards'
underscore-prefixed names (display.forms_wizards._task_template_choices etc.) are now thin
aliases re-exported for backwards compatibility - the tests here import the service module
directly, since it's the surface a future REST endpoint will be built against.
"""

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from display.services.route_compatibility import effective_subtype_key, no_compatible_routes_message
from display.services.task_templates import normalize_task_template_selection
from display.utilities.cima_task_type_definitions import CIRCLE, LEGACY_ANR_CORRIDOR
from display.utilities.navigation_task_type_definitions import ANR_CORRIDOR, PRECISION


class TestNormalizeTaskTemplateSelection(SimpleTestCase):
    def test_empty_value_returns_none_pair(self):
        self.assertEqual(normalize_task_template_selection(""), (None, None))
        self.assertEqual(normalize_task_template_selection(None), (None, None))

    def test_legacy_family_key_returns_itself_with_no_subtype(self):
        self.assertEqual(normalize_task_template_selection(PRECISION), (PRECISION, ""))

    def test_cima_subtype_key_resolves_to_its_coarse_family(self):
        task_type, task_subtype = normalize_task_template_selection(CIRCLE)
        self.assertEqual(task_subtype, CIRCLE)
        self.assertTrue(task_type)  # coarse_family, whatever it is for this subtype

    def test_unknown_value_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            normalize_task_template_selection("not-a-real-task-template")


class TestEffectiveSubtypeKey(SimpleTestCase):
    def test_explicit_subtype_wins(self):
        self.assertEqual(effective_subtype_key(ANR_CORRIDOR, CIRCLE), CIRCLE)

    def test_falls_back_to_legacy_shim_for_the_family(self):
        self.assertEqual(effective_subtype_key(ANR_CORRIDOR, None), LEGACY_ANR_CORRIDOR)
        self.assertEqual(effective_subtype_key(ANR_CORRIDOR, ""), LEGACY_ANR_CORRIDOR)

    def test_unknown_family_falls_back_to_itself(self):
        self.assertEqual(effective_subtype_key("not-a-real-family", None), "not-a-real-family")


class TestNoCompatibleRoutesMessage(SimpleTestCase):
    def test_mentions_required_and_forbidden_primitives(self):
        message = no_compatible_routes_message(LEGACY_ANR_CORRIDOR)
        self.assertIn("None of the routes you can edit currently support this task type", message)
