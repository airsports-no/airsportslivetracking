"""
Regression test (scorecard-system review roadmap, Phase 0 follow-up): NAVIGATION_TASK_TYPES'
label for AIRSPORT_CHALLENGE was "AirSport Challenge" (no space) while every other source of
this task type's name - task_information.FAMILY_DISPLAY_NAMES, the canonical Scorecard name
settled on in the AirSport Challenge duplicate-scorecard merge, and CIMA's own
LEGACY_AIRSPORT_CHALLENGE.display_name - used "Air Sport Challenge" (with a space). Plain typo,
not an intentional terse/verbose split (contrast PRECISION, where "Precision" vs. "Precision
navigation" is a defensible dropdown-option-vs-heading distinction and is left alone).
"""

from django.test import SimpleTestCase

from display.utilities.cima_task_type_definitions import LEGACY_AIRSPORT_CHALLENGE, TASK_SUBTYPE_DEFINITIONS
from display.utilities.navigation_task_type_definitions import AIRSPORT_CHALLENGE, NAVIGATION_TASK_TYPES
from display.utilities.task_information import FAMILY_DISPLAY_NAMES


class TestTaskTypeDisplayNameConsistency(SimpleTestCase):
    def test_airsport_challenge_label_is_spelled_consistently_everywhere(self):
        navigation_task_types_label = dict(NAVIGATION_TASK_TYPES)[AIRSPORT_CHALLENGE]
        self.assertEqual(navigation_task_types_label, "Air Sport Challenge")
        self.assertEqual(FAMILY_DISPLAY_NAMES[AIRSPORT_CHALLENGE], navigation_task_types_label)

        legacy_definition = TASK_SUBTYPE_DEFINITIONS[LEGACY_AIRSPORT_CHALLENGE]
        self.assertIn(navigation_task_types_label, legacy_definition.display_name)
