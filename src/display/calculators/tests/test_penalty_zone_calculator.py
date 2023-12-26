import datetime
from unittest.mock import Mock, call

from django.test import TransactionTestCase

from display.calculators.penalty_zone_calculator import PenaltyZoneCalculator
from display.models import Prohibited, Route
from display.waypoint import Waypoint


class TestPenaltyZoneCalculator(TransactionTestCase):
    def setUp(self):
        self.route = Route.objects.create(name="test")
        Prohibited.objects.create(name="test", path=[(60, 11), (60, 12), (61, 12), (61, 11)],
                                  route=self.route,
                                  type="penalty")
        from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
        self.update_score = Mock()
        self.contestant = Mock()
        waypoint = Waypoint("")
        waypoint.latitude = 60
        waypoint.longitude = 11
        self.contestant.navigation_task.route.waypoints = [waypoint]
        self.calculator = PenaltyZoneCalculator(self.contestant, get_default_scorecard(), [], self.route,
                                                self.update_score)
        self.calculator.scorecard.penalty_zone_grace_time = 3
        self.calculator.scorecard.penalty_zone_penalty_per_second = 3
        self.calculator.scorecard.penalty_zone_maximum = 200

    def test_inside_enroute(self):
        position = Mock()
        position.latitude = 60.5
        position.longitude = 11.5
        position.time = datetime.datetime(2020, 1, 1, 0, 0, 2, tzinfo=datetime.timezone.utc)
        gate = Mock()
        self.calculator.calculate_enroute([position], gate, gate, None)
        self.update_score.assert_called_with(gate, 0, 'entering penalty zone test', 60.5, 11.5, 'information',
                                             'inside_penalty_zone')

    def test_inside_outside_route(self):
        position = Mock()
        position.latitude = 60.5
        position.longitude = 11.5
        position.time = datetime.datetime(2020, 1, 1, 0, 0, 2, tzinfo=datetime.timezone.utc)
        gate = Mock()
        self.calculator.calculate_outside_route([position], gate)
        self.update_score.assert_called_with(gate, 0, 'entering penalty zone test', 60.5, 11.5, 'information',
                                             'inside_penalty_zone')

    def test_in_and_out_within_grace_time_enroute(self):
        position = Mock()
        position.latitude = 60.5
        position.longitude = 11.5
        position.time = datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)
        gate = Mock()
        self.calculator.calculate_outside_route([position], gate)
        self.update_score.assert_called_with(gate, 0, 'entering penalty zone test', 60.5, 11.5, 'information',
                                             'inside_penalty_zone')

        position = Mock()
        position.latitude = 59.5
        position.longitude = 11.5
        position.time = datetime.datetime(2020, 1, 1, 0, 0, 2, tzinfo=datetime.timezone.utc)
        gate = Mock()
        self.calculator.calculate_outside_route([position], gate)
        self.update_score.assert_called_with(gate, 0, 'inside penalty zone test (2s)', 59.5, 11.5, 'anomaly',
                                             'inside_penalty_zone')

    def test_in_and_out_beyond_grace_time_enroute(self):
        position = Mock()
        position.latitude = 60.5
        position.longitude = 11.5
        gate = Mock()
        for index in range(0, 30, 3):
            position.time = datetime.datetime(2020, 1, 1, second=index, tzinfo=datetime.timezone.utc)
            self.calculator.calculate_outside_route([position], gate)
        # outside_position = Mock()
        # outside_position.latitude = 59.5
        # outside_position.longitude = 11.5
        # outside_position.time = datetime.datetime(2020, 1, 1, second=30, tzinfo=datetime.timezone.utc)
        # reference=self.calculator.existing_reference["test"]
        # self.calculator.calculate_outside_route([outside_position], gate)
        expected_calls = [
            call(gate, 0, 'entering penalty zone test', 60.5, 11.5, 'information', 'inside_penalty_zone')
            # call(gate, 81, 'inside penalty zone test', 59.5, 11.5, 'anomaly', 'inside_penalty_zone',
            #      existing_reference=reference)
        ]
        self.update_score.assert_has_calls(expected_calls)

        position = Mock()
        position.latitude = 59.5
        position.longitude = 11.5
        position.time = datetime.datetime(2020, 1, 1, 0, 0, 10, tzinfo=datetime.timezone.utc)
        gate = Mock()
        self.calculator.calculate_outside_route([position], gate)
        self.update_score.assert_called_with(gate, 21, 'inside penalty zone test (10s)', 59.5, 11.5, 'anomaly',
                                             'inside_penalty_zone')

    def test_outside_enroute(self):
        position = Mock()
        position.latitude = 59.5
        position.longitude = 11.5
        gate = Mock()
        self.calculator.calculate_enroute([position], gate, gate, None)
        self.update_score.assert_not_called()

    def test_outside_outside_route(self):
        position = Mock()
        position.latitude = 59.5
        position.longitude = 11.5
        gate = Mock()
        self.calculator.calculate_outside_route([position], gate)
        self.update_score.assert_not_called()
