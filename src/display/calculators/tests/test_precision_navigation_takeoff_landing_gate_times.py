"""Regression test for the precision-navigation compiled gate-times filter dropping
takeoff/landing gate times.

CurveOrPrecisionNavigationStrategy.update_gate_times filters the compiled gate_times
dict down to route.waypoints names only, before persisting it as the contestant's
ContestantTaskConfiguration.compiled_gate_times_payload. That silently drops any
takeoff/landing gate times calculate_missing_gate_times had put there.
TakeoffAndLandingGateCalculator.initiate_takeoff_and_landing_gates then does an
unguarded self.contestant.gate_times[gate.name] lookup for every route.takeoff_gates/
landing_gates entry - a KeyError at calculator construction for any 2.A2 precision
navigation task whose route has an authored takeoff or landing gate.
"""

import datetime
from queue import Queue
from unittest.mock import patch

from django.test import TestCase

from display.calculators.calculator_factory import calculator_factory
from display.default_scorecards.create_scorecards import create_scorecards
from display.models import Aeroplane, Contest, Contestant, Crew, EditableRoute, NavigationTask, Person, Scorecard, Team
from display.services.contestant_task_compiler import ContestantTaskCompiler
from display.utilities.cima_task_type_definitions import PRECISION_NAVIGATION
from display.utilities.navigation_task_type_definitions import PRECISION
from utilities.mock_utilities import TraccarMock


class TestPrecisionNavigationTakeoffLandingGateTimes(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        create_scorecards()
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        self.editable_route = EditableRoute.objects.create(
            name="Precision navigation with takeoff/landing gates",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"featureType": "route_path"},
                        "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1], [11.2, 60.2]]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-1",
                            "name": "SP",
                            "pointType": "sp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 0,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.0, 60.0]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-2",
                            "name": "TP1",
                            "pointType": "tp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 1,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.1, 60.1]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-3",
                            "name": "FP",
                            "pointType": "fp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 2,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"featureType": "takeoff_gate"},
                        "geometry": {"type": "LineString", "coordinates": [[10.98, 59.98], [10.99, 59.99]]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"featureType": "landing_gate"},
                        "geometry": {"type": "LineString", "coordinates": [[11.21, 60.21], [11.22, 60.22]]},
                    },
                ],
            },
        )
        self.route = self.editable_route.create_route(PRECISION, self.scorecard, None, None, task_subtype=PRECISION_NAVIGATION)
        self.assertEqual(len(self.route.takeoff_gates), 1)
        self.assertEqual(len(self.route.landing_gates), 1)

        self.contest = Contest.objects.create(
            name="Precision navigation gate times contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
            time_zone="Europe/Oslo",
        )
        self.navigation_task = NavigationTask.create(
            name="Precision navigation gate times task",
            contest=self.contest,
            route=self.route,
            editable_route=self.editable_route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
            task_subtype=PRECISION_NAVIGATION,
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Pilot", last_name="TwoA2"))
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-A2G8"))
        start_time = datetime.datetime(2020, 8, 1, 8, 5, tzinfo=datetime.timezone.utc)
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_device_id="a2g8-test",
            contestant_number=1,
            minutes_to_starting_point=6,
            air_speed=75,
            wind_direction=165,
            wind_speed=8,
        )
        # A fully valid declaration (predictions for every real turnpoint) so
        # ContestantTaskConfiguration.is_valid is True - Contestant.gate_times only
        # reads compiled_gate_times_payload (the buggy filtered dict) when valid;
        # an invalid config falls back to calculate_missing_gate_times directly,
        # which never hits the bug.
        compiled = ContestantTaskCompiler(self.contestant).compile(
            declaration_payload={
                "known_time_gate_predictions": {
                    "SP": "2020-08-01T08:11:00Z",
                    "TP1": "2020-08-01T08:20:00Z",
                    "FP": "2020-08-01T08:30:00Z",
                }
            },
            force=True,
        )
        self.assertTrue(compiled.is_valid, compiled.validation_errors)
        self.contestant.refresh_from_db()

    def test_compiled_gate_times_include_takeoff_and_landing_gate_names(self):
        payload = self.contestant.contestanttaskconfiguration.compiled_gate_times_payload
        self.assertIn("Takeoff 1", payload)
        self.assertIn("Landing 1", payload)

    def test_takeoff_and_landing_gate_calculator_construction_does_not_raise(self):
        # Before the fix, this raised KeyError('Takeoff 1') inside
        # TakeoffAndLandingGateCalculator.initiate_takeoff_and_landing_gates,
        # called synchronously from Orchestrator.__init__ via calculator_factory -
        # i.e. calculator construction for any live 2.A2 contestant on a route
        # with an authored takeoff/landing gate.
        orchestrator = calculator_factory(self.contestant, Queue(), live_processing=False, projector=None)
        takeoff_landing = next(c for c in orchestrator.calculators if type(c).__name__ == "TakeoffAndLandingGateCalculator")
        self.assertEqual(takeoff_landing.takeoff_gate.gates[0].name, "Takeoff 1")
        self.assertEqual(takeoff_landing.landing_gate.gates[0].name, "Landing 1")
