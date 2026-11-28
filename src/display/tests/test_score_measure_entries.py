"""
The score log entries that carry a measure and not points of Q: the 2.A3 declared points V (plus or minus 1 each) and
the 2.A4 speed S (knots). The registry says which they are (relative_quality_terms); the stored text, the gate times
text and the task serialiser all follow it, so the displays need not list score types.
"""

from display.calculators.tests.test_score_message_kinds import MessageTestCase
from display.calculators.update_score_message import ACHIEVEMENT, PENALTY
from display.models import ScoreLogEntry
from display.serialisers import NavigationTaskNestedTeamRouteSerialiser
from display.services.task_scoring import measure_text, score_measures
from display.utilities.task_types import (
    CONTRACT_NAVIGATION_TIME_CONTROLS,
    CONTRACT_POINTS_SCORE_TYPE,
    KNOWN_CIRCUIT,
    PRECISION_NAVIGATION,
    SPEED_TERM_SCORE_TYPE,
    TASK_TYPE_REGISTRY,
)


class TestMeasureDescriptions(MessageTestCase):
    def test_the_registry_names_the_measures_of_a_task_type(self):
        self.assertEqual(
            {CONTRACT_POINTS_SCORE_TYPE: {"symbol": "V", "unit": "", "is_change": True}},
            score_measures(TASK_TYPE_REGISTRY[CONTRACT_NAVIGATION_TIME_CONTROLS]),
        )
        self.assertEqual(
            {SPEED_TERM_SCORE_TYPE: {"symbol": "S", "unit": "kt", "is_change": False}},
            score_measures(TASK_TYPE_REGISTRY[KNOWN_CIRCUIT]),
        )
        self.assertEqual({}, score_measures(TASK_TYPE_REGISTRY[PRECISION_NAVIGATION]))

    def test_the_text_of_a_measure(self):
        contract, known = TASK_TYPE_REGISTRY[CONTRACT_NAVIGATION_TIME_CONTROLS], TASK_TYPE_REGISTRY[KNOWN_CIRCUIT]
        self.assertEqual("V +1", measure_text(contract, CONTRACT_POINTS_SCORE_TYPE, 1))
        self.assertEqual("V -1", measure_text(contract, CONTRACT_POINTS_SCORE_TYPE, -1))
        self.assertEqual("S = 62.4 kt", measure_text(known, SPEED_TERM_SCORE_TYPE, 62.4))
        self.assertIsNone(measure_text(contract, "gate_score", 10))
        self.assertIsNone(measure_text(known, CONTRACT_POINTS_SCORE_TYPE, 1))


class TestStoredLogText(MessageTestCase):
    def apply(self, task_subtype, points, kind, score_type):
        task = self.make_task(task_subtype)
        contestant = self.make_contestant(task)
        processor = self.bare_processor(contestant, suppress_side_effects=False)
        processor.update_score_from_thread(self.message(points, kind, score_type, gate_name="FP"))
        return contestant, ScoreLogEntry.objects.get(contestant=contestant)

    def test_a_declared_point_flown_reads_v_plus_one(self):
        _, entry = self.apply(CONTRACT_NAVIGATION_TIME_CONTROLS, 1, ACHIEVEMENT, CONTRACT_POINTS_SCORE_TYPE)
        self.assertEqual("FP: V +1 test", entry.string)

    def test_a_declared_point_not_flown_reads_v_minus_one(self):
        _, entry = self.apply(CONTRACT_NAVIGATION_TIME_CONTROLS, 1, PENALTY, CONTRACT_POINTS_SCORE_TYPE)
        self.assertEqual("FP: V -1 test", entry.string)

    def test_the_speed_reads_as_knots(self):
        _, entry = self.apply(KNOWN_CIRCUIT, 62.4, ACHIEVEMENT, SPEED_TERM_SCORE_TYPE)
        self.assertEqual("FP: S = 62.4 kt test", entry.string)

    def test_other_entries_keep_their_points_text(self):
        _, entry = self.apply(CONTRACT_NAVIGATION_TIME_CONTROLS, 12, PENALTY, "gate_score")
        self.assertEqual("FP: -12.0 points test", entry.string)


class TestTaskPayload(MessageTestCase):
    def test_the_task_serialiser_sends_the_measures(self):
        for subtype, expected in (
            (CONTRACT_NAVIGATION_TIME_CONTROLS, {CONTRACT_POINTS_SCORE_TYPE}),
            (KNOWN_CIRCUIT, {SPEED_TERM_SCORE_TYPE}),
            (PRECISION_NAVIGATION, set()),
        ):
            task = self.make_task(subtype)
            # The field alone: the whole serialiser needs a request with a user
            measures = NavigationTaskNestedTeamRouteSerialiser().get_score_measures(task)
            self.assertEqual(expected, set(measures), subtype)
