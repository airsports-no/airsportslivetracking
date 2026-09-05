"""
Regression test for GateScoreForm.save() (src/display/forms.py) - the organizer-facing
gate-score override form. Every field on this form is required=False, so clearing a numeric
input submits an empty value and cleaned_data holds None for it. save() used to
`.update(self.cleaned_data)` unconditionally, writing that None straight into
config["gates"][gate_type] - GateScoreValue.from_dict then returns the stored None (not the
dataclass's real default, since the key is present), and every calculator/task_information
call doing arithmetic on that field raises TypeError or silently produces "None" in rendered
text (see PR #753 review, flagged against the same class of bug already fixed for
ScorecardAdminForm in test_scorecard_admin.py).
"""

from django.test import TestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.forms import GateScoreForm
from display.utilities.gate_definitions import TURNPOINT


class TestGateScoreFormSave(TestCase):
    def setUp(self):
        self.scorecard = get_default_scorecard()

    def _bound_form(self, **overrides):
        gate = self.scorecard.get_gate_scorecard(TURNPOINT)
        data = {field: getattr(gate, field) for field in GateScoreForm.base_fields}
        data.update(overrides)
        return GateScoreForm(data=data, scorecard=self.scorecard, gate_type=TURNPOINT)

    def test_clearing_a_field_does_not_wipe_the_configured_value(self):
        before = self.scorecard.get_gate_scorecard(TURNPOINT).maximum_penalty
        form = self._bound_form(maximum_penalty="")
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(before, self.scorecard.get_gate_scorecard(TURNPOINT).maximum_penalty)

    def test_setting_a_field_still_saves_normally(self):
        form = self._bound_form(maximum_penalty=999)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(999, self.scorecard.get_gate_scorecard(TURNPOINT).maximum_penalty)
