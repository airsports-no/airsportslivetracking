import datetime
from unittest.mock import Mock

from django.test import TransactionTestCase

from display.calculators.penalty_zone_calculator import PenaltyZoneCalculator
from display.models import Prohibited, Route


class TestPenaltyZoneCalculator(TransactionTestCase):
    def setUp(self):
        self.route = Route.objects.create(name="test")
        Prohibited.objects.create(name="test", path=[(60, 11), (60, 12), (61, 12), (61, 11)],
                                  route=self.route,
                                  type="penalty")
        from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
        self.update_score = Mock()
        self.calculator = PenaltyZoneCalculator(None, get_default_scorecard(), [], self.route, self.update_score)

    def test_inside_enroute(self):
        position = Mock()
        position.latitude = 60.5
        position.longitude = 11.5
        gate = Mock()
        self.calculator.calculate_enroute([position], gate, gate)
        self.update_score.assert_called_with(gate, 0, 'entered penalty zone test', 60.5, 11.5, 'info',
                                             'inside_penalty_zone')

    def test_inside_outside_route(self):
        position = Mock()
        position.latitude = 60.5
        position.longitude = 11.5
        gate = Mock()
        self.calculator.calculate_outside_route([position], gate)
        self.update_score.assert_called_with(gate, 0, 'entered penalty zone test', 60.5, 11.5, 'info',
                                             'inside_penalty_zone')

    def test_in_and_out_within_grace_time_enroute(self):
        position = Mock()
        position.latitude = 60.5
        position.longitude = 11.5
        position.time = datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)
        gate = Mock()
        self.calculator.calculate_outside_route([position], gate)
        self.update_score.assert_called_with(gate, 0, 'entered penalty zone test', 60.5, 11.5, 'info',
                                             'inside_penalty_zone')

        position = Mock()
        position.latitude = 59.5
        position.longitude = 11.5
        position.time = datetime.datetime(2020, 1, 1, 0, 0, 2, tzinfo=datetime.timezone.utc)
        gate = Mock()
        self.calculator.calculate_outside_route([position], gate)
        self.update_score.assert_called_with(gate, 0, 'exited penalty zone test', 59.5, 11.5, 'anomaly',
                                             'inside_penalty_zone')

    def test_in_and_out_beyond_grace_time_enroute(self):
        position = Mock()
        position.latitude = 60.5
        position.longitude = 11.5
        position.time = datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)
        gate = Mock()
        self.calculator.calculate_outside_route([position], gate)
        self.update_score.assert_called_with(gate, 0, 'entered penalty zone test', 60.5, 11.5, 'info',
                                             'inside_penalty_zone')

        position = Mock()
        position.latitude = 59.5
        position.longitude = 11.5
        position.time = datetime.datetime(2020, 1, 1, 0, 0, 10, tzinfo=datetime.timezone.utc)
        gate = Mock()
        self.calculator.calculate_outside_route([position], gate)
        self.update_score.assert_called_with(gate, 21, 'exited penalty zone test', 59.5, 11.5, 'anomaly',
                                             'inside_penalty_zone')

    def test_outside_enroute(self):
        position = Mock()
        position.latitude = 59.5
        position.longitude = 11.5
        gate = Mock()
        self.calculator.calculate_enroute([position], gate, gate)
        self.update_score.assert_not_called()

    def test_outside_outside_route(self):
        position = Mock()
        position.latitude = 59.5
        position.longitude = 11.5
        gate = Mock()
        self.calculator.calculate_outside_route([position], gate)
        self.update_score.assert_not_called()
