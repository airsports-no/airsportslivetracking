import datetime
from unittest.mock import patch

from django.test import TestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Contest, EditableRoute, NavigationTask, Photo, Route
from display.services.photo_management import create_decoy_photo, delete_decoy_photo


class TestDecoyPhotos(TestCase):
    def setUp(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        self.contest = Contest.objects.create(
            name="Decoy photo contest",
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
            time_zone="Europe/Oslo",
        )
        self.route = Route.objects.create(name="Decoy photo route")
        self.navigation_task = NavigationTask.objects.create(
            name="Decoy photo task",
            route=self.route,
            contest=self.contest,
            original_scorecard=get_default_scorecard(),
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
            task_subtype="unknown_legs",
        )
        self.editable_route = EditableRoute.objects.create(
            name="Decoy photo primitives",
            route={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"featureType": "route_path"}, "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1]]}},
                    {"type": "Feature", "properties": {"id": "wp-sp", "name": "SP", "pointType": "sp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 0}, "geometry": {"type": "Point", "coordinates": [11.0, 60.0]}},
                    {"type": "Feature", "properties": {"id": "wp-ul", "name": "TRG1", "pointType": "ul", "featureType": "route_waypoint", "width": 1852, "isTiming": False, "isPassing": True, "sequence": 1}, "geometry": {"type": "Point", "coordinates": [11.05, 60.05]}},
                    {"type": "Feature", "properties": {"id": "wp-fp", "name": "FP", "pointType": "fp", "featureType": "route_waypoint", "width": 1852, "isTiming": True, "isPassing": True, "sequence": 1}, "geometry": {"type": "Point", "coordinates": [11.1, 60.1]}},
                ],
            },
        )
        self.navigation_task.editable_route = self.editable_route
        self.navigation_task.save(update_fields=["editable_route"])

    def test_decoy_photo_leg_is_always_none(self):
        photo = Photo.objects.create(name="DECOY-1", route=self.route, latitude=60.05, longitude=11.05, is_decoy=True)
        self.assertIsNone(photo.leg)

    def test_create_decoy_photo_rejects_name_collision_with_real_feature(self):
        with self.assertRaises(ValueError):
            create_decoy_photo(self.navigation_task, name="TRG1", latitude=60.02, longitude=11.02)

    def test_create_decoy_photo_rejects_duplicate_decoy_name(self):
        with patch.object(Photo, "generate_image"):
            create_decoy_photo(self.navigation_task, name="DECOY-1", latitude=60.02, longitude=11.02)
        with self.assertRaises(ValueError), patch.object(Photo, "generate_image"):
            create_decoy_photo(self.navigation_task, name="DECOY-1", latitude=60.03, longitude=11.03)

    def test_create_decoy_photo_sets_expected_fields(self):
        with patch.object(Photo, "generate_image") as mock_generate:
            photo = create_decoy_photo(self.navigation_task, name="DECOY-1", latitude=60.02, longitude=11.02, decoy_course=275)
        mock_generate.assert_called_once_with(force=True)
        self.assertTrue(photo.is_decoy)
        self.assertEqual(photo.decoy_course, 275)
        self.assertEqual(photo.route_id, self.route.id)

    def test_delete_decoy_photo_removes_row(self):
        with patch.object(Photo, "generate_image"):
            photo = create_decoy_photo(self.navigation_task, name="DECOY-1", latitude=60.02, longitude=11.02)
        photo_id = photo.id
        delete_decoy_photo(photo)
        self.assertFalse(Photo.objects.filter(id=photo_id).exists())

    def test_delete_decoy_photo_rejects_non_decoy(self):
        photo = Photo.objects.create(name="SP", route=self.route, latitude=60.0, longitude=11.0, is_decoy=False)
        with self.assertRaises(ValueError):
            delete_decoy_photo(photo)
        self.assertTrue(Photo.objects.filter(id=photo.id).exists())


class TestDecoyPhotoFlightOrderInclusion(TestCase):
    def setUp(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        self.contest = Contest.objects.create(
            name="Decoy flight order contest",
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
            time_zone="Europe/Oslo",
        )
        self.route = Route.objects.create(name="Decoy flight order route")
        self.navigation_task = NavigationTask.objects.create(
            name="Decoy flight order task",
            route=self.route,
            contest=self.contest,
            original_scorecard=get_default_scorecard(),
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
            task_subtype="unknown_legs",
        )

    def test_build_decoy_photo_waypoints_uses_declared_course(self):
        from display.flight_order_and_maps.generate_flight_orders import _build_decoy_photo_waypoints

        Photo.objects.create(name="DECOY-A", route=self.route, latitude=60.2, longitude=11.2, is_decoy=True, decoy_course=90)
        Photo.objects.create(name="DECOY-B", route=self.route, latitude=60.3, longitude=11.3, is_decoy=True, decoy_course=None)
        # A real (non-decoy) photo must not be picked up here.
        Photo.objects.create(name="REAL", route=self.route, latitude=60.1, longitude=11.1, is_decoy=False)

        decoy_waypoints = _build_decoy_photo_waypoints(self.navigation_task)

        by_name = {wp.name: wp for wp in decoy_waypoints}
        self.assertEqual(set(by_name.keys()), {"DECOY-A", "DECOY-B"})
        self.assertEqual(by_name["DECOY-A"].bearing_next, 90)
        self.assertEqual(by_name["DECOY-A"].bearing_from_previous, 90)
        self.assertEqual(by_name["DECOY-B"].bearing_next, 0)
        self.assertEqual(by_name["DECOY-A"].latitude, 60.2)
        self.assertEqual(by_name["DECOY-A"].longitude, 11.2)

    def test_insert_unknown_leg_images_latex_shuffles_in_decoys(self):
        from display.flight_order_and_maps.generate_flight_orders import insert_unknown_leg_images_latex
        from types import SimpleNamespace

        Photo.objects.create(name="DECOY-A", route=self.route, latitude=60.2, longitude=11.2, is_decoy=True, decoy_course=90)

        contestant = SimpleNamespace(navigation_task=self.navigation_task, contestanttaskconfiguration=None)

        with patch("display.flight_order_and_maps.generate_flight_orders.render_turning_point_images") as mock_render:
            insert_unknown_leg_images_latex(contestant, document=None, flight_order_configuration=None, waypoints=[])

        mock_render.assert_called_once()
        rendered_waypoints = mock_render.call_args.args[0]
        self.assertIn("DECOY-A", [wp.name for wp in rendered_waypoints])
