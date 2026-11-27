"""
The task information shown to organisers and pilots (display.utilities.task_information) quotes the numbers of the task's
scorecard, not the catalogue's defaults: an organiser who briefs a 30% altitude penalty must not be told 20%.
"""

from display.calculators.tests.test_score_message_kinds import MessageTestCase
from display.utilities.task_information import build_navigation_task_information
from display.utilities.task_types import (
    ANR_CATALOGUE,
    CIRCLE,
    CONTRACT_NAVIGATION_TIME_CONTROLS,
    LIMITED_FUEL_TURNPOINT_HUNT,
    PRECISION_NAVIGATION,
    TURNPOINT_HUNT,
)


class TestTaskInformationFollowsTheScorecard(MessageTestCase):
    def information(self, subtype, original_scorecard=None, **scorecard_values):
        task = self.make_task(subtype, original_scorecard)
        for field, value in scorecard_values.items():
            setattr(task.scorecard, field, value)
        task.scorecard.save()
        info = build_navigation_task_information(task)
        return "\n".join(info["scoring"] + info["penalties"] + info["overrides"])

    def test_the_circle_altitude_rule_is_the_scorecards(self):
        default = self.information(CIRCLE)
        self.assertIn("A 20% penalty applies if altitude spread exceeds 200 ft / 61 m", default)
        changed = self.information(CIRCLE, circle_altitude_penalty_percent=30, circle_altitude_band_ft=300)
        self.assertIn("A 30% penalty applies if altitude spread exceeds 300 ft / 91 m", changed)
        self.assertNotIn("20%", changed)

    def test_the_circle_radius_band_is_the_scorecards(self):
        self.assertIn(
            "Configured radius band is 300 m to 900 m.",
            self.information(CIRCLE, circle_radius_min_m=300, circle_radius_max_m=900),
        )

    def test_the_backtracking_percentage_is_the_scorecards(self):
        for subtype in (PRECISION_NAVIGATION, CONTRACT_NAVIGATION_TIME_CONTROLS):
            self.assertIn("Backtracking is a 50% penalty.", self.information(subtype))
            self.assertIn(
                "Backtracking is a 25% penalty.", self.information(subtype, backtracking_penalty_percentage=25)
            )

    def test_the_hunt_timing_numbers_are_the_scorecards(self):
        for subtype in (TURNPOINT_HUNT, LIMITED_FUEL_TURNPOINT_HUNT):
            self.assertIn(
                "tolerance of 10 seconds, beyond which each second costs 10 points of the 200 each gate is worth",
                self.information(subtype),
            )
            changed = self.information(
                subtype,
                compulsory_timing_tolerance_seconds=15,
                compulsory_timing_penalty_per_second=5,
                turnpoint_hunt_time_gate_value=150,
            )
            self.assertIn(
                "tolerance of 15 seconds, beyond which each second costs 5 points of the 150 each gate is worth",
                changed,
            )

    def test_the_hunt_maximum_duration_is_the_scorecards(self):
        text = self.information(TURNPOINT_HUNT, maximum_task_duration_minutes=90, maximum_task_duration_penalty=7)
        self.assertIn("maximum task duration is 90 minutes with 7 points/second overtime penalty", text)

    def test_the_2a8_numbers_are_the_scorecards(self):
        # Default scorecard of the task type: the catalogue's values
        default = self.information(ANR_CATALOGUE, self.anr_original)
        self.assertIn("SP and FP each use a 0.6 NM gate", default)
        self.assertIn("scales that 0-2000 total onto the task value (0-1000)", default)
        changed = self.information(ANR_CATALOGUE, self.anr_original, backtracking_penalty=150, task_value=800)
        self.assertIn("gives 150 points each", changed)
        self.assertIn("(0-800)", changed)
