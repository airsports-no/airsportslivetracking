import datetime
from unittest.mock import Mock

from django.test import TransactionTestCase

from display.calculators.calculator import OrchestratorState
from display.calculators.prohibited_zone_calculator import ProhibitedZoneCalculator
from display.calculators.update_score_message import UpdateScoreMessage
from display.models import Prohibited, Route
from display.waypoint import Waypoint
from display.utilities.coordinate_utilities import Projector


class TestProhibitedZoneCalculator(TransactionTestCase):
    def setUp(self):
        self.route = Route.objects.create(name="test")
        Prohibited.objects.create(
            name="test", path=[(11, 60), (12, 60), (12, 61), (11, 61)], route=self.route, type="prohibited"
        )
        from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard

        self.contestant = Mock()
        waypoint = Waypoint("")
        waypoint.latitude = 60
        waypoint.longitude = 11
        self.contestant.navigation_task.route.waypoints = [waypoint]
        
        self.projector = Projector(60, 11)
        self.calculator = ProhibitedZoneCalculator(self.contestant, get_default_scorecard(), self.route, Mock(), projector=self.projector)
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

    def test_inside_enroute_before_grace_time(self):
        position = self.create_position(60.5, 11.5, datetime.datetime(2023, 6, 22, 12))
        state = Mock(OrchestratorState)
        state.last_visible_gate = Mock()
        self.calculator.calculate_enroute([position], state)
        position = self.create_position(60.5, 11.5, datetime.datetime(2023, 6, 22, 12, 0, 3))
        self.calculator.update_score.assert_not_called()

    def test_inside_enroute_after_grace_time(self):
        position = self.create_position(60.5, 11.5, datetime.datetime(2023, 6, 22, 12))
        state = Mock(OrchestratorState)
        state.last_visible_gate = Mock()

        self.calculator.calculate_enroute([position], state)
        position = self.create_position(60.5, 11.5, datetime.datetime(2023, 6, 22, 12, 0, 7))
        self.calculator.calculate_enroute([position], state)
        self.calculator.update_score.assert_called_with(
            UpdateScoreMessage(
                datetime.datetime(2023, 6, 22, 12, 0, 7),
                state.last_visible_gate,
                self.calculator.scorecard.prohibited_zone_penalty,
                "entered prohibited zone test",
                60.5,
                11.5,
                "anomaly",
                "inside_prohibited_zone_test",
                maximum_score=0,
            )
        )

    def test_outside_enroute(self):
        position = self.create_position(59.5, 11.5, datetime.datetime(2023, 6, 22, 12))
        state = Mock(OrchestratorState)
        state.last_visible_gate = Mock()
        self.calculator.calculate_enroute([position], state)
        self.calculator.update_score.assert_not_called()
        position = self.create_position(59.5, 11.5, datetime.datetime(2023, 6, 22, 12, 1))
        self.calculator.calculate_enroute([position], state)
        self.calculator.update_score.assert_not_called()

    def test_outside_outside_route(self):
        position = self.create_position(59.5, 11.5, datetime.datetime(2023, 6, 22, 12))
        state = Mock(OrchestratorState)
        state.last_visible_gate = Mock()
        self.calculator.calculate_outside_route([position], state)
        self.calculator.update_score.assert_not_called()
        position = self.create_position(59.5, 11.5, datetime.datetime(2023, 6, 22, 12))
        self.calculator.calculate_outside_route([position], state)
        self.calculator.update_score.assert_not_called()
