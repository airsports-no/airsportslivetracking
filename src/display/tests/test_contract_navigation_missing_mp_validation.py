"""
Regression test for models+services finding #4 (2026-08-28 review):
_build_contract_navigation_declared_gate_times built gate times before validation ran,
and unconditionally did datetime.fromisoformat(gate_times["MP"]) - but "MP" is only
present if "MP" was in declared_sequence. The REST API lets a client post
declared_sequence directly (skipping the synthesis that normally guarantees an "MP"
entry), so declared_t_seconds > 0 with no "MP" in declared_sequence raised a bare
KeyError - a 500 - instead of the "requires exactly one MP" validation error
ContractNavigationStrategy.validate_declaration already exists to produce.
"""

import datetime
from unittest.mock import patch

from django.test import TestCase

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import Aeroplane, Contest, Contestant, Crew, EditableRoute, NavigationTask, Person, Route, Scorecard, Team
from display.services.contestant_task_compiler import ContestantTaskCompiler
from display.utilities.cima_task_type_definitions import CONTRACT_NAVIGATION_TIME_CONTROLS
from utilities.mock_utilities import TraccarMock


class TestContractNavigationMissingMpValidation(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        create_scorecards()
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        # A real backbone (SP/.../FP) is required here, unlike task-level compiler tests -
        # ContestantTaskCompiler reads contestant.navigation_task.route.waypoints directly to
        # build declared-sequence effective waypoints (_build_contract_navigation_effective_waypoints
        # returns [] for an empty backbone, short-circuiting before ever reaching the bug).
        with open("display/tests/NM.csv", "r") as file:
            editable_route_for_backbone, _ = EditableRoute.create_from_csv("Missing MP backbone", file.readlines()[1:])
            self.route = editable_route_for_backbone.create_precision_route(True, self.scorecard)
        self.editable_route = EditableRoute.objects.create(
            name="Contract nav missing MP primitives",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"featureType": "route_path"},
                        "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-sp",
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
                            "id": "wp-mp",
                            "name": "MP",
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
                            "id": "wp-fp",
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
                        "properties": {"id": "cat-1", "name": "A", "pointType": "tp", "featureType": "catalogue_turnpoint"},
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "cat-2", "name": "B", "pointType": "tp", "featureType": "catalogue_turnpoint"},
                        "geometry": {"type": "Point", "coordinates": [11.3, 60.3]},
                    },
                ],
            },
        )
        self.contest = Contest.objects.create(
            name="Missing MP contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
            time_zone="Europe/Oslo",
        )
        self.navigation_task = NavigationTask.create(
            name="Missing MP task",
            contest=self.contest,
            route=self.route,
            editable_route=self.editable_route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
            task_subtype=CONTRACT_NAVIGATION_TIME_CONTROLS,
            task_config={"contract_time_seconds": 600},
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Pilot", last_name="MissingMP"))
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-NOMP"))
        start_time = datetime.datetime(2020, 8, 1, 8, 5, tzinfo=datetime.timezone.utc)
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_device_id="no-mp-test",
            contestant_number=1,
            minutes_to_starting_point=6,
            air_speed=75,
            wind_direction=165,
            wind_speed=8,
        )

    def test_declared_sequence_without_mp_and_positive_t_seconds_produces_a_validation_error_not_a_500(self):
        # Client posts declared_sequence directly with no "MP" entry - the normal
        # synthesis path (build_declaration_payload_from_input's before/after-MP lists)
        # is bypassed entirely, exactly like a raw REST API payload would.
        compiled = ContestantTaskCompiler(self.contestant).compile(
            declaration_payload={"declared_sequence": ["A", "B", "FP"], "declared_t_seconds": 82},
            force=True,
        )

        self.assertFalse(compiled.is_valid)
        joined_errors = " ".join(compiled.validation_errors)
        self.assertIn("exactly one MP", joined_errors)
