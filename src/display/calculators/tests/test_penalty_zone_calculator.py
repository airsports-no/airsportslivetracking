import datetime
from unittest.mock import Mock, call

from django.test import TransactionTestCase

from display.calculators.calculator import OrchestratorState
from display.calculators.penalty_zone_calculator import PenaltyZoneCalculator
from display.calculators.update_score_message import UpdateScoreMessage
from display.models import Prohibited, Route
from display.waypoint import Waypoint
from display.utilities.coordinate_utilities import Projector


class TestPenaltyZoneCalculator(TransactionTestCase):
    def setUp(self):
        self.route = Route.objects.create(name="test")
        Prohibited.objects.create(
            name="test", path=[(11, 60), (12, 60), (12, 61), (11, 61)], route=self.route, type="penalty"
        )
        from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard

        self.contestant = Mock()
        waypoint = Waypoint("")
        waypoint.latitude = 60
        waypoint.longitude = 11
        self.contestant.navigation_task.route.waypoints = [waypoint]
        
        self.projector = Projector(60, 11)
        self.calculator = PenaltyZoneCalculator(self.contestant, get_default_scorecard(), self.route, Mock(), projector=self.projector)
        self.calculator.scorecard.penalty_zone_grace_time = 3
        self.calculator.scorecard.penalty_zone_penalty_per_second = 3
        self.calculator.scorecard.penalty_zone_maximum = 200
        self.calculator.update_score = Mock()

    def create_position(self, lat, lon, time):
        position = Mock()
        position.latitude = lat
        position.longitude = lon
        position.time = time
        p = self.projector.project_point(lat, lon)
        position.projected_x = p.projected_x
        position.projected_y = p.projected_y
        return position

    def test_maximum_score_is_reset_between_entries(self):
        position = self.create_position(60.5, 11.5, datetime.datetime(2020, 1, 1, 0, 0, tzinfo=datetime.timezone.utc))
        state = Mock(OrchestratorState)
        state.last_visible_gate = Mock()
        state.last_visible_gate.is_visible = True
        state.last_visible_gate.waypoint.on_curved_segment = False
        self.calculator.calculate_outside_route([position], state)

        self.calculator.update_score.assert_called_with(
            UpdateScoreMessage(
                time=datetime.datetime(2020, 1, 1, 0, 0, tzinfo=datetime.timezone.utc),
                gate=state.last_visible_gate,
                score=0,
                message="entering penalty zone test",
                latitude=60.5,
                longitude=11.5,
                annotation_type="information",
                score_type="inside_penalty_zone",
                maximum_score=None,
                planned=None,
                actual=None,
            )
        )

        position = self.create_position(59.5, 11.5, datetime.datetime(2020, 1, 1, 0, 2, 0, tzinfo=datetime.timezone.utc))
        self.calculator.calculate_outside_route([position], state)
        self.calculator.update_score.assert_called_with(
            UpdateScoreMessage(
                position.time,
                state.last_visible_gate,
                200,
                "inside penalty zone test (120s)",
                59.5,
                11.5,
                "anomaly",
                "inside_penalty_zone",
            )
        )
        # Moving outside again
        position = self.create_position(60.5, 11.5, datetime.datetime(2020, 1, 1, 0, 3, tzinfo=datetime.timezone.utc))
        self.calculator.calculate_outside_route([position], state)
        # Moving inside, should not get additional score.
        position = self.create_position(59.5, 11.5, datetime.datetime(2020, 1, 1, 0, 3, 15, tzinfo=datetime.timezone.utc))
        self.calculator.calculate_outside_route([position], state)
        self.calculator.update_score.assert_called_with(
            UpdateScoreMessage(
                position.time,
                state.last_visible_gate,
                36,
                "inside penalty zone test (15s)",
                59.5,
                11.5,
                "anomaly",
                "inside_penalty_zone",
            )
        )

    def test_inside_enroute(self):
        position = self.create_position(60.5, 11.5, datetime.datetime(2020, 1, 1, 0, 0, 2, tzinfo=datetime.timezone.utc))
        state = Mock(OrchestratorState)
        state.last_visible_gate = Mock()
        state.last_visible_gate.is_visible = True
        state.last_visible_gate.waypoint.on_curved_segment = False
        self.calculator.calculate_enroute([position], state)
        self.calculator.update_score.assert_called_with(
            UpdateScoreMessage(
                position.time,
                state.last_visible_gate,
                0,
                "entering penalty zone test",
                60.5,
                11.5,
                "information",
                "inside_penalty_zone",
            )
        )

    def test_inside_outside_route(self):
        position = self.create_position(60.5, 11.5, datetime.datetime(2020, 1, 1, 0, 0, 2, tzinfo=datetime.timezone.utc))
        state = Mock(OrchestratorState)
        state.last_visible_gate = Mock()
        state.last_visible_gate.is_visible = True
        state.last_visible_gate.waypoint.on_curved_segment = False
        self.calculator.calculate_outside_route([position], state)
        self.calculator.update_score.assert_called_with(
            UpdateScoreMessage(
                position.time,
                state.last_visible_gate,
                0,
                "entering penalty zone test",
                60.5,
                11.5,
                "information",
                "inside_penalty_zone",
            )
        )

    def test_in_and_out_within_grace_time_enroute(self):
        position = self.create_position(60.5, 11.5, datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc))
        state = Mock(OrchestratorState)
        state.last_visible_gate = Mock()
        state.last_visible_gate.is_visible = True
        state.last_visible_gate.waypoint.on_curved_segment = False
        self.calculator.calculate_outside_route([position], state)
        self.calculator.update_score.assert_called_with(
            UpdateScoreMessage(
                position.time,
                state.last_visible_gate,
                0,
                "entering penalty zone test",
                60.5,
                11.5,
                "information",
                "inside_penalty_zone",
            )
        )

        position = self.create_position(59.5, 11.5, datetime.datetime(2020, 1, 1, 0, 0, 2, tzinfo=datetime.timezone.utc))
        state = Mock(OrchestratorState)
        state.last_visible_gate = Mock()
        state.last_visible_gate.is_visible = True
        state.last_visible_gate.waypoint.on_curved_segment = False
        self.calculator.calculate_outside_route([position], state)
        self.calculator.update_score.assert_called_with(
            UpdateScoreMessage(
                position.time,
                state.last_visible_gate,
                0,
                "inside penalty zone test (2s)",
                59.5,
                11.5,
                "anomaly",
                "inside_penalty_zone",
            )
        )

    def test_in_and_out_beyond_grace_time_enroute(self):
        state = Mock(OrchestratorState)
        state.last_visible_gate = Mock()
        state.last_visible_gate.is_visible = True
        state.last_visible_gate.waypoint.on_curved_segment = False

        for index in range(0, 30, 3):
            position = self.create_position(60.5, 11.5, datetime.datetime(2020, 1, 1, second=index, tzinfo=datetime.timezone.utc))
            self.calculator.calculate_outside_route([position], state)
        # outside_position = Mock()
        # outside_position.latitude = 59.5
        # outside_position.longitude = 11.5
        # outside_position.time = datetime.datetime(2020, 1, 1, second=30, tzinfo=datetime.timezone.utc)
        # reference=self.calculator.existing_reference["test"]
        # self.calculator.calculate_outside_route([outside_position], gate)
        expected_calls = [
            call(
                UpdateScoreMessage(
                    time=datetime.datetime(2020, 1, 1, 0, 0, tzinfo=datetime.timezone.utc),
                    gate=state.last_visible_gate,
                    score=0,
                    message="entering penalty zone test",
                    latitude=60.5,
                    longitude=11.5,
                    annotation_type="information",
                    score_type="inside_penalty_zone",
                    maximum_score=None,
                    planned=None,
                    actual=None,
                )
            ),
            # call(gate, 81, 'inside penalty zone test', 59.5, 11.5, 'anomaly', 'inside_penalty_zone',
            #      existing_reference=reference)
        ]
        self.calculator.update_score.assert_has_calls(expected_calls)

        position = self.create_position(59.5, 11.5, datetime.datetime(2020, 1, 1, 0, 0, 10, tzinfo=datetime.timezone.utc))
        state = Mock(OrchestratorState)
        state.last_visible_gate = Mock()
        state.last_visible_gate.is_visible = True
        state.last_visible_gate.waypoint.on_curved_segment = False

        self.calculator.calculate_outside_route([position], state)
        self.calculator.update_score.assert_called_with(
            UpdateScoreMessage(
                position.time,
                state.last_visible_gate,
                21,
                "inside penalty zone test (10s)",
                59.5,
                11.5,
                "anomaly",
                "inside_penalty_zone",
            )
        )

    def test_outside_enroute(self):
        position = self.create_position(59.5, 11.5, datetime.datetime(2020, 1, 1, second=0, tzinfo=datetime.timezone.utc))
        state = Mock(OrchestratorState)
        state.last_visible_gate = Mock()
        state.last_visible_gate.is_visible = True
        state.last_visible_gate.waypoint.on_curved_segment = False
        self.calculator.calculate_enroute([position], state)
        self.calculator.update_score.assert_not_called()

    def test_outside_outside_route(self):
        position = self.create_position(59.5, 11.5, datetime.datetime(2020, 1, 1, second=0, tzinfo=datetime.timezone.utc))
        state = Mock(OrchestratorState)
        state.last_visible_gate = Mock()
        state.last_visible_gate.is_visible = True
        state.last_visible_gate.waypoint.on_curved_segment = False
        self.calculator.calculate_outside_route([position], state)
        self.calculator.update_score.assert_not_called()

    def test_track_ending_inside_zone_without_exit_never_scores_penalty(self):
        """CURRENT BEHAVIOR (documented, not asserted as correct): the
        penalty-zone score is only emitted on exit (check_inside_
        prohibited_zone, penalty_zone_calculator.py:129-144); finalise()
        is a bare `pass` with no end-of-track fallback. A contestant whose
        track ends while still inside a penalty zone (e.g. they land or
        lose signal without ever crossing back out) is only ever shown the
        zero-score "entering" informational message and never actually
        penalized for the time spent inside, unlike prohibited zones which
        score immediately after the grace period regardless of when/if the
        contestant leaves. Flagged as a possible fairness gap for the user
        to weigh in on, not asserted as correct."""
        state = Mock(OrchestratorState)
        state.last_visible_gate = Mock()
        state.last_visible_gate.is_visible = True
        state.last_visible_gate.waypoint.on_curved_segment = False

        position = self.create_position(60.5, 11.5, datetime.datetime(2020, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc))
        self.calculator.calculate_outside_route([position], state)
        position = self.create_position(60.5, 11.5, datetime.datetime(2020, 1, 1, 0, 5, 0, tzinfo=datetime.timezone.utc))
        self.calculator.calculate_outside_route([position], state)
        self.calculator.finalise([position])

        # Only the zero-score "entering" informational message was ever
        # emitted - no non-zero exit-scoring message for the 5 minutes spent
        # inside the zone.
        for call_args in self.calculator.update_score.call_args_list:
            message = call_args.args[0]
            self.assertEqual(message.score, 0)
            self.assertEqual(message.message, "entering penalty zone test")
