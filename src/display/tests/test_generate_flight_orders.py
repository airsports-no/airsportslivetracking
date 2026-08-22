import datetime
import os
from io import BytesIO
from unittest.mock import patch

from django.test import TransactionTestCase
from PIL import Image

from display.default_scorecards import default_scorecard_fai_precision_2020
from display.flight_order_and_maps.generate_flight_orders import embed_map_in_pdf, generate_flight_orders
from display.flight_order_and_maps.map_constants import A3, LANDSCAPE
from display.models import Aeroplane, Contest, Contestant, Crew, NavigationTask, Person, Team
from display.utilities.route_building_utilities import create_precision_route_from_gpx
from utilities.mock_utilities import TraccarMock


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class GenerateFlightOrdersTests(TransactionTestCase):
    def setUp(self, *args):
        with open(
            os.path.join(os.path.dirname(__file__), "demo_contests", "2017_WPFC", "Route-1-Blue.gpx"), "r"
        ) as file:
            route = create_precision_route_from_gpx(file, True)
        navigation_task_start_time = datetime.datetime(2020, 8, 1, 6, 0, 0).astimezone()
        navigation_task_finish_time = datetime.datetime(2020, 8, 1, 16, 0, 0).astimezone()
        self.aeroplane = Aeroplane.objects.create(registration="LN-YDB")
        self.navigation_task = NavigationTask.create(
            name="NM navigation_task",
            route=route,
            original_scorecard=default_scorecard_fai_precision_2020.get_default_scorecard(),
            contest=Contest.objects.create(
                name="contest",
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
                email="mister_flight_order_test@pilot.com",
            )
        )
        self.team = Team.objects.create(crew=crew, aeroplane=self.aeroplane)
        self.navigation_task.refresh_from_db()
        start_time = datetime.datetime(2020, 8, 1, 7, 30, tzinfo=datetime.timezone.utc)
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=self.team,
            takeoff_time=start_time,
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            tracker_device_id="Test contestant",
            contestant_number=1,
            minutes_to_starting_point=8,
            air_speed=80,
            wind_direction=160,
            wind_speed=18,
        )

    def test_generate_flight_order(self, *args):
        pdf_bytes = generate_flight_orders(self.contestant)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        self.assertGreater(len(pdf_bytes), 1000)

    def test_generate_flight_order_with_turning_point_images(self, *args):
        configuration = self.navigation_task.flightorderconfiguration
        configuration.include_turning_point_images = True
        configuration.save()
        pdf_bytes = generate_flight_orders(self.contestant)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    def test_generate_flight_order_a3_landscape(self, *args):
        configuration = self.navigation_task.flightorderconfiguration
        configuration.document_size = A3
        configuration.map_orientation = LANDSCAPE
        configuration.save()
        pdf_bytes = generate_flight_orders(self.contestant)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    def test_generate_flight_order_escapes_special_characters(self, *args):
        # Team names/rules text come from user data and must never be interpreted
        # as Typst markup (e.g. "#", "*", "[", "]" breaking or injecting layout).
        self.team.crew.member1.first_name = 'Team #1 * [Ø] 100% <tag> @user \\backslash "quoted"'
        self.team.crew.member1.save()
        pdf_bytes = generate_flight_orders(self.contestant)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    def test_embed_map_in_pdf(self, *args):
        buf = BytesIO()
        Image.new("RGB", (400, 300), (100, 150, 200)).save(buf, format="PNG")
        pdf_bytes = embed_map_in_pdf("a4paper", buf.getvalue(), 190.0, 277.0, False)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
