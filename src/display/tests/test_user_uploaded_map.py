import os
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models.fields.files import FieldFile
from django.test import TestCase, override_settings
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITransactionTestCase

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import Contest, EditableRoute, NavigationTask, Route, Scorecard
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
             patch("display.tasks.request_mbtiles_reload") as reload_mock:
            process_user_uploaded_map(instance.pk)

        instance.refresh_from_db()
        self.assertEqual(instance.processing_status, UserUploadedMap.PROCESSING_READY)
        self.assertEqual(instance.processing_error, "")
        self.assertEqual(instance.minimum_zoom_level, 10)
        self.assertEqual(instance.maximum_zoom_level, 14)
        self.assertEqual(instance.default_zoom_level, 12)
        self.assertEqual(instance.published_service_key, instance.default_service_key)
        self.assertEqual(instance.published_relative_path, str(instance.map_file))
        self.assertIsNotNone(instance.published_at)
        self.assertTrue(instance.thumbnail)
        reload_mock.assert_called_once()

    @override_settings(MBTILES_PUBLISH_ROOT="/tilesets-test")
    def test_processing_stores_bounds_when_available(self):
        instance = _make_instance(self.user, default_zoom=12)
        fake_png = BytesIO(b"\x89PNG\r\n\x1a\nfake")

        with patch.object(UserUploadedMap, "create_thumbnail", return_value=(fake_png, 10, 14)), \
             patch.object(UserUploadedMap, "get_bounds", return_value=(10.0, 59.0, 11.0, 60.0)), \
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
             patch("display.tasks.request_mbtiles_reload") as reload_mock, \
             patch.object(FieldFile, "save", side_effect=PermissionError("no thumbnail write permission")):
            process_user_uploaded_map(instance.pk)

        instance.refresh_from_db()
        self.assertEqual(instance.processing_status, UserUploadedMap.PROCESSING_READY)
        self.assertEqual(instance.processing_error, "")
        self.assertEqual(instance.minimum_zoom_level, 10)
        self.assertEqual(instance.maximum_zoom_level, 14)
        self.assertEqual(instance.published_service_key, instance.default_service_key)
        self.assertEqual(instance.published_relative_path, str(instance.map_file))
        self.assertIsNotNone(instance.published_at)
        reload_mock.assert_called_once()

    def test_default_zoom_is_clamped_when_outside_range(self):
        instance = _make_instance(self.user, default_zoom=18)
        fake_png = BytesIO(b"\x89PNGfake")

        with patch.object(UserUploadedMap, "create_thumbnail", return_value=(fake_png, 10, 14)), \
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
        self.assertEqual(instance.default_published_relative_path, instance.map_file.name)

    @override_settings(MBTILES_PUBLISH_ROOT="/tmp/tilesets-test")
    def test_processing_uses_published_file_as_canonical_source_after_initial_publish(self):
        instance = _make_instance(self.user, default_zoom=12)
        fake_png = BytesIO(b"\x89PNG\r\n\x1a\nfake")

        with patch.object(UserUploadedMap, "create_thumbnail", return_value=(fake_png, 10, 14)), \
             patch.object(UserUploadedMap, "get_bounds", return_value=(10.0, 59.0, 11.0, 60.0)), \
             patch("display.tasks.request_mbtiles_reload"):
            process_user_uploaded_map(instance.pk)

        instance.refresh_from_db()
        published_path = instance.published_absolute_path
        published_path.parent.mkdir(parents=True, exist_ok=True)
        published_path.write_bytes(b"published mbtiles bytes")
        self.addCleanup(lambda: published_path.unlink(missing_ok=True))

        with patch.object(UserUploadedMap, "create_thumbnail", return_value=(fake_png, 10, 14)) as second_thumbnail_mock, \
             patch.object(UserUploadedMap, "get_bounds", return_value=(10.0, 59.0, 11.0, 60.0)), \
             patch("display.tasks.request_mbtiles_reload"):
            process_user_uploaded_map(instance.pk)

        self.assertTrue(second_thumbnail_mock.called)


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
        MBTILES_RELOAD_METHOD="kubernetes",
        MBTILES_RELOAD_NAMESPACE="default",
        MBTILES_RELOAD_POD_LABEL_SELECTOR="service=mbtiles",
    )
    @patch("display.flight_order_and_maps.user_uploaded_mbtiles_publish.stream")
    @patch("display.flight_order_and_maps.user_uploaded_mbtiles_publish.client.CoreV1Api")
    @patch("display.flight_order_and_maps.user_uploaded_mbtiles_publish.config.load_incluster_config")
    def test_request_mbtiles_reload_signals_every_matching_pod(self, load_config_mock, core_api_cls, stream_mock):
        from display.flight_order_and_maps.user_uploaded_mbtiles_publish import request_mbtiles_reload

        pod_a, pod_b = MagicMock(), MagicMock()
        pod_a.metadata.name = "mbtiles-pod-1"
        pod_b.metadata.name = "mbtiles-pod-2"
        core_api = core_api_cls.return_value
        core_api.list_namespaced_pod.return_value.items = [pod_a, pod_b]

        request_mbtiles_reload()

        self.assertEqual(stream_mock.call_count, 2)
        signaled_names = {call.kwargs["name"] for call in stream_mock.call_args_list}
        self.assertEqual(signaled_names, {"mbtiles-pod-1", "mbtiles-pod-2"})

    @override_settings(
        MBTILES_RELOAD_METHOD="kubernetes",
        MBTILES_RELOAD_NAMESPACE="default",
        MBTILES_RELOAD_POD_LABEL_SELECTOR="service=mbtiles",
    )
    @patch("display.flight_order_and_maps.user_uploaded_mbtiles_publish.stream")
    @patch("display.flight_order_and_maps.user_uploaded_mbtiles_publish.client.CoreV1Api")
    @patch("display.flight_order_and_maps.user_uploaded_mbtiles_publish.config.load_incluster_config")
    def test_request_mbtiles_reload_signals_remaining_pods_after_one_failure(
        self, load_config_mock, core_api_cls, stream_mock
    ):
        from display.flight_order_and_maps.user_uploaded_mbtiles_publish import request_mbtiles_reload

        pod_a, pod_b = MagicMock(), MagicMock()
        pod_a.metadata.name = "mbtiles-pod-1"
        pod_b.metadata.name = "mbtiles-pod-2"
        core_api = core_api_cls.return_value
        core_api.list_namespaced_pod.return_value.items = [pod_a, pod_b]
        stream_mock.side_effect = [Exception("exec failed"), None]

        with self.assertRaises(RuntimeError) as ctx:
            request_mbtiles_reload()

        # Both pods still got an exec attempt despite the first one failing.
        self.assertEqual(stream_mock.call_count, 2)
        self.assertIn("mbtiles-pod-1", str(ctx.exception))
        self.assertIn("1/2", str(ctx.exception))


class MapSourceDefinitionPayloadTests(APITransactionTestCase):
    reset_sequences = True

    def setUp(self):
        create_scorecards()
        self.user = get_user_model().objects.create(email="apiuser@example.com")
        self.contest = Contest.objects.create(
            name="Contest",
            start_time="2024-01-01T08:00:00Z",
            finish_time="2024-01-01T18:00:00Z",
        )
        self.route = Route.objects.create(name="Route")
        self.navigation_task = NavigationTask.create(
            name="Task",
            original_scorecard=Scorecard.objects.first(),
            start_time="2024-01-01T10:00:00Z",
            finish_time="2024-01-01T11:00:00Z",
            route=self.route,
            contest=self.contest,
        )
        self.editable_route = EditableRoute.objects.create(
            name="Editable route",
            route={"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"featureType": "route_path"}, "geometry": {"type": "LineString", "coordinates": []}}]},
        )
        self.client.force_login(self.user)
        assign_perm("display.view_contest", self.user, self.contest)
        assign_perm("display.change_contest", self.user, self.contest)
        assign_perm("display.add_editableroute", self.user)
        assign_perm("display.change_editableroute", self.user, self.editable_route)
        assign_perm("display.view_editableroute", self.user, self.editable_route)

    @patch("display.viewsets.get_builtin_map_source_definitions")
    @override_settings(MBTILES_PUBLIC_URL="http://localhost:8001/")
    def test_route_editor_map_sources_include_builtin_and_accessible_uploaded_maps(self, mock_get_builtin_map_source_definitions):
        mock_get_builtin_map_source_definitions.return_value = [
            {"key": "Norway250k", "label": "Norway 250k", "provider": "mbtiles", "type": "mbtiles", "tile_url": "http://localhost:8001/services/mbtiles/Norway250k/tiles/{z}/{x}/{y}.png", "attribution": "", "min_zoom": 8, "max_zoom": 14, "default_zoom": 12, "is_overlay": True, "allow_multiple": False, "is_always_on_top": False, "bounds": [10.0, 59.0, 11.0, 60.0]},
            {"key": "osm", "label": "OSM", "provider": "osm", "type": "raster_xyz", "tile_url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", "attribution": "© OpenStreetMap contributors", "min_zoom": 0, "max_zoom": 19, "default_zoom": 12, "is_overlay": False, "allow_multiple": False, "is_always_on_top": False, "bounds": None},
            {"key": "fc", "label": "Flight Contest", "provider": "fc", "type": "raster_xyz", "tile_url": "https://flightcontest.de/route/maps/{z}/{x}/{y}.png", "attribution": "FlightContest", "min_zoom": 0, "max_zoom": 18, "default_zoom": 12, "is_overlay": False, "allow_multiple": False, "is_always_on_top": False, "bounds": None},
            {"key": "mto", "label": "MapTiler Outdoor", "provider": "mto", "type": "raster_xyz", "tile_url": "https://api.maptiler.com/maps/outdoor/{z}/{x}/{y}.png?key=test", "attribution": "maptiler.com", "min_zoom": 0, "max_zoom": 18, "default_zoom": 12, "is_overlay": False, "allow_multiple": False, "is_always_on_top": False, "bounds": None},
            {"key": "cyclosm", "label": "CycleOSM", "provider": "cyclosm", "type": "raster_xyz", "tile_url": "https://a.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png", "attribution": "openstreetmap.org CycleOSM", "min_zoom": 0, "max_zoom": 20, "default_zoom": 12, "is_overlay": False, "allow_multiple": False, "is_always_on_top": False, "bounds": None},
            {"key": "openaip", "label": "OpenAIP", "provider": "openaip", "type": "raster_xyz", "tile_url": "https://api.tiles.openaip.net/api/data/openaip/{z}/{x}/{y}.png?apiKey=test", "attribution": "OpenAIP Data", "min_zoom": 4, "max_zoom": 14, "default_zoom": 10, "is_overlay": True, "allow_multiple": True, "is_always_on_top": True, "bounds": None},
        ]

        allowed = _make_instance(self.user)
        allowed.name = "Pilot uploaded map"
        allowed.processing_status = UserUploadedMap.PROCESSING_READY
        allowed.minimum_zoom_level = 10
        allowed.maximum_zoom_level = 13
        allowed.default_zoom_level = 11
        allowed.attribution = "Uploaded attribution"
        allowed.published_service_key = f"user-uploaded-map-{allowed.pk}"
        allowed.published_relative_path = f"user_uploaded_maps/user-uploaded-map-{allowed.pk}.mbtiles"
        allowed.minimum_longitude = 10.0
        allowed.minimum_latitude = 59.0
        allowed.maximum_longitude = 11.0
        allowed.maximum_latitude = 60.0
        allowed.save()
        assign_perm("display.view_useruploadedmap", self.user, allowed)

        hidden = UserUploadedMap.objects.create(user=self.user, name="Hidden map", processing_status=UserUploadedMap.PROCESSING_FAILED)
        collision = UserUploadedMap.objects.create(
            user=get_user_model().objects.create(email="collision@example.com"),
            name="Pilot uploaded map",
            processing_status=UserUploadedMap.PROCESSING_READY,
            published_service_key="user-uploaded-map-collision",
            minimum_zoom_level=9,
            maximum_zoom_level=12,
            default_zoom_level=10,
            attribution="Second uploaded attribution",
            minimum_longitude=12.0,
            minimum_latitude=61.0,
            maximum_longitude=13.0,
            maximum_latitude=62.0,
        )
        assign_perm("display.view_useruploadedmap", self.user, hidden)
        assign_perm("display.view_useruploadedmap", self.user, collision)

        response = self.client.get(reverse("editableroutes-map-sources", kwargs={"pk": self.editable_route.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        payload = response.json()

        self.assertEqual(len([item for item in payload if item["origin"] == "user_upload"]), 2)
        builtin = next(item for item in payload if item["key"] == "Norway250k")
        self.assertEqual(builtin["key"], "Norway250k")
        self.assertEqual(builtin["label"], "Norway 250k")
        self.assertEqual(builtin["tile_url"], "http://localhost:8001/services/mbtiles/Norway250k/tiles/{z}/{x}/{y}.png")
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

        uploaded = next(item for item in payload if item["origin"] == "user_upload" and item["key"] == f"user_uploaded:{allowed.pk}")
        self.assertEqual(uploaded["key"], f"user_uploaded:{allowed.pk}")
        self.assertEqual(uploaded["label"], allowed.name)
        self.assertEqual(uploaded["min_zoom"], 10)
        self.assertEqual(uploaded["max_zoom"], 13)
        self.assertEqual(uploaded["default_zoom"], 11)
        self.assertEqual(uploaded["attribution"], "Uploaded attribution")
        self.assertEqual(uploaded["tile_url"], f"http://localhost:8001/services/{Path(allowed.published_relative_path).stem}/tiles/{{z}}/{{x}}/{{y}}.png")
        self.assertEqual(uploaded["bounds"], [10.0, 59.0, 11.0, 60.0])
        self.assertNotIn(hidden.published_service_key, [item["key"] for item in payload])

    @patch("display.viewsets.get_builtin_map_source_definitions")
    @override_settings(MBTILES_PUBLIC_URL="http://localhost:8001/")
    def test_global_route_editor_map_sources_available_without_route_id(self, mock_get_builtin_map_source_definitions):
        mock_get_builtin_map_source_definitions.return_value = [
            {"key": "Norway250k", "label": "Norway 250k", "provider": "mbtiles", "type": "mbtiles", "tile_url": "http://localhost:8001/services/mbtiles/Norway250k/tiles/{z}/{x}/{y}.png", "attribution": "", "min_zoom": 8, "max_zoom": 14, "default_zoom": 12, "is_overlay": True, "allow_multiple": False, "is_always_on_top": False, "bounds": [10.0, 59.0, 11.0, 60.0]},
            {"key": "osm", "label": "OSM", "provider": "osm", "type": "raster_xyz", "tile_url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", "attribution": "© OpenStreetMap contributors", "min_zoom": 0, "max_zoom": 19, "default_zoom": 12, "is_overlay": False, "allow_multiple": False, "is_always_on_top": False, "bounds": None},
        ]

        response = self.client.get(reverse("editableroutes-global-map-sources"))
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        payload = response.json()
        self.assertTrue(any(item["key"] == "osm" for item in payload))
        self.assertTrue(any(item["key"] == "Norway250k" and item["is_overlay"] for item in payload))
        norway = next(item for item in payload if item["key"] == "Norway250k")
        self.assertEqual(norway["source_group"], "system_overlay")


class UserUploadedMapLifecycleViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="lifecycletester@example.com")

    @patch("display.views.unpublish_user_uploaded_map")
    @patch("display.views.request_mbtiles_reload")
    def test_update_view_unpublishes_before_reprocessing(self, reload_mock, unpublish_mock):
        instance = _make_instance(self.user)
        instance.published_service_key = f"user-uploaded-map-{instance.pk}"
        instance.published_relative_path = str(instance.map_file)
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
        self.assertEqual(instance.published_service_key, instance.default_service_key)
        self.assertEqual(instance.published_relative_path, str(instance.map_file))
        self.assertIsNone(instance.published_at)
        unpublish_mock.assert_not_called()
        reload_mock.assert_not_called()
        clear_local_mock.assert_called_once()
        on_commit_mock.assert_called_once()
        delay_mock.assert_called_once_with(instance.pk)

    @patch("display.views.unpublish_user_uploaded_map")
    @patch("display.views.request_mbtiles_reload")
    def test_update_view_unpublishes_previous_file_before_reprocessing(self, reload_mock, unpublish_mock):
        instance = _make_instance(self.user)
        instance.published_service_key = f"user-uploaded-map-{instance.pk}"
        instance.published_relative_path = "user_uploaded_maps/old-file.mbtiles"
        instance.processing_status = UserUploadedMap.PROCESSING_READY
        instance.processing_error = "old error"
        instance.save()
        instance.map_file = SimpleUploadedFile("new-file.mbtiles", b"replacement bytes")
        instance.save(update_fields=["map_file"])

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
        self.assertEqual(instance.published_service_key, instance.default_service_key)
        self.assertEqual(instance.published_relative_path, instance.default_published_relative_path)
        self.assertIsNone(instance.published_at)
        unpublish_mock.assert_called_once_with(instance, relative_path="user_uploaded_maps/old-file.mbtiles")
        reload_mock.assert_called_once()
        clear_local_mock.assert_called_once()
        on_commit_mock.assert_called_once()
        delay_mock.assert_called_once_with(instance.pk)

    @patch("display.views.unpublish_user_uploaded_map")
    @patch("display.views.request_mbtiles_reload")
    def test_update_view_skips_unpublish_when_file_path_is_unchanged(self, reload_mock, unpublish_mock):
        instance = _make_instance(self.user)
        instance.published_service_key = f"user-uploaded-map-{instance.pk}"
        instance.published_relative_path = str(instance.map_file)
        instance.processing_status = UserUploadedMap.PROCESSING_READY
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
        unpublish_mock.assert_not_called()
        reload_mock.assert_not_called()
        clear_local_mock.assert_called_once()
        on_commit_mock.assert_called_once()
        delay_mock.assert_called_once_with(instance.pk)

    @patch("display.views.unpublish_user_uploaded_map")
    @patch("display.views.request_mbtiles_reload")
    def test_delete_view_unpublishes_and_reloads(self, reload_mock, unpublish_mock):
        instance = _make_instance(self.user)
        instance.published_service_key = f"user-uploaded-map-{instance.pk}"
        instance.published_relative_path = f"user_uploaded_maps/user-uploaded-map-{instance.pk}.mbtiles"
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
        uploaded_map = UserUploadedMap.objects.create(user=self.user, name="Missing file map", processing_status=UserUploadedMap.PROCESSING_READY)
        assign_perm("display.view_useruploadedmap", self.user, uploaded_map)

        response = self.client.get(reverse("useruploadedmap_list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertContains(response, "Missing file map")

    def test_list_view_shows_extent_when_bounds_are_available(self):
        uploaded_map = UserUploadedMap.objects.create(
            user=self.user,
            name="Extent map",
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
        uploaded_map = UserUploadedMap.objects.create(user=self.user, name="Missing file map", processing_status=UserUploadedMap.PROCESSING_READY)
        assign_perm("display.view_useruploadedmap", self.user, uploaded_map)
        assign_perm("display.change_useruploadedmap", self.user, uploaded_map)

        response = self.client.get(reverse("useruploadedmap_change", kwargs={"pk": uploaded_map.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertContains(response, "Upload User Map")

    def test_delete_view_tolerates_missing_map_file_on_disk(self):
        uploaded_map = UserUploadedMap.objects.create(user=self.user, name="Missing file map", processing_status=UserUploadedMap.PROCESSING_READY)
        assign_perm("display.view_useruploadedmap", self.user, uploaded_map)
        assign_perm("display.delete_useruploadedmap", self.user, uploaded_map)

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
        self.assertEqual(created.published_service_key, created.default_service_key)
        self.assertEqual(created.published_relative_path, str(created.map_file))
        self.assertEqual(created.processing_error, "")
        on_commit_mock.assert_called_once()
        delay_mock.assert_called_once_with(created.pk)

    @patch("display.views.process_user_uploaded_map.delay")
    @patch("display.views.transaction.on_commit", side_effect=lambda fn: fn())
    def test_create_view_keeps_uploaded_blob_as_canonical_storage(self, on_commit_mock, delay_mock):
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
        created = UserUploadedMap.objects.get(name="Created map")
        self.assertEqual(created.processing_status, UserUploadedMap.PROCESSING_PENDING)
        self.assertTrue(bool(created.map_file))


class UnifiedMapSelectionViewTests(TestCase):
    def setUp(self):
        create_scorecards()
        self.user = get_user_model().objects.create(email="unified-map-selection@example.com")
        self.client.force_login(self.user)
        self.contest = Contest.objects.create(
            name="Contest",
            start_time="2024-01-01T08:00:00Z",
            finish_time="2024-01-01T18:00:00Z",
        )
        self.navigation_task = NavigationTask.create(
            name="Task",
            original_scorecard=Scorecard.objects.first(),
            start_time="2024-01-01T10:00:00Z",
            finish_time="2024-01-01T11:00:00Z",
            route=Route.objects.create(name="Route"),
            contest=self.contest,
        )
        assign_perm("display.view_contest", self.user, self.contest)
        assign_perm("display.change_contest", self.user, self.contest)

    @patch("display.views.get_available_map_source_definitions_for_navigation_task")
    def test_update_flight_order_form_exposes_only_unified_map_source_field(self, mock_get_sources):
        mock_get_sources.return_value = [
            {"key": "osm", "label": "OSM", "min_zoom": 0, "max_zoom": 19, "default_zoom": 12},
            {"key": "user_uploaded:42", "label": "Uploaded map", "min_zoom": 7, "max_zoom": 13, "default_zoom": 10},
        ]

        response = self.client.get(reverse("navigationtask_flightorderconfiguration", kwargs={"pk": self.navigation_task.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertContains(response, 'id="id_map_source"')
        self.assertNotContains(response, 'id="id_map_user_source"')
        self.assertContains(response, "user_uploaded:42")

    @patch("display.views.get_available_map_source_definitions_for_navigation_task")
    @patch("display.tasks.generate_map_async")
    def test_navigation_task_map_post_uses_unified_map_source_without_user_map_source_id(self, generate_map_async_mock, mock_get_sources):
        mock_get_sources.return_value = [
            {"key": "osm", "label": "OSM", "min_zoom": 0, "max_zoom": 19, "default_zoom": 12},
            {"key": "user_uploaded:42", "label": "Uploaded map", "min_zoom": 7, "max_zoom": 13, "default_zoom": 10},
        ]

        response = self.client.post(
            reverse("navigationtask_map", kwargs={"pk": self.navigation_task.pk}),
            {
                "size": "A4",
                "orientation": "landscape",
                "plot_track_between_waypoints": True,
                "include_meridians_and_parallels_lines": True,
                "include_openaip_overlay": True,
                "scale": "100000",
                "map_source": "user_uploaded:42",
                "zoom_level": 10,
                "dpi": 150,
                "line_width": 0.5,
                "colour": "#0000ff",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")
        generate_map_async_mock.delay.assert_not_called()

    @patch("display.tasks.generate_map_async")
    @patch("display.views.get_available_map_source_definitions_for_navigation_task")
    def test_navigation_task_map_includes_openaip_overlay_flag_in_async_payload(self, mock_get_sources, generate_map_async_mock):
        mock_get_sources.return_value = [
            {"key": "osm", "label": "OSM", "min_zoom": 0, "max_zoom": 19, "default_zoom": 12},
        ]

        response = self.client.post(
            reverse("navigationtask_map", kwargs={"pk": self.navigation_task.pk}),
            {
                "size": "A4",
                "zoom_level": 12,
                "orientation": "landscape",
                "plot_track_between_waypoints": True,
                "include_meridians_and_parallels_lines": True,
                "include_openaip_overlay": True,
                "scale": "100",
                "map_source": "osm",
                "dpi": 150,
                "line_width": 0.5,
                "colour": "#0000ff",
            },
        )

        self.assertEqual(response.status_code, 302, response.content)
        args = generate_map_async_mock.delay.call_args.args
        self.assertTrue(args[2]["include_openaip_overlay"])

    @patch("display.tasks.generate_map_async")
    @patch("display.views.get_available_map_source_definitions_for_navigation_task")
    def test_contestant_map_includes_contestant_declaration_flag_in_async_payload(self, mock_get_sources, generate_map_async_mock):
        from display.models import Contestant, Team, Crew, Aeroplane, Person
        import datetime

        mock_get_sources.return_value = [
            {"key": "osm", "label": "OSM", "min_zoom": 0, "max_zoom": 19, "default_zoom": 12},
        ]
        pilot = Person.objects.create(first_name="Pilot", last_name="One", country="NO")
        crew = Crew.objects.create(member1=pilot)
        aeroplane = Aeroplane.objects.create(registration="LN-MAP")
        team = Team.objects.create(crew=crew, aeroplane=aeroplane)
        contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=team,
            contestant_number=1,
            air_speed=80,
            wind_speed=0,
            wind_direction=0,
            takeoff_time=datetime.datetime(2024, 1, 1, 10, 0, tzinfo=datetime.timezone.utc),
            finished_by_time=datetime.datetime(2024, 1, 1, 11, 0, tzinfo=datetime.timezone.utc),
            tracker_start_time=datetime.datetime(2024, 1, 1, 9, 50, tzinfo=datetime.timezone.utc),
        )

        response = self.client.post(
            reverse("contestant_map", kwargs={"pk": contestant.pk}),
            {
                "size": "A4",
                "dpi": 150,
                "zoom_level": 12,
                "orientation": "portrait",
                "scale": "100",
                "map_source": "osm",
                "include_openaip_overlay": False,
                "include_annotations": True,
                "include_contestant_declarations": False,
                "plot_track_between_waypoints": True,
                "include_meridians_and_parallels_lines": True,
                "line_width": 0.5,
                "minute_mark_line_width": 0.5,
                "colour": "#0000ff",
            },
        )

        self.assertEqual(response.status_code, 302, response.content)
        args = generate_map_async_mock.delay.call_args.args
        self.assertFalse(args[2]["include_contestant_declarations"])
