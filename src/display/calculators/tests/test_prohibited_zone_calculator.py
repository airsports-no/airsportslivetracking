import datetime
from unittest.mock import Mock

from django.test import TransactionTestCase

from display.calculators.prohibited_zone_calculator import ProhibitedZoneCalculator
from display.calculators.update_score_message import UpdateScoreMessage
from display.models import Prohibited, Route
from display.waypoint import Waypoint


class TestProhibitedZoneCalculator(TransactionTestCase):
    def setUp(self):
        self.route = Route.objects.create(name="test")
        Prohibited.objects.create(
            name="test", path=[(60, 11), (60, 12), (61, 12), (61, 11)], route=self.route, type="prohibited"
        )
        from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard

        self.contestant = Mock()
        waypoint = Waypoint("")
        waypoint.latitude = 60
        waypoint.longitude = 11
        self.contestant.route.waypoints = [waypoint]
        self.calculator = ProhibitedZoneCalculator(self.contestant, get_default_scorecard(), [], self.route, Mock())
        self.calculator.update_score = Mock()

    def test_inside_enroute_before_grace_time(self):
        position = Mock()
        position.latitude = 60.5
        position.longitude = 11.5
        position.time = datetime.datetime(2023, 6, 22, 12)
        gate = Mock()
        self.calculator.calculate_enroute([position], gate, gate, None)
        position = Mock()
        position.latitude = 60.5
        position.longitude = 11.5
        position.time = datetime.datetime(2023, 6, 22, 12, 0, 3)
        self.calculator.update_score.assert_not_called()

    def test_inside_enroute_after_grace_time(self):
        position = Mock()
        position.latitude = 60.5
        position.longitude = 11.5
        position.time = datetime.datetime(2023, 6, 22, 12)
        gate = Mock()
        self.calculator.calculate_enroute([position], gate, gate, None)
        position = Mock()
        position.latitude = 60.5
        position.longitude = 11.5
        position.time = datetime.datetime(2023, 6, 22, 12, 0, 7)
        self.calculator.calculate_enroute([position], gate, gate, None)
        self.calculator.update_score.assert_called_with(
            UpdateScoreMessage(
                datetime.datetime(2023, 6, 22, 12, 0, 7),
                gate,
                self.calculator.scorecard.prohibited_zone_penalty,
                "entered prohibited zone test",
                60.5,
                11.5,
                "anomaly",
                "inside_prohibited_zone",
            )
        )

    def test_outside_enroute(self):
        position = Mock()
        position.latitude = 59.5
        position.longitude = 11.5
        position.time = datetime.datetime(2023, 6, 22, 12)
        gate = Mock()
        self.calculator.calculate_enroute([position], gate, gate, None)
        self.calculator.update_score.assert_not_called()
        position = Mock()
        position.latitude = 59.5
        position.longitude = 11.5
        position.time = datetime.datetime(2023, 6, 22, 12, 1)
        self.calculator.calculate_enroute([position], gate, gate, None)
        self.calculator.update_score.assert_not_called()

    def test_outside_outside_route(self):
        position = Mock()
        position.latitude = 59.5
        position.longitude = 11.5
        position.time = datetime.datetime(2023, 6, 22, 12)
        gate = Mock()
        self.calculator.calculate_outside_route([position], gate)
        self.calculator.update_score.assert_not_called()
        position = Mock()
        position.latitude = 59.5
        position.longitude = 11.5
        position.time = datetime.datetime(2023, 6, 22, 12)
        self.calculator.calculate_outside_route([position], gate)
        self.calculator.update_score.assert_not_called()
