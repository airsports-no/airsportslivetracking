import datetime
import io
import os
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.test.client import BOUNDARY, MULTIPART_CONTENT, encode_multipart
from guardian.shortcuts import assign_perm
from PIL import Image

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Contest, EditableRoute, NavigationTask, Photo, Route
from display.services.photo_management import get_navigation_task_photo_targets
from display.utilities.route_building_utilities import build_waypoint
from display.utilities.gate_definitions import UNKNOWN_LEG

MEDIA_ROOT = tempfile.mkdtemp()


def _png(width=400, height=300) -> bytes:
    data = io.BytesIO()
    Image.new("RGB", (width, height), (40, 120, 40)).save(data, "PNG")
    return data.getvalue()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
@patch.object(Photo, "generate_image")
class TestUnknownLegPhotos(TestCase):
    """The unknown-leg waypoints of a 2.A5 task are photo targets: the organisers can replace their generated
    satellite pictures with real aerial photos, which the flight order then prints."""

    def setUp(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        self.manager = get_user_model().objects.create(email="manager@example.com")
        self.contest = Contest.objects.create(
            name="Unknown leg photo contest",
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
            time_zone="Europe/Oslo",
            is_public=True,
            created_by=self.manager,
        )
        assign_perm("view_contest", self.manager, self.contest)
        assign_perm("change_contest", self.manager, self.contest)
        self.route = Route.objects.create(name="Unknown leg photo route")
        self.navigation_task = NavigationTask.objects.create(
            name="Unknown leg photo task",
            route=self.route,
            contest=self.contest,
            original_scorecard=get_default_scorecard(),
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
            task_subtype="unknown_legs",
            is_public=True,
        )
        self.navigation_task.editable_route = EditableRoute.objects.create(
            name="Unknown leg photo primitives",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"featureType": "route_path"}, "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]}},
                    {"type": "Feature", "properties": {"id": "wp-sp", "name": "SP", "pointType": "sp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 0}, "geometry": {"type": "Point", "coordinates": [11.0, 60.0]}},
                    {"type": "Feature", "properties": {"id": "wp-ul", "name": "Unknown leg 1", "pointType": "ul", "featureType": "route_waypoint", "width": 1852, "isTiming": False, "isPassing": True, "sequence": 1}, "geometry": {"type": "Point", "coordinates": [11.05, 60.05]}},
                    {"type": "Feature", "properties": {"id": "wp-fp", "name": "FP", "pointType": "fp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 2}, "geometry": {"type": "Point", "coordinates": [11.1, 60.1]}},
                    {"type": "Feature", "properties": {"featureType": "observation_photo", "name": "Photo A"}, "geometry": {"type": "Point", "coordinates": [11.02, 60.02]}},
                ],
            },
        )
        self.navigation_task.save(update_fields=["editable_route"])
        self.photos_url = f"/api/v1/contests/{self.contest.pk}/navigationtasks/{self.navigation_task.pk}/photos/"

    def test_the_unknown_leg_waypoints_are_photo_targets(self, _generate_image):
        targets = {target["name"]: target["target_kind"] for target in get_navigation_task_photo_targets(self.navigation_task)}
        self.assertEqual(
            targets,
            {"SP": "route_waypoint", "FP": "route_waypoint", "Unknown leg 1": "unknown_leg", "Photo A": "observation"},
        )

    def test_hidden_gates_and_the_points_of_a_curve_are_not_photo_targets(self, _generate_image):
        self.navigation_task.editable_route.route["features"].append(
            {"type": "Feature", "properties": {"id": "wp-secret", "name": "Secret 1", "pointType": "secret", "featureType": "route_waypoint", "width": 1852, "isTiming": False, "isPassing": True, "sequence": 3}, "geometry": {"type": "Point", "coordinates": [11.07, 60.07]}}
        )
        self.navigation_task.editable_route.save()
        curve_point = build_waypoint("Curve 1.1", 60.01, 11.01, "secret", 1, False, False)
        with patch.object(type(self.route), "waypoints", [curve_point], create=True):
            names = {target["name"] for target in get_navigation_task_photo_targets(self.navigation_task)}
        self.assertNotIn("Secret 1", names)
        self.assertNotIn("Curve 1.1", names)

    def test_the_turning_point_pages_use_an_uploaded_waypoint_picture(self, _generate_image):
        from display.flight_order_and_maps.generate_flight_orders import _turning_point_gallery_cells

        Photo.objects.create(
            name="SP",
            route=self.route,
            latitude=60.0,
            longitude=11.0,
            file=SimpleUploadedFile("sp.png", _png(), content_type="image/png"),
            uploaded=True,
        )
        # A generated picture that was never replaced is generated again for the flight order, with the route on it
        Photo.objects.create(
            name="FP",
            route=self.route,
            latitude=60.1,
            longitude=11.1,
            file=SimpleUploadedFile("fp.png", _png(), content_type="image/png"),
        )
        waypoints = [
            build_waypoint("SP", 60.0, 11.0, "sp", 1, True, True),
            build_waypoint("Secret 1", 60.05, 11.05, "secret", 1, False, True),
            build_waypoint("FP", 60.1, 11.1, "fp", 1, True, True),
        ]
        contestant = SimpleNamespace(navigation_task=self.navigation_task, contestanttaskconfiguration=None)

        with patch("display.flight_order_and_maps.generate_flight_orders.get_turning_point_image") as mock_generate:
            mock_generate.side_effect = lambda waypoints, index, *a, **k: SimpleNamespace(name=f"/tmp/{waypoints[index].name}.png")
            cells = _turning_point_gallery_cells(contestant, self.navigation_task.flightorderconfiguration, waypoints)

        self.assertEqual([caption for _, caption in cells], ["SP", "FP"])
        self.assertEqual([call.args[1] for call in mock_generate.call_args_list], [2], "only FP is generated")
        self.assertEqual(Image.open(cells[0][0]).size, (400, 300))
        os.remove(cells[0][0])

    def test_decoys_are_not_on_the_photos_pages(self, _generate_image):
        from display.flight_order_and_maps.generate_flight_orders import _route_photos

        Photo.objects.create(name="Photo A", route=self.route, latitude=60.02, longitude=11.02)
        Photo.objects.create(name="Decoy 1", route=self.route, latitude=60.03, longitude=11.03, is_decoy=True)
        contestant = SimpleNamespace(navigation_task=self.navigation_task)
        self.assertEqual([photo.name for photo in _route_photos(contestant)], ["Photo A"])

        # Without editable-route features as well
        self.navigation_task.editable_route = None
        self.assertEqual([photo.name for photo in _route_photos(contestant)], ["Photo A"])

    def test_only_the_organisers_see_the_unknown_leg_photos(self, _generate_image):
        response = self.client.get(self.photos_url)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertNotIn("Unknown leg 1", {item["name"] for item in response.json()}, "they give the unknown legs away")

        self.client.force_login(self.manager)
        response = self.client.get(self.photos_url)
        self.assertEqual(response.status_code, 200, response.content)
        by_name = {item["name"]: item for item in response.json()}
        self.assertEqual(by_name["Unknown leg 1"]["target_kind"], "unknown_leg")
        self.assertFalse(by_name["Unknown leg 1"]["uploaded"])

    def test_an_uploaded_picture_is_marked_until_it_is_reverted(self, _generate_image):
        self.client.force_login(self.manager)
        self.client.get(self.photos_url)
        photo = Photo.objects.get(route=self.route, name="Unknown leg 1")

        # As the photo management page sends it: multipart, with only the file
        response = self.client.patch(
            f"/api/v1/photos/{photo.pk}/",
            encode_multipart(BOUNDARY, {"file": SimpleUploadedFile("aerial.png", _png(), content_type="image/png")}),
            content_type=MULTIPART_CONTENT,
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["uploaded"])

        response = self.client.post(f"/api/v1/photos/{photo.pk}/revert/")
        self.assertEqual(response.status_code, 200, response.content)
        photo.refresh_from_db()
        self.assertFalse(photo.uploaded)

    def test_uploaded_cannot_be_set_by_hand(self, _generate_image):
        self.client.force_login(self.manager)
        self.client.get(self.photos_url)
        photo = Photo.objects.get(route=self.route, name="Unknown leg 1")
        response = self.client.patch(f"/api/v1/photos/{photo.pk}/", {"uploaded": True}, content_type="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        photo.refresh_from_db()
        self.assertFalse(photo.uploaded)

    def test_the_flight_order_prints_the_uploaded_picture_with_the_course(self, _generate_image):
        from display.flight_order_and_maps.generate_flight_orders import _unknown_leg_gallery_cells

        Photo.objects.create(
            name="Unknown leg 1",
            route=self.route,
            latitude=60.05,
            longitude=11.05,
            file=SimpleUploadedFile("aerial.png", _png(), content_type="image/png"),
            uploaded=True,
        )
        unknown_leg = build_waypoint("Unknown leg 1", 60.05, 11.05, UNKNOWN_LEG, 1, False, True)
        unknown_leg.bearing_next = 47
        generated = build_waypoint("Unknown leg 2", 60.07, 11.07, UNKNOWN_LEG, 1, False, True)
        generated.bearing_next = 90
        contestant = SimpleNamespace(navigation_task=self.navigation_task, contestanttaskconfiguration=None)

        with patch("display.flight_order_and_maps.generate_flight_orders.get_turning_point_image") as mock_generate:
            mock_generate.side_effect = lambda waypoints, index, *a, **k: SimpleNamespace(
                name=f"/tmp/{waypoints[index].name}.png"
            )
            cells = _unknown_leg_gallery_cells(
                contestant, self.navigation_task.flightorderconfiguration, [unknown_leg, generated]
            )

        generated_names = [call.args[0][call.args[1]].name for call in mock_generate.call_args_list]
        self.assertEqual(generated_names, ["Unknown leg 2"], "only the point without an uploaded picture is generated")
        uploaded_files = [path for path, _ in cells if path != "/tmp/Unknown leg 2.png"]
        self.assertEqual(len(uploaded_files), 1)
        printed = Image.open(uploaded_files[0])
        self.assertEqual(printed.size, (400, 300))
        # The course is printed in red at the top left, over the green picture
        corner = [printed.getpixel((x, y)) for x in range(0, 60) for y in range(0, 60)]
        self.assertTrue(any(red > 200 and green < 80 for red, green, _ in corner))
        os.remove(uploaded_files[0])
