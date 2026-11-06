"""The documents an organiser makes in advance: the flight order's map for a range of speeds in a wind, and the
turning point images and observation photos, each as one PDF."""

import datetime
import os
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from guardian.shortcuts import assign_perm
from PIL import Image
from rest_framework.test import APITestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.flight_order_and_maps import generate_flight_orders
from display.flight_order_and_maps.generate_flight_orders import (
    generate_speed_maps_pdf,
    generate_task_images_pdf,
    speed_wind_stand_in_contestant,
)
from display.models import Contest, FlightOrderConfiguration, NavigationTask
from display.utilities.gate_definitions import UNKNOWN_LEG
from display.tasks import generate_speed_maps_async, generate_task_images_async, prepared_pdf_cache_key
from display.utilities.route_building_utilities import create_precision_route_from_gpx
from utilities.mock_utilities import TraccarMock

UTC = datetime.timezone.utc


def make_task(name="Prepared maps") -> NavigationTask:
    with open(os.path.join(os.path.dirname(__file__), "demo_contests", "2017_WPFC", "Route-1-Blue.gpx"), "r") as file:
        route = create_precision_route_from_gpx(file, True)
    now = datetime.datetime.now(UTC)
    contest = Contest.objects.create(name="Prepared Cup", start_time=now, finish_time=now, is_public=True)
    task = NavigationTask.create(
        name=name,
        original_scorecard=get_default_scorecard(),
        start_time=now,
        finish_time=now + datetime.timedelta(hours=8),
        route=route,
        contest=contest,
        is_public=True,
    )
    FlightOrderConfiguration.objects.get_or_create(navigation_task=task)
    return task


def png() -> BytesIO:
    buffer = BytesIO()
    Image.new("RGB", (40, 60), "white").save(buffer, "PNG")
    buffer.seek(0)
    return buffer


class PreparedPdfApiTest(APITestCase):
    URL = "/api/v1/contests/{contest}/navigationtasks/{task}/{action}/"

    def setUp(self):
        for target in ("display.models.contestant.get_traccar_instance", "display.signals.get_traccar_instance"):
            patcher = patch(target, return_value=TraccarMock)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.task = make_task()
        self.manager = get_user_model().objects.create(email="manager@example.com")
        assign_perm("view_contest", self.manager, self.task.contest)
        assign_perm("change_contest", self.manager, self.task.contest)
        self.viewer = get_user_model().objects.create(email="viewer@example.com")
        assign_perm("view_contest", self.viewer, self.task.contest)
        self.client.force_login(self.manager)
        cache.clear()

    def url(self, action):
        return self.URL.format(contest=self.task.contest_id, task=self.task.pk, action=action)

    def post_speed_maps(self, **data):
        payload = {"speeds": [90, 70, 80, 70], "wind_speed": 15, "wind_direction": 250, **data}
        with patch("display.viewsets.generate_speed_maps_async.delay") as delay:
            response = self.client.post(self.url("generate_speed_maps"), payload, format="json")
        return response, delay

    def test_a_manager_starts_the_maps_with_each_speed_once_slowest_first(self):
        response, delay = self.post_speed_maps()
        self.assertEqual(response.status_code, 202, response.content)
        delay.assert_called_once_with(self.task.pk, [70.0, 80.0, 90.0], 15.0, 250.0, self.manager.pk)
        self.assertTrue(response.json()["status_check_url"].endswith("prepared-pdf-status/?kind=speed_maps"))

    def test_the_speeds_and_wind_are_checked(self):
        for data, field in (
            ({"speeds": []}, "speeds"),
            ({"speeds": [10]}, "speeds"),
            ({"speeds": [60 + n for n in range(21)]}, "speeds"),
            ({"wind_speed": -1}, "wind_speed"),
            ({"wind_direction": 361}, "wind_direction"),
            # The gate times cannot be planned when the wind stops the aircraft
            ({"speeds": [60, 90], "wind_speed": 60}, "wind_speed"),
        ):
            response, delay = self.post_speed_maps(**data)
            self.assertEqual(response.status_code, 400, data)
            self.assertIn(field, response.json(), data)
            delay.assert_not_called()

    def test_only_managers_may_make_them(self):
        self.client.force_login(self.viewer)
        response, delay = self.post_speed_maps()
        self.assertEqual(response.status_code, 403)
        delay.assert_not_called()
        with patch("display.viewsets.generate_task_images_async.delay") as images:
            self.assertEqual(self.client.post(self.url("generate_task_images")).status_code, 403)
        images.assert_not_called()
        self.assertEqual(self.client.get(self.url("prepared-pdf-status") + "?kind=speed_maps").status_code, 403)

    def test_the_images_are_started_in_the_background(self):
        with patch("display.viewsets.generate_task_images_async.delay") as delay:
            response = self.client.post(self.url("generate_task_images"))
        self.assertEqual(response.status_code, 202, response.content)
        delay.assert_called_once_with(self.task.pk, self.manager.pk)
        self.assertTrue(response.json()["status_check_url"].endswith("prepared-pdf-status/?kind=task_images"))

    def test_the_status_is_pending_then_what_the_task_stored_for_this_user_and_kind(self):
        url = self.url("prepared-pdf-status")
        self.assertEqual(self.client.get(url + "?kind=speed_maps").json(), {"status": "pending"})
        cache.set(
            prepared_pdf_cache_key(self.task.pk, self.manager.pk, "speed_maps"), {"status": "complete", "url": "/x.pdf"}
        )
        self.assertEqual(self.client.get(url + "?kind=speed_maps").json(), {"status": "complete", "url": "/x.pdf"})
        self.assertEqual(self.client.get(url + "?kind=task_images").json(), {"status": "pending"})
        self.assertEqual(self.client.get(url + "?kind=other").status_code, 400)

    def test_asking_again_forgets_the_earlier_result(self):
        key = prepared_pdf_cache_key(self.task.pk, self.manager.pk, "speed_maps")
        cache.set(key, {"status": "complete", "url": "/old.pdf"})
        self.post_speed_maps()
        self.assertIsNone(cache.get(key))


class PreparedPdfTaskTest(TestCase):
    def setUp(self):
        for target in ("display.models.contestant.get_traccar_instance", "display.signals.get_traccar_instance"):
            patcher = patch(target, return_value=TraccarMock)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.task = make_task()
        self.user = get_user_model().objects.create(email="u@example.com")
        cache.clear()

    def result(self, kind):
        return cache.get(prepared_pdf_cache_key(self.task.pk, self.user.pk, kind))

    def test_the_maps_are_stored_and_their_address_and_warning_given(self):
        with (
            patch(
                "display.flight_order_and_maps.generate_flight_orders.generate_speed_maps_pdf",
                return_value=(b"%PDF-maps", "Lower zoom."),
            ) as generate,
            patch("display.tasks.default_storage") as storage,
        ):
            storage.save.side_effect = lambda name, content: name
            storage.url.side_effect = lambda name: f"/media/{name}"
            generate_speed_maps_async(self.task.pk, [70.0, 80.0], 10.0, 250.0, self.user.pk)
        generate.assert_called_once_with(self.task, [70.0, 80.0], 10.0, 250.0)
        result = self.result("speed_maps")
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["warning"], "Lower zoom.")
        self.assertRegex(result["url"], rf"^/media/generated_maps/{self.task.pk}/speed_maps_prepared-maps_\d+\.pdf$")
        self.assertIsNone(self.result("task_images"))

    def test_a_failure_is_given_as_an_error_with_the_reason(self):
        with patch(
            "display.flight_order_and_maps.generate_flight_orders.generate_speed_maps_pdf",
            side_effect=RuntimeError("no tiles"),
        ):
            generate_speed_maps_async(self.task.pk, [70.0], 0.0, 0.0, self.user.pk)
        self.assertEqual(self.result("speed_maps"), {"status": "error", "message": "no tiles"})

    def test_a_task_that_is_gone_is_an_error_too(self):
        generate_speed_maps_async(0, [70.0], 0.0, 0.0, self.user.pk)
        generate_task_images_async(0, self.user.pk)
        for kind in ("speed_maps", "task_images"):
            self.assertEqual(cache.get(prepared_pdf_cache_key(0, self.user.pk, kind))["status"], "error")

    def test_nothing_to_put_in_the_images_is_said_as_it_is(self):
        with patch(
            "display.flight_order_and_maps.generate_flight_orders.generate_task_images_pdf",
            side_effect=ValueError("The task has no turning point images or observation photos to put in a document."),
        ):
            generate_task_images_async(self.task.pk, self.user.pk)
        self.assertIn("no turning point images", self.result("task_images")["message"])


class SpeedMapsPdfTest(TestCase):
    def setUp(self):
        for target in ("display.models.contestant.get_traccar_instance", "display.signals.get_traccar_instance"):
            patcher = patch(target, return_value=TraccarMock)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.task = make_task()

    def gate_times(self, speed, wind_speed=0, wind_direction=0):
        return speed_wind_stand_in_contestant(self.task, speed, wind_speed, wind_direction).gate_times

    def test_the_stand_in_contestants_gate_times_are_offsets_from_the_start(self):
        slow, fast = self.gate_times(60), self.gate_times(120)
        waypoints = self.task.route.waypoints
        start, finish = waypoints[0].name, waypoints[-1].name
        zone = self.task.contest.time_zone
        # The starting point is minute zero for any speed, and the finish comes sooner the faster it is flown
        self.assertEqual(slow[start].astimezone(zone).strftime("%H:%M:%S"), "00:00:00")
        self.assertEqual(fast[start].astimezone(zone).strftime("%H:%M:%S"), "00:00:00")
        self.assertLess(fast[finish], slow[finish])
        # And a wind takes its toll
        self.assertNotEqual(self.gate_times(90, 20, 90)[finish], self.gate_times(90, 0, 0)[finish])

    def test_each_speed_gets_its_own_map_in_the_configured_style_slowest_first(self):
        calls = []

        def plot(task, size, zoom_level, **kwargs):
            calls.append((size, zoom_level, kwargs))
            return png(), zoom_level

        compiled = []
        with (
            patch.object(generate_flight_orders, "plot_route_within_memory_limit", side_effect=plot),
            patch.object(
                generate_flight_orders,
                "_compile_typst",
                side_effect=lambda source: compiled.append(source) or b"%PDF-maps",
            ),
        ):
            pdf, warning = generate_speed_maps_pdf(self.task, [100, 80, 80], 12, 250)
        self.assertEqual((pdf, warning), (b"%PDF-maps", None))
        configuration = self.task.flightorderconfiguration
        self.assertEqual([call[2]["contestant"].air_speed for call in calls], [80, 100])
        for size, zoom_level, kwargs in calls:
            self.assertEqual(size, configuration.document_size)
            self.assertEqual(zoom_level, configuration.map_zoom_level)
            self.assertEqual((kwargs["contestant"].wind_speed, kwargs["contestant"].wind_direction), (12, 250))
            self.assertEqual(kwargs["annotations"], configuration.map_include_annotations)
            self.assertEqual(kwargs["scale"], configuration.map_scale)
            self.assertFalse(kwargs["include_contestant_declarations"])
        self.assertEqual([call[2]["title_label"] for call in calls], ["Speed: 80 kt", "Speed: 100 kt"])
        # One page each, with the flight order's map footer
        self.assertEqual(compiled[0].count("#image("), 2 + 1, "two maps and the footer's logo")
        self.assertEqual(compiled[0].count("#pagebreak()"), 1)

    def test_a_lower_zoom_level_is_told(self):
        def plot(task, size, zoom_level, **kwargs):
            return png(), zoom_level - 1

        with (
            patch.object(generate_flight_orders, "plot_route_within_memory_limit", side_effect=plot),
            patch.object(generate_flight_orders, "_compile_typst", return_value=b"%PDF"),
        ):
            _, warning = generate_speed_maps_pdf(self.task, [80, 100], 0, 0)
        self.assertIn("zoom level", warning)


class TaskImagesPdfTest(TestCase):
    def setUp(self):
        for target in ("display.models.contestant.get_traccar_instance", "display.signals.get_traccar_instance"):
            patcher = patch(target, return_value=TraccarMock)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.task = make_task("Images day")

    def generate(self, turning_points, photos, route_photos=True, unknown_legs=None):
        """The document's source; ``unknown_legs`` are the cells of an unknown legs task's pictures (None: not such a task)."""
        compiled = []
        waypoints = [SimpleNamespace(type=UNKNOWN_LEG, name="UL")] if unknown_legs is not None else None
        with (
            patch.object(generate_flight_orders, "_unknown_leg_gallery_cells", return_value=unknown_legs or []),
            patch.object(
                generate_flight_orders,
                "get_flight_order_visual_waypoints",
                side_effect=lambda *args, **kwargs: (
                    waypoints
                    if waypoints is not None
                    else generate_flight_orders.get_effective_route_waypoints(self.task)
                ),
            ),
            patch.object(generate_flight_orders, "_turning_point_gallery_cells", return_value=turning_points),
            patch.object(generate_flight_orders, "_photo_gallery_cells", return_value=photos),
            patch.object(generate_flight_orders, "_route_photos", return_value=[MagicMock()] if route_photos else []),
            patch.object(
                generate_flight_orders,
                "_compile_typst",
                side_effect=lambda source: compiled.append(source) or b"%PDF-images",
            ),
        ):
            pdf = generate_task_images_pdf(self.task)
        return pdf, compiled[0]

    def test_the_turning_points_and_the_photos_are_pages_of_their_own_named_for_the_task(self):
        pdf, source = self.generate(
            [("/tmp/a.png", "SP"), ("/tmp/b.png", "TP1")], [("/tmp/c.png", "1"), ("/tmp/d.png", "2")]
        )
        self.assertEqual(pdf, b"%PDF-images")
        self.assertIn("Images day: Turning point and time gate images 1/1", source)
        self.assertIn("Images day: Photos 1/1", source)
        # The photos are numbered, never named
        self.assertIn('caption: "1"', source)
        # The first page is the document's first: no empty page before it
        self.assertNotRegex(source, r"#set text\([^\n]*\)\s*#pagebreak\(\)")
        self.assertEqual(source.count("#pagebreak()"), 1, "between the turning points and the photos")

    def test_the_unknown_legs_pictures_come_between_the_turning_points_and_the_photos(self):
        _, source = self.generate(
            [("/tmp/a.png", "SP")], [("/tmp/c.png", "1")], unknown_legs=[("/tmp/u1.png", None), ("/tmp/u2.png", None)]
        )
        order = [
            source.index("Turning point and time gate images"),
            source.index("Images day: Unknown legs images 1/1"),
            source.index("Images day: Photos"),
        ]
        self.assertEqual(order, sorted(order))
        self.assertEqual(source.count("#pagebreak()"), 2)
        # The pictures of unknown legs carry no caption: a name could give the route away
        self.assertIn('#image("/tmp/u1.png"', source)

    def test_a_task_without_unknown_legs_has_no_such_pages(self):
        _, source = self.generate([("/tmp/a.png", "SP")], [], route_photos=False)
        self.assertNotIn("Unknown legs", source)

    def test_an_unknown_legs_task_with_nothing_else_still_gets_a_document(self):
        pdf, source = self.generate([], [], route_photos=False, unknown_legs=[("/tmp/u1.png", None)])
        self.assertEqual(pdf, b"%PDF-images")
        self.assertIn("Unknown legs images", source)

    def test_a_task_without_photos_gets_only_its_turning_points(self):
        _, source = self.generate([("/tmp/a.png", "SP")], [], route_photos=False)
        self.assertIn("Turning point and time gate images", source)
        self.assertNotIn("Photos", source)

    def test_a_task_with_nothing_to_put_in_it_says_so(self):
        with self.assertRaisesMessage(ValueError, "no turning point images, unknown leg images or observation photos"):
            self.generate([], [], route_photos=False)
