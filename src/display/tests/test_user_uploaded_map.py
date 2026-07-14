import os
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models.fields.files import FieldFile
from django.test import TestCase, override_settings
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITransactionTestCase

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import Contest, EditableRoute, Scorecard
from display.models.user_uploaded_map import UserUploadedMap
from display.tasks import process_user_uploaded_map


def _make_instance(user, default_zoom=12) -> UserUploadedMap:
    return UserUploadedMap.objects.create(
        user=user,
        name="test-map",
        map_file=SimpleUploadedFile("test.mbtiles", b"fake mbtiles bytes"),
        default_zoom_level=default_zoom,
    )


class ProcessUserUploadedMapTaskTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="taskuser@example.com")

    def test_missing_map_does_not_raise(self):
        process_user_uploaded_map(999999)

    @override_settings(MBTILES_PUBLISH_ROOT="/tilesets-test")
    def test_successful_processing_marks_ready_and_stores_publish_metadata(self):
        instance = _make_instance(self.user, default_zoom=12)

        fake_png = BytesIO(b"\x89PNG\r\n\x1a\nfake")

        with patch.object(UserUploadedMap, "create_thumbnail", return_value=(fake_png, 10, 14)), \
             patch("display.tasks.publish_user_uploaded_map", return_value=("user-uploaded-map-1", "user-uploaded/user-uploaded-map-1.mbtiles")) as publish_mock, \
             patch("display.tasks.request_mbtiles_reload") as reload_mock:
            process_user_uploaded_map(instance.pk)

        instance.refresh_from_db()
        self.assertEqual(instance.processing_status, UserUploadedMap.PROCESSING_READY)
        self.assertEqual(instance.processing_error, "")
        self.assertEqual(instance.minimum_zoom_level, 10)
        self.assertEqual(instance.maximum_zoom_level, 14)
        self.assertEqual(instance.default_zoom_level, 12)
        self.assertEqual(instance.published_service_key, "user-uploaded-map-1")
        self.assertEqual(instance.published_relative_path, "user-uploaded/user-uploaded-map-1.mbtiles")
        self.assertIsNotNone(instance.published_at)
        self.assertTrue(instance.thumbnail)
        publish_mock.assert_called_once()
        reload_mock.assert_called_once()

    @override_settings(MBTILES_PUBLISH_ROOT="/tilesets-test")
    def test_processing_stores_bounds_when_available(self):
        instance = _make_instance(self.user, default_zoom=12)
        fake_png = BytesIO(b"\x89PNG\r\n\x1a\nfake")

        with patch.object(UserUploadedMap, "create_thumbnail", return_value=(fake_png, 10, 14)), \
             patch.object(UserUploadedMap, "get_bounds", return_value=(10.0, 59.0, 11.0, 60.0)), \
             patch("display.tasks.publish_user_uploaded_map", return_value=("user-uploaded-map-1", "user-uploaded/user-uploaded-map-1.mbtiles")), \
             patch("display.tasks.request_mbtiles_reload"):
            process_user_uploaded_map(instance.pk)

        instance.refresh_from_db()
        self.assertEqual(instance.minimum_longitude, 10.0)
        self.assertEqual(instance.minimum_latitude, 59.0)
        self.assertEqual(instance.maximum_longitude, 11.0)
        self.assertEqual(instance.maximum_latitude, 60.0)
        self.assertEqual(instance.bounds, [10.0, 59.0, 11.0, 60.0])

    @override_settings(MBTILES_PUBLISH_ROOT="/tilesets-test")
    def test_processing_stores_uploaded_bounds_in_south_then_north_order(self):
        instance = _make_instance(self.user, default_zoom=12)
        fake_png = BytesIO(b"\x89PNG\r\n\x1a\nfake")

        with patch.object(UserUploadedMap, "create_thumbnail", return_value=(fake_png, 12, 15)), \
             patch.object(UserUploadedMap, "get_bounds", return_value=(-0.9474, 38.3457, -0.0357, 38.6619)), \
             patch("display.tasks.publish_user_uploaded_map", return_value=("user-uploaded-map-1", "user-uploaded/user-uploaded-map-1.mbtiles")), \
             patch("display.tasks.request_mbtiles_reload"):
            process_user_uploaded_map(instance.pk)

        instance.refresh_from_db()
        self.assertEqual(instance.minimum_longitude, -0.9474)
        self.assertEqual(instance.minimum_latitude, 38.3457)
        self.assertEqual(instance.maximum_longitude, -0.0357)
        self.assertEqual(instance.maximum_latitude, 38.6619)

    @override_settings(MBTILES_PUBLISH_ROOT="/tilesets-test")
    def test_thumbnail_save_failure_does_not_block_publish(self):
        instance = _make_instance(self.user, default_zoom=12)
        fake_png = BytesIO(b"\x89PNG\r\n\x1a\nfake")

        with patch.object(UserUploadedMap, "create_thumbnail", return_value=(fake_png, 10, 14)), \
             patch("display.tasks.publish_user_uploaded_map", return_value=("user-uploaded-map-1", "user-uploaded/user-uploaded-map-1.mbtiles")) as publish_mock, \
             patch("display.tasks.request_mbtiles_reload") as reload_mock, \
             patch.object(FieldFile, "save", side_effect=PermissionError("no thumbnail write permission")):
            process_user_uploaded_map(instance.pk)

        instance.refresh_from_db()
        self.assertEqual(instance.processing_status, UserUploadedMap.PROCESSING_READY)
        self.assertEqual(instance.processing_error, "")
        self.assertEqual(instance.minimum_zoom_level, 10)
        self.assertEqual(instance.maximum_zoom_level, 14)
        self.assertEqual(instance.published_service_key, "user-uploaded-map-1")
        self.assertEqual(instance.published_relative_path, "user-uploaded/user-uploaded-map-1.mbtiles")
        self.assertIsNotNone(instance.published_at)
        publish_mock.assert_called_once()
        reload_mock.assert_called_once()

    def test_default_zoom_is_clamped_when_outside_range(self):
        instance = _make_instance(self.user, default_zoom=18)
        fake_png = BytesIO(b"\x89PNGfake")

        with patch.object(UserUploadedMap, "create_thumbnail", return_value=(fake_png, 10, 14)), \
             patch("display.tasks.publish_user_uploaded_map", return_value=("user-uploaded-map-1", "user-uploaded/user-uploaded-map-1.mbtiles")), \
             patch("display.tasks.request_mbtiles_reload"):
            process_user_uploaded_map(instance.pk)

        instance.refresh_from_db()
        self.assertEqual(instance.processing_status, UserUploadedMap.PROCESSING_READY)
        self.assertEqual(instance.default_zoom_level, 14)

    def test_failure_marks_failed_with_error(self):
        instance = _make_instance(self.user)

        with patch.object(UserUploadedMap, "create_thumbnail", side_effect=RuntimeError("corrupt mbtiles")):
            process_user_uploaded_map(instance.pk)

        instance.refresh_from_db()
        self.assertEqual(instance.processing_status, UserUploadedMap.PROCESSING_FAILED)
        self.assertIn("corrupt mbtiles", instance.processing_error)

    def test_default_service_key_and_relative_path(self):
        instance = _make_instance(self.user)
        self.assertEqual(instance.default_service_key, f"user-uploaded-map-{instance.pk}")
        self.assertEqual(
            instance.default_published_relative_path,
            f"user-uploaded/user-uploaded-map-{instance.pk}.mbtiles",
        )


class RequestMbtilesReloadTests(TestCase):
    @override_settings(MBTILES_RELOAD_METHOD="noop")
    @patch("display.flight_order_and_maps.user_uploaded_mbtiles_publish.requests.post")
    def test_request_mbtiles_reload_is_noop_when_disabled(self, post_mock):
        from display.flight_order_and_maps.user_uploaded_mbtiles_publish import request_mbtiles_reload

        request_mbtiles_reload()

        post_mock.assert_not_called()

    @override_settings(
        MBTILES_RELOAD_METHOD="kubernetes",
        MBTILES_RELOAD_NAMESPACE="default",
        MBTILES_RELOAD_POD_LABEL_SELECTOR="service=mbtiles",
    )
    @patch("display.flight_order_and_maps.user_uploaded_mbtiles_publish.stream")
    @patch("display.flight_order_and_maps.user_uploaded_mbtiles_publish.client.CoreV1Api")
    @patch("display.flight_order_and_maps.user_uploaded_mbtiles_publish.config.load_incluster_config")
    def test_request_mbtiles_reload_uses_kubernetes_exec(self, load_config_mock, core_api_cls, stream_mock):
        from display.flight_order_and_maps.user_uploaded_mbtiles_publish import request_mbtiles_reload

        pod = MagicMock()
        pod.metadata.name = "mbtiles-pod-1"
        core_api = core_api_cls.return_value
        core_api.list_namespaced_pod.return_value.items = [pod]

        request_mbtiles_reload()

        load_config_mock.assert_called_once()
        core_api.list_namespaced_pod.assert_called_once_with(namespace="default", label_selector="service=mbtiles")
        stream_mock.assert_called_once()
        _, kwargs = stream_mock.call_args
        self.assertEqual(kwargs["name"], "mbtiles-pod-1")
        self.assertEqual(kwargs["namespace"], "default")
        self.assertEqual(kwargs["command"], ["/bin/sh", "-c", "kill -HUP 1"])

    @override_settings(
        MBTILES_RELOAD_METHOD="local",
        MBTILES_RELOAD_LOCAL_URL="http://mbtiles:8000/services/",
    )
    @patch("display.flight_order_and_maps.user_uploaded_mbtiles_publish.os.kill")
    def test_request_mbtiles_reload_sends_local_hup_signal(self, kill_mock):
        from display.flight_order_and_maps.user_uploaded_mbtiles_publish import request_mbtiles_reload

        request_mbtiles_reload()

        kill_mock.assert_called_once()

    @override_settings(
        MBTILES_RELOAD_METHOD="local",
        MBTILES_RELOAD_LOCAL_URL="http://mbtiles:8000/services/",
    )
    @patch("display.flight_order_and_maps.user_uploaded_mbtiles_publish.os.kill", side_effect=PermissionError("signal denied"))
    def test_request_mbtiles_reload_raises_when_local_hup_signal_fails(self, kill_mock):
        from display.flight_order_and_maps.user_uploaded_mbtiles_publish import request_mbtiles_reload

        with self.assertRaises(PermissionError):
            request_mbtiles_reload()

        kill_mock.assert_called_once()


class UnifiedMapSourcesApiTests(APITransactionTestCase):
    def setUp(self):
        create_scorecards()
        self.client = self.client_class()
        self.user = get_user_model().objects.create(email="mapsources@example.com")
        self.client.force_authenticate(user=self.user)
        assign_perm("display.add_editableroute", self.user)
        self.contest = Contest.objects.create(
            name="Contest",
            start_time="2024-01-01T10:00:00Z",
            finish_time="2024-01-01T12:00:00Z",
        )
        scorecard = Scorecard.get_originals().first()
        self.route = EditableRoute.objects.create(
            name="Route",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {
                            "name": "Test route",
                        },
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [[10.0, 60.0], [10.1, 60.1]],
                        },
                    }
                ],
            },
            settings={},
        )
        assign_perm("display.view_contest", self.user, self.contest)
        assign_perm("display.view_editableroute", self.user, self.route)

    @patch("display.viewsets.get_builtin_map_source_definitions")
    @override_settings(MBTILES_PUBLIC_URL="http://localhost:8001/")
    def test_route_editor_map_sources_include_builtin_and_accessible_uploaded_maps(
        self, mock_get_builtin_map_source_definitions
    ):
        mock_get_builtin_map_source_definitions.return_value = [
            {
                "key": "Norway250k",
                "label": "Norway 250k",
                "provider": "mbtiles",
                "type": "mbtiles",
                "tile_url": "https://mbtiles.airsports.no/services/Norway250k/tiles/{z}/{x}/{y}.png",
                "attribution": "",
                "min_zoom": 8,
                "max_zoom": 14,
                "default_zoom": 12,
                "is_overlay": True,
                "bounds": [10.0, 59.0, 11.0, 60.0],
            },
            {
                "key": "osm",
                "label": "OSM",
                "provider": "osm",
                "type": "raster_xyz",
                "tile_url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
                "attribution": "© OpenStreetMap contributors",
                "min_zoom": 0,
                "max_zoom": 19,
                "default_zoom": 12,
                "is_overlay": False,
                "bounds": None,
            },
            {
                "key": "fc",
                "label": "Flight Contest",
                "provider": "fc",
                "type": "raster_xyz",
                "tile_url": "https://flightcontest.de/route/maps/{z}/{x}/{y}.png",
                "attribution": "FlightContest",
                "min_zoom": 0,
                "max_zoom": 18,
                "default_zoom": 12,
                "is_overlay": False,
                "bounds": None,
            },
            {
                "key": "mto",
                "label": "MapTiler Outdoor",
                "provider": "mto",
                "type": "raster_xyz",
                "tile_url": "https://api.maptiler.com/maps/outdoor/{z}/{x}/{y}.png?key=YxHsFU6aEqsEULL34uJT",
                "attribution": "maptiler.com",
                "min_zoom": 0,
                "max_zoom": 18,
                "default_zoom": 12,
                "is_overlay": False,
                "bounds": None,
            },
            {
                "key": "cyclosm",
                "label": "CycleOSM",
                "provider": "cyclosm",
                "type": "raster_xyz",
                "tile_url": "https://a.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png",
                "attribution": "openstreetmap.org CycleOSM",
                "min_zoom": 0,
                "max_zoom": 20,
                "default_zoom": 12,
                "is_overlay": False,
                "bounds": None,
            },
            {
                "key": "openaip",
                "label": "OpenAIP",
                "provider": "openaip",
                "type": "raster_xyz",
                "tile_url": "https://api.tiles.openaip.net/api/data/openaip/{z}/{x}/{y}.png?apiKey=3d5d3f82528731731362a23f445951d8",
                "attribution": "OpenAIP Data",
                "min_zoom": 4,
                "max_zoom": 14,
                "default_zoom": 10,
                "is_overlay": True,
            },
        ]

        allowed = _make_instance(self.user)
        allowed.name = "Pilot uploaded map"
        allowed.processing_status = UserUploadedMap.PROCESSING_READY
        allowed.minimum_zoom_level = 10
        allowed.maximum_zoom_level = 13
        allowed.default_zoom_level = 11
        allowed.attribution = "Uploaded attribution"
        allowed.published_service_key = f"user-uploaded-map-{allowed.pk}"
        allowed.published_relative_path = f"user-uploaded/user-uploaded-map-{allowed.pk}.mbtiles"
        allowed.minimum_longitude = 10.0
        allowed.minimum_latitude = 59.0
        allowed.maximum_longitude = 11.0
        allowed.maximum_latitude = 60.0
        allowed.save()
        assign_perm("display.view_useruploadedmap", self.user, allowed)

        hidden = UserUploadedMap.objects.create(
            user=self.user,
            name="Hidden map",
            map_file=SimpleUploadedFile("hidden.mbtiles", b"hidden bytes"),
            processing_status=UserUploadedMap.PROCESSING_FAILED,
        )
        assign_perm("display.view_useruploadedmap", self.user, hidden)

        response = self.client.get(
            reverse("editableroutes-map-sources", kwargs={"pk": self.route.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        payload = response.json()

        builtin = next(item for item in payload if item["key"] == "Norway250k")
        self.assertEqual(builtin["key"], "Norway250k")
        self.assertEqual(builtin["label"], "Norway 250k")
        self.assertEqual(builtin["tile_url"], "https://mbtiles.airsports.no/services/Norway250k/tiles/{z}/{x}/{y}.png")
        self.assertEqual(builtin["min_zoom"], 8)
        self.assertEqual(builtin["max_zoom"], 14)
        self.assertTrue(builtin["is_overlay"])
        self.assertEqual(builtin["bounds"], [10.0, 59.0, 11.0, 60.0])

        osm = next(item for item in payload if item["key"] == "osm")
        self.assertEqual(osm["label"], "OSM")
        self.assertEqual(osm["origin"], "builtin")
        self.assertEqual(osm["type"], "raster_xyz")
        self.assertTrue(osm["tile_url"].startswith("https://{s}.tile.openstreetmap.org/"))
        self.assertFalse(osm["is_overlay"])

        flight_contest = next(item for item in payload if item["key"] == "fc")
        self.assertEqual(flight_contest["label"], "Flight Contest")
        self.assertEqual(flight_contest["origin"], "builtin")
        self.assertEqual(flight_contest["type"], "raster_xyz")

        maptiler = next(item for item in payload if item["key"] == "mto")
        self.assertEqual(maptiler["label"], "MapTiler Outdoor")
        self.assertEqual(maptiler["origin"], "builtin")
        self.assertEqual(maptiler["type"], "raster_xyz")

        cyclosm = next(item for item in payload if item["key"] == "cyclosm")
        self.assertEqual(cyclosm["label"], "CycleOSM")
        self.assertEqual(cyclosm["origin"], "builtin")
        self.assertEqual(cyclosm["type"], "raster_xyz")

        openaip = next(item for item in payload if item["key"] == "openaip")
        self.assertEqual(openaip["label"], "OpenAIP")
        self.assertEqual(openaip["origin"], "builtin")
        self.assertEqual(openaip["type"], "raster_xyz")
        self.assertTrue(openaip["is_overlay"])
        self.assertIsNone(openaip["bounds"])

        uploaded = next(item for item in payload if item["origin"] == "user_upload")
        self.assertEqual(uploaded["key"], allowed.published_service_key)
        self.assertEqual(uploaded["label"], allowed.name)
        self.assertEqual(uploaded["min_zoom"], 10)
        self.assertEqual(uploaded["max_zoom"], 13)
        self.assertEqual(uploaded["default_zoom"], 11)
        self.assertEqual(uploaded["attribution"], "Uploaded attribution")
        self.assertEqual(uploaded["tile_url"], f"http://localhost:8001/services/user-uploaded/{allowed.published_service_key}/tiles/{{z}}/{{x}}/{{y}}.png")
        self.assertEqual(uploaded["bounds"], [10.0, 59.0, 11.0, 60.0])
        self.assertNotIn(hidden.published_service_key, [item["key"] for item in payload])

    @patch("display.viewsets.get_builtin_map_source_definitions")
    @override_settings(MBTILES_PUBLIC_URL="http://localhost:8001/")
    def test_global_route_editor_map_sources_available_without_route_id(
        self, mock_get_builtin_map_source_definitions
    ):
        mock_get_builtin_map_source_definitions.return_value = [
            {
                "key": "Norway250k",
                "label": "Norway 250k",
                "provider": "mbtiles",
                "type": "mbtiles",
                "tile_url": "https://mbtiles.airsports.no/services/Norway250k/tiles/{z}/{x}/{y}.png",
                "attribution": "",
                "min_zoom": 8,
                "max_zoom": 14,
                "default_zoom": 12,
                "is_overlay": True,
                "bounds": [10.0, 59.0, 11.0, 60.0],
            },
            {
                "key": "osm",
                "label": "OSM",
                "provider": "osm",
                "type": "raster_xyz",
                "tile_url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
                "attribution": "© OpenStreetMap contributors",
                "min_zoom": 0,
                "max_zoom": 19,
                "default_zoom": 12,
                "is_overlay": False,
                "bounds": None,
            },
        ]

        response = self.client.get(reverse("editableroutes-global-map-sources"))

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        payload = response.json()
        self.assertTrue(any(item["key"] == "osm" for item in payload))
        self.assertTrue(any(item["key"] == "Norway250k" and item["is_overlay"] for item in payload))


class UserUploadedMapLifecycleViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="lifecycletester@example.com")

    @patch("display.views.unpublish_user_uploaded_map")
    @patch("display.views.request_mbtiles_reload")
    def test_update_view_unpublishes_before_reprocessing(self, reload_mock, unpublish_mock):
        instance = _make_instance(self.user)
        instance.published_service_key = f"user-uploaded-map-{instance.pk}"
        instance.published_relative_path = f"user-uploaded/user-uploaded-map-{instance.pk}.mbtiles"
        instance.processing_status = UserUploadedMap.PROCESSING_READY
        instance.processing_error = "old error"
        instance.save()

        from display.views import UserUploadedMapUpdate

        view = UserUploadedMapUpdate()
        form = MagicMock()
        form.save.return_value = instance

        with patch.object(instance, "clear_local_file_path") as clear_local_mock, \
             patch("display.views.process_user_uploaded_map.delay") as delay_mock, \
             patch("display.views.transaction.on_commit", side_effect=lambda fn: fn()) as on_commit_mock, \
             patch.object(view, "get_success_url", return_value="/maps/"):
            response = view.form_valid(form)

        instance.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/maps/")
        self.assertEqual(instance.processing_status, UserUploadedMap.PROCESSING_PENDING)
        self.assertEqual(instance.processing_error, "")
        self.assertEqual(instance.published_service_key, "")
        self.assertEqual(instance.published_relative_path, "")
        self.assertIsNone(instance.published_at)
        unpublish_mock.assert_called_once_with(instance)
        reload_mock.assert_called_once()
        clear_local_mock.assert_called_once()
        on_commit_mock.assert_called_once()
        delay_mock.assert_called_once_with(instance.pk)

    @patch("display.views.unpublish_user_uploaded_map")
    @patch("display.views.request_mbtiles_reload")
    def test_delete_view_unpublishes_and_reloads(self, reload_mock, unpublish_mock):
        instance = _make_instance(self.user)
        instance.published_service_key = f"user-uploaded-map-{instance.pk}"
        instance.published_relative_path = f"user-uploaded/user-uploaded-map-{instance.pk}.mbtiles"
        instance.save()

        from display.views import UserUploadedMapDelete

        view = UserUploadedMapDelete()
        view.object = instance

        with patch.object(instance, "clear_local_file_path") as clear_local_mock:
            response = view.form_valid(form=MagicMock())

        self.assertEqual(response.status_code, 302)
        self.assertFalse(UserUploadedMap.objects.filter(pk=instance.pk).exists())
        unpublish_mock.assert_called_once_with(instance)
        reload_mock.assert_called_once()
        clear_local_mock.assert_called_once()


class UserUploadedMapListViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="listviewer@example.com")
        self.client.force_login(self.user)
        assign_perm("display.add_contest", self.user)

    def test_list_view_tolerates_missing_map_file_on_disk(self):
        uploaded_map = UserUploadedMap.objects.create(
            user=self.user,
            name="Missing file map",
            map_file=SimpleUploadedFile("missing.mbtiles", b"placeholder"),
            processing_status=UserUploadedMap.PROCESSING_READY,
        )
        assign_perm("display.view_useruploadedmap", self.user, uploaded_map)

        map_path = uploaded_map.map_file.path
        if os.path.exists(map_path):
            os.remove(map_path)

        response = self.client.get(reverse("useruploadedmap_list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertContains(response, "Missing file map")

    def test_list_view_shows_extent_when_bounds_are_available(self):
        uploaded_map = UserUploadedMap.objects.create(
            user=self.user,
            name="Extent map",
            map_file=SimpleUploadedFile("extent.mbtiles", b"placeholder"),
            processing_status=UserUploadedMap.PROCESSING_READY,
            minimum_longitude=-3.5266,
            minimum_latitude=40.6639,
            maximum_longitude=-2.5158,
            maximum_latitude=41.0047,
        )
        assign_perm("display.view_useruploadedmap", self.user, uploaded_map)

        response = self.client.get(reverse("useruploadedmap_list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertContains(response, "Extent")
        self.assertContains(response, "40.6639")
        self.assertContains(response, "41.0047")

    def test_update_view_tolerates_missing_map_file_on_disk(self):
        uploaded_map = UserUploadedMap.objects.create(
            user=self.user,
            name="Missing file map",
            map_file=SimpleUploadedFile("missing-update.mbtiles", b"placeholder"),
            processing_status=UserUploadedMap.PROCESSING_READY,
        )
        assign_perm("display.view_useruploadedmap", self.user, uploaded_map)
        assign_perm("display.change_useruploadedmap", self.user, uploaded_map)

        map_path = uploaded_map.map_file.path
        if os.path.exists(map_path):
            os.remove(map_path)

        response = self.client.get(reverse("useruploadedmap_change", kwargs={"pk": uploaded_map.pk}))

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertContains(response, "Upload User Map")

    def test_delete_view_tolerates_missing_map_file_on_disk(self):
        uploaded_map = UserUploadedMap.objects.create(
            user=self.user,
            name="Missing file map",
            map_file=SimpleUploadedFile("missing-delete.mbtiles", b"placeholder"),
            processing_status=UserUploadedMap.PROCESSING_READY,
        )
        assign_perm("display.view_useruploadedmap", self.user, uploaded_map)
        assign_perm("display.delete_useruploadedmap", self.user, uploaded_map)

        map_path = uploaded_map.map_file.path
        if os.path.exists(map_path):
            os.remove(map_path)

        response = self.client.get(reverse("useruploadedmap_delete", kwargs={"pk": uploaded_map.pk}))

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertContains(response, "Missing file map")


class UserUploadedMapCreateViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="createviewer@example.com")
        self.client.force_login(self.user)
        assign_perm("display.add_contest", self.user)

    @patch("display.views.process_user_uploaded_map.delay")
    @patch("display.views.transaction.on_commit", side_effect=lambda fn: fn())
    def test_create_view_redirects_and_creates_map(self, on_commit_mock, delay_mock):
        response = self.client.post(
            reverse("useruploadedmap_add"),
            {
                "name": "Created map",
                "default_zoom_level": 12,
                "attribution": "created attribution",
                "user": self.user.pk,
                "map_file": SimpleUploadedFile("created.mbtiles", b"placeholder"),
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("useruploadedmap_list"))
        created = UserUploadedMap.objects.get(name="Created map")
        self.assertEqual(created.user, self.user)
        self.assertEqual(created.processing_status, UserUploadedMap.PROCESSING_PENDING)
        self.assertEqual(created.processing_error, "")
        on_commit_mock.assert_called_once()
        delay_mock.assert_called_once_with(created.pk)


class GetLocalFilePathStreamingTests(TestCase):
    """
    The old implementation called `self.map_file.read()` which loaded the entire (up to 100MB) mbtiles into
    memory in a single gunicorn request worker. This test guards against that regression by asserting we
    use the chunked iterator instead.
    """

    def setUp(self):
        self.user = get_user_model().objects.create(email="streamuser@example.com")

    def test_uses_chunks_not_full_read(self):
        instance = _make_instance(self.user)

        from display.models import user_uploaded_map as module
        module.LOCAL_MAP_FILE_CACHE.pop(f"user_map_{instance.map_file.name}", None)

        with patch.object(instance.map_file, "chunks", return_value=[b"fake bytes"]) as chunks_mock, \
             patch.object(FieldFile, "read", new_callable=PropertyMock) as read_mock:
            path = instance.get_local_file_path()
            self.addCleanup(instance.clear_local_file_path)

        self.assertTrue(path)
        chunks_mock.assert_called_once()
        read_mock.assert_not_called()
