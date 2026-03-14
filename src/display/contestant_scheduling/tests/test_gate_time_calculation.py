import datetime
from unittest.mock import patch

from django.test import TestCase

from display.models.contest import Contest
from display.models.contestant import Contestant
from display.models.editable_route import EditableRoute
from display.models.navigation_task import NavigationTask
from display.models.team_structure import Aeroplane, Crew, Person, Team
from utilities.mock_utilities import TraccarMock


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.calculators.contestant_processor.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestGateTimeCalculation(TestCase):
    def test_gate_time_calculation(self, *args):
        editable_route = EditableRoute.objects.create(
            name="Test Route",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"featureType": "route_path"},
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [
                                [-0.5629956722259523, 39.67034733986822],
                                [-0.6645011901855469, 39.717994611067205],
                                [-0.7961424578228573, 39.72110245103177],
                                [-0.8604625133804334, 39.67265988187228],
                                [-0.811699086056501, 39.65764598786738],
                                [-0.7461244400604073, 39.69853280812744],
                                [-0.6580205394889839, 39.66074626973707],
                                [-0.5805154277946479, 39.646546722937515],
                            ],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "90e01231-a729-4332-8c1c-cea6f6825818",
                            "name": "Start",
                            "pointType": "sp",
                            "featureType": "route_waypoint",
                            "segmentType": "straight",
                            "controlLat": 0,
                            "controlLng": 0,
                            "width": 741,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 0,
                        },
                        "geometry": {"type": "Point", "coordinates": [-0.5629956722259523, 39.67034733986822]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "fb86c974-4c86-4bc5-8dd3-9c1d41d93149",
                            "name": "WP 2",
                            "pointType": "tp",
                            "featureType": "route_waypoint",
                            "segmentType": "straight",
                            "controlLat": 0,
                            "controlLng": 0,
                            "width": 741,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 1,
                        },
                        "geometry": {"type": "Point", "coordinates": [-0.6645011901855469, 39.717994611067205]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "95f9960b-cefe-4d3e-9586-9af3e753b9d3",
                            "name": "WP3",
                            "pointType": "tp",
                            "featureType": "route_waypoint",
                            "segmentType": "straight",
                            "controlLat": 0,
                            "controlLng": 0,
                            "width": 741,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 2,
                        },
                        "geometry": {"type": "Point", "coordinates": [-0.7961424578228573, 39.72110245103177]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "53d0ae7d-6ff1-40f1-9cd7-b04056353c62",
                            "name": "WP 6",
                            "pointType": "tp",
                            "featureType": "route_waypoint",
                            "segmentType": "straight",
                            "controlLat": 0,
                            "controlLng": 0,
                            "width": 778,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 3,
                        },
                        "geometry": {"type": "Point", "coordinates": [-0.8604625133804334, 39.67265988187228]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "70d48cea-6898-47e5-b3f6-d3ac8917c91c",
                            "name": "WP 7",
                            "pointType": "tp",
                            "featureType": "route_waypoint",
                            "segmentType": "straight",
                            "controlLat": 0,
                            "controlLng": 0,
                            "width": 741,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 4,
                        },
                        "geometry": {"type": "Point", "coordinates": [-0.811699086056501, 39.65764598786738]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "081bf525-a67b-4025-b76d-38f42c3dc47f",
                            "name": "WP 8",
                            "pointType": "tp",
                            "featureType": "route_waypoint",
                            "segmentType": "straight",
                            "controlLat": 0,
                            "controlLng": 0,
                            "width": 741,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 5,
                        },
                        "geometry": {"type": "Point", "coordinates": [-0.7461244400604073, 39.69853280812744]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "d1848493-594c-4cdc-9e49-6dc1f52a96be",
                            "name": "WP 9",
                            "pointType": "tp",
                            "featureType": "route_waypoint",
                            "segmentType": "straight",
                            "controlLat": 0,
                            "controlLng": 0,
                            "width": 741,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 6,
                        },
                        "geometry": {"type": "Point", "coordinates": [-0.6580205394889839, 39.66074626973707]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "76878917-7cdb-4d72-85b2-6c60f7dc0752",
                            "name": "FP",
                            "pointType": "fp",
                            "featureType": "route_waypoint",
                            "segmentType": "straight",
                            "controlLat": 0,
                            "controlLng": 0,
                            "width": 741,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 7,
                        },
                        "geometry": {"type": "Point", "coordinates": [-0.5805154277946479, 39.646546722937515]},
                    },
                ],
            },
            settings={"showCorridor": False, "maxObsDist": 926, "hideLabels": False},
        )

        navigation_task_start_time = datetime.datetime(2021, 3, 31, 14, 0, 0, tzinfo=datetime.timezone.utc)
        navigation_task_finish_time = datetime.datetime(2021, 3, 31, 16, 0, 0, tzinfo=datetime.timezone.utc)
        self.aeroplane = Aeroplane.objects.create(registration="LN-YDB")
        from display.default_scorecards import default_scorecard_airsport_challenge

        self.navigation_task = NavigationTask.create(
            name="NM navigation_task",
            route=editable_route.create_airsports_route(
                True, default_scorecard_airsport_challenge.get_default_scorecard()
            ),
            original_scorecard=default_scorecard_airsport_challenge.get_default_scorecard(),
            contest=Contest.objects.create(
                name="contest_{}_{}".format(self.__class__.__name__, datetime.datetime.now().timestamp()),
                start_time=datetime.datetime.now(datetime.timezone.utc),
                finish_time=datetime.datetime.now(datetime.timezone.utc),
                time_zone="Europe/Oslo",
            ),
            start_time=navigation_task_start_time,
            finish_time=navigation_task_finish_time,
        )
        crew = Crew.objects.create(
            member1=Person.objects.create(
                first_name="Mister",
                last_name="Pilot",
                email="mister_{}_{}@pilot.com".format(self.__class__.__name__, datetime.datetime.now().timestamp()),
            )
        )
        self.team = Team.objects.create(crew=crew, aeroplane=self.aeroplane)
        # Required to make the time zone save correctly
        self.navigation_task.refresh_from_db()

        # This test will check the gate time calculation logic, especially for start and finish gates.
        # We will create a contestant, assign them a track with specific positions and times, and then
        # verify that the gate times are calculated correctly.
        start_time, speed = (
            datetime.datetime(2025, 3, 2, 12, 00, tzinfo=datetime.timezone.utc),
            60,
        )

        # Create a contestant
        contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=self.team,
            takeoff_time=start_time,
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            tracker_device_id="Test contestant",
            contestant_number=1,
            minutes_to_starting_point=7,
            adaptive_start=True,
            air_speed=speed,
            wind_direction=340,
            wind_speed=15,
        )

        gate_times = contestant.gate_times
        self.assertDictEqual(
            {
                "Start": datetime.datetime(2025, 3, 2, 12, 7, tzinfo=datetime.timezone.utc),
                "WP 2": datetime.datetime(2025, 3, 2, 12, 13, 57, tzinfo=datetime.timezone.utc),
                "WP3": datetime.datetime(2025, 3, 2, 12, 20, 52, tzinfo=datetime.timezone.utc),
                "WP 6": datetime.datetime(2025, 3, 2, 12, 24, 44, tzinfo=datetime.timezone.utc),
                "WP 7": datetime.datetime(2025, 3, 2, 12, 26, 51, tzinfo=datetime.timezone.utc),
                "WP 8": datetime.datetime(2025, 3, 2, 12, 31, 14, tzinfo=datetime.timezone.utc),
                "WP 9": datetime.datetime(2025, 3, 2, 12, 35, 13, tzinfo=datetime.timezone.utc),
                "FP": datetime.datetime(2025, 3, 2, 12, 38, 31, tzinfo=datetime.timezone.utc),
            },
            gate_times,
        )
