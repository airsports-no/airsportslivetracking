"""
Phase 2b of the scorecard-system review roadmap: pins the exact set of keys the scorecard
API serializers expose. Both ScorecardNestedSerialiser and GateScoreSerialiser use an
explicit field list (not `exclude=(...)`, whatever columns/attributes happen to exist),
precisely so the API contract can no longer drift silently the next time a scoring field
changes - this test is the guardrail that would actually catch that drift. (Phase 2e retired
the GateScore table entirely - GateScoreSerialiser now reads a GateScoreValue, not a model
instance, but the exposed key set is unchanged apart from dropping the confirmed-dead
bad_course_crossing_penalty. Phase 3 added a read-only `visible_fields` key to both - see
serialisers.py - deliberately widening the contract so the new React scorecard editor can use
scorecard/gate curation as a grouping hint instead of GateScoreForm/ScorecardForm's previous
hard filter.)
"""

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import Contest, EditableRoute, NavigationTask, Scorecard
from display.serialisers import GateScoreSerialiser, ScorecardNestedSerialiser
from display.utilities.gate_definitions import TURNPOINT

EXPECTED_SCORECARD_NESTED_KEYS = {
    "shortcut_name",
    "valid_from",
    "free_text",
    "score_sorting_direction",
    "initial_score",
    "task_type",
    "corridor_width",
    "gatescore_set",
    "visible_fields",
    "backtracking_penalty",
    "backtracking_bearing_difference",
    "backtracking_grace_time_seconds",
    "backtracking_maximum_penalty",
    "prohibited_zone_penalty",
    "prohibited_zone_grace_time",
    "prohibited_zone_maximum",
    "penalty_zone_grace_time",
    "penalty_zone_penalty_per_second",
    "penalty_zone_maximum",
    "corridor_grace_time",
    "corridor_outside_penalty",
    "corridor_maximum_penalty",
    "corridor_maximum_penalty_is_per_leg",
    "anr_route_to_sp_penalty",
    "anr_route_from_fp_penalty",
    "compulsory_timing_tolerance_seconds",
    "maximum_task_duration_minutes",
    "maximum_task_duration_penalty",
    "fuel_deadline_penalty",
    "duration_normalization_policy",
    "duration_residual_fuel_required",
    "circle_radius_min_m",
    "circle_radius_max_m",
    "speed_keeping_tolerance_kt",
    "speed_keeping_penalty_per_kt",
    "turnpoint_hunt_sequence_bonus",
}

EXPECTED_GATE_SCORE_KEYS = {
    "gate_type",
    "extended_gate_width",
    "bad_crossing_extended_gate_penalty",
    "graceperiod_before",
    "graceperiod_after",
    "maximum_penalty",
    "penalty_per_second",
    "missed_penalty",
    "missed_procedure_turn_penalty",
    "backtracking_after_steep_gate_grace_period_seconds",
    "backtracking_before_gate_grace_period_nm",
    "backtracking_after_gate_grace_period_nm",
    "visible_fields",
}


class TestScorecardSerialiserShape(TestCase):
    def setUp(self):
        create_scorecards()
        user = get_user_model().objects.create(email="serialiser-shape@example.com")
        contest = Contest.objects.create(
            name="Serialiser Shape Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
            created_by=user,
        )
        original_scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("SerialiserShapeRoute", file.readlines()[1:])
            route = editable_route.create_precision_route(True, original_scorecard)
        navigation_task = NavigationTask.create(
            name="Serialiser Shape Task",
            contest=contest,
            route=route,
            original_scorecard=original_scorecard,
            start_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 8, 1, 17, 0, tzinfo=datetime.timezone.utc),
        )
        # A per-task copy (not the original template) so corridor_width - which reads
        # navigation_task_override.route.corridor_width - can actually be evaluated.
        self.scorecard = navigation_task.scorecard

    def test_scorecard_nested_serialiser_exposes_exactly_the_expected_keys(self):
        serialiser = ScorecardNestedSerialiser(self.scorecard)
        self.assertEqual(EXPECTED_SCORECARD_NESTED_KEYS, set(serialiser.data.keys()))

    def test_gate_score_serialiser_exposes_exactly_the_expected_keys(self):
        gate_score = self.scorecard.get_gate_scorecard(TURNPOINT)
        serialiser = GateScoreSerialiser(gate_score)
        self.assertEqual(EXPECTED_GATE_SCORE_KEYS, set(serialiser.data.keys()))
