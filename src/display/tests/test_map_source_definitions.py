from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from guardian.shortcuts import assign_perm

from display.flight_order_and_maps import map_plotter_shared_utilities as sources
from display.models.user_uploaded_map import UserUploadedMap


class MapSourceDefinitionTests(TestCase):
    def test_returns_builtin_non_mbtiles_source_definition(self):
        definition = sources.get_map_source_definition("openaip")

        self.assertEqual(definition["key"], "openaip")
        self.assertEqual(definition["label"], "OpenAIP")
        self.assertEqual(definition["provider"], "openaip")
        self.assertEqual(definition["type"], "raster_xyz")
        self.assertTrue(definition["is_overlay"])
        self.assertTrue(definition["allow_multiple"])
        self.assertTrue(definition["is_always_on_top"])
        self.assertEqual(definition["default_zoom"], 10)

    @patch("display.flight_order_and_maps.map_plotter_shared_utilities.get_map_details")
    @patch("display.flight_order_and_maps.map_plotter_shared_utilities.get_available_maps")
    def test_returns_builtin_mbtiles_source_definition(self, mock_get_available_maps, mock_get_map_details):
        mock_get_available_maps.return_value = [
            {"name": "Norway 250k", "url": "https://mbtiles.airsports.no/services/Norway250k"}
        ]
        mock_get_map_details.return_value = {"minzoom": 8, "maxzoom": 14, "tiles": ["http://mbtiles:8000/services/Norway250k/tiles/{z}/{x}/{y}.png"]}

        definition = sources.get_map_source_definition("Norway250k")

        self.assertEqual(definition["key"], "Norway250k")
        self.assertEqual(definition["label"], "Norway 250k")
        self.assertEqual(definition["provider"], "mbtiles")
        self.assertEqual(definition["type"], "mbtiles")
        self.assertEqual(definition["min_zoom"], 8)
        self.assertEqual(definition["max_zoom"], 14)
        self.assertEqual(definition["tile_url"], "http://localhost:8001/services/Norway250k/tiles/{z}/{x}/{y}.png")
        payload = sources.map_source_definition_to_payload(definition)
        self.assertEqual(payload["source_group"], "system_overlay")
        mock_get_map_details.assert_called_once_with("Norway250k")

    @patch("display.flight_order_and_maps.map_plotter_shared_utilities.get_map_details")
    @patch("display.flight_order_and_maps.map_plotter_shared_utilities.get_available_maps")
    def test_get_builtin_map_source_definitions_contains_both_non_mbtiles_and_mbtiles(
        self, mock_get_available_maps, mock_get_map_details
    ):
        mock_get_available_maps.return_value = [
            {"name": "Norway 250k", "url": "https://mbtiles.airsports.no/services/Norway250k"}
        ]
        mock_get_map_details.return_value = {
            "minzoom": 8,
            "maxzoom": 14,
            "tiles": ["http://mbtiles:8000/services/mbtiles/Norway250k/tiles/{z}/{x}/{y}.png"],
            "bounds": [10.0, 59.0, 11.0, 60.0],
        }

        definitions = sources.get_builtin_map_source_definitions()
        keys = {item["key"] for item in definitions}

        self.assertIn("osm", keys)
        self.assertIn("openaip", keys)
        self.assertIn("Norway250k", keys)

        norway = next(item for item in definitions if item["key"] == "Norway250k")
        self.assertEqual(
            norway["tile_url"],
            "http://localhost:8001/services/mbtiles/Norway250k/tiles/{z}/{x}/{y}.png",
        )
        mock_get_map_details.assert_called_once_with("Norway250k")

    def test_map_source_payload_groups_uploaded_and_system_overlays(self):
        system_payload = sources.map_source_definition_to_payload(
            {
                "key": "Norway250k",
                "label": "Norway 250k",
                "type": "mbtiles",
                "tile_url": "http://localhost:8001/services/Norway250k/tiles/{z}/{x}/{y}.png",
                "attribution": "",
                "min_zoom": 8,
                "max_zoom": 14,
                "default_zoom": 12,
                "is_overlay": True,
                "allow_multiple": False,
                "is_always_on_top": False,
                "bounds": [10.0, 59.0, 11.0, 60.0],
            }
        )
        uploaded_payload = sources.map_source_definition_to_payload(
            {
                "key": "user_uploaded:42",
                "label": "Uploaded map",
                "type": "mbtiles",
                "tile_url": "http://localhost:8001/services/uploaded/tiles/{z}/{x}/{y}.png",
                "attribution": "",
                "min_zoom": 8,
                "max_zoom": 14,
                "default_zoom": 12,
                "is_overlay": True,
                "allow_multiple": False,
                "is_always_on_top": False,
                "bounds": [10.0, 59.0, 11.0, 60.0],
            },
            origin="user_upload",
        )

        self.assertEqual(system_payload["source_group"], "system_overlay")
        self.assertEqual(uploaded_payload["source_group"], "uploaded_overlay")
    @patch("display.flight_order_and_maps.map_plotter_shared_utilities.get_available_maps")
    def test_get_builtin_map_source_definitions_excludes_user_uploaded_namespace(
        self, mock_get_available_maps, mock_get_map_details
    ):
        mock_get_available_maps.return_value = [
            {"name": "Norway 250k", "url": "https://mbtiles.airsports.no/services/Norway250k"},
            {"name": "Pilot uploaded map", "url": "http://localhost:8001/services/user-uploaded-map-307"},
            {"name": "Swiss uploaded file", "url": "http://localhost:8001/services/swiss-map-raster200_2021_14_krel_10_2056_eraIjwJ"},
        ]
        mock_get_map_details.return_value = {
            "minzoom": 8,
            "maxzoom": 14,
            "tiles": ["http://mbtiles:8000/services/mbtiles/Norway250k/tiles/{z}/{x}/{y}.png"],
        }
        UserUploadedMap.objects.create(
            user=get_user_model().objects.create(email="uploaded@example.com"),
            name="Swiss",
            published_service_key="user-uploaded-map-307",
            published_relative_path="user_uploaded_maps/swiss-map-raster200_2021_14_krel_10_2056_eraIjwJ.mbtiles",
            processing_status=UserUploadedMap.PROCESSING_READY,
        )

        definitions = sources.get_builtin_map_source_definitions()

        self.assertTrue(any(item["key"] == "Norway250k" for item in definitions))
        self.assertFalse(any(item["label"] == "Pilot uploaded map" for item in definitions))
        self.assertFalse(any(item["key"] == "swiss-map-raster200_2021_14_krel_10_2056_eraIjwJ" for item in definitions))


class NavigationTaskMapSourceAvailabilityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="maps@example.com")

    @patch("display.flight_order_and_maps.map_plotter_shared_utilities.get_builtin_map_source_definitions")
    def test_includes_global_sources_and_extent_overlapping_maps_only(self, mock_get_builtin_map_source_definitions):
        mock_get_builtin_map_source_definitions.return_value = [
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
                "allow_multiple": False,
                "is_always_on_top": False,
                "bounds": None,
            },
            {
                "key": "Norway250k",
                "label": "Norway 250k",
                "provider": "mbtiles",
                "type": "mbtiles",
                "tile_url": "http://localhost:8001/services/mbtiles/Norway250k/tiles/{z}/{x}/{y}.png",
                "attribution": "",
                "min_zoom": 8,
                "max_zoom": 14,
                "default_zoom": 12,
                "is_overlay": True,
                "allow_multiple": False,
                "is_always_on_top": False,
                "bounds": [10.0, 59.0, 11.0, 60.0],
            },
            {
                "key": "Sweden250k",
                "label": "Sweden 250k",
                "provider": "mbtiles",
                "type": "mbtiles",
                "tile_url": "http://localhost:8001/services/mbtiles/Sweden250k/tiles/{z}/{x}/{y}.png",
                "attribution": "",
                "min_zoom": 8,
                "max_zoom": 14,
                "default_zoom": 12,
                "is_overlay": True,
                "allow_multiple": False,
                "is_always_on_top": False,
                "bounds": [20.0, 65.0, 21.0, 66.0],
            },
        ]
        overlapping_uploaded = UserUploadedMap.objects.create(
            user=self.user,
            name="Overlap",
            published_service_key="user-uploaded-map-1",
            minimum_zoom_level=10,
            maximum_zoom_level=13,
            default_zoom_level=11,
            attribution="Uploaded attribution",
            processing_status=UserUploadedMap.PROCESSING_READY,
            minimum_longitude=10.0,
            minimum_latitude=59.0,
            maximum_longitude=11.0,
            maximum_latitude=60.0,
        )
        outside_uploaded = UserUploadedMap.objects.create(
            user=self.user,
            name="Outside",
            published_service_key="user-uploaded-map-2",
            minimum_zoom_level=10,
            maximum_zoom_level=13,
            default_zoom_level=11,
            attribution="Uploaded attribution",
            processing_status=UserUploadedMap.PROCESSING_READY,
            minimum_longitude=20.0,
            minimum_latitude=65.0,
            maximum_longitude=21.0,
            maximum_latitude=66.0,
        )
        hidden_uploaded = UserUploadedMap.objects.create(
            user=self.user,
            name="Hidden",
            published_service_key="user-uploaded-map-3",
            minimum_zoom_level=10,
            maximum_zoom_level=13,
            default_zoom_level=11,
            attribution="Uploaded attribution",
            processing_status=UserUploadedMap.PROCESSING_READY,
            minimum_longitude=10.0,
            minimum_latitude=59.0,
            maximum_longitude=11.0,
            maximum_latitude=60.0,
        )
        assign_perm("display.view_useruploadedmap", self.user, overlapping_uploaded)
        assign_perm("display.view_useruploadedmap", self.user, outside_uploaded)

        task = SimpleNamespace(route=SimpleNamespace(get_extent=lambda: (59.0, 60.0, 10.0, 11.0)))

        definitions = sources.get_available_map_source_definitions_for_navigation_task(task, self.user)
        keys = {item["key"] for item in definitions}

        self.assertIn("osm", keys)
        self.assertIn("Norway250k", keys)
        self.assertNotIn("Sweden250k", keys)
        self.assertNotIn("openaip", keys)
        self.assertIn(sources.uploaded_map_token(overlapping_uploaded), keys)
        self.assertNotIn(sources.uploaded_map_token(outside_uploaded), keys)
        self.assertNotIn(sources.uploaded_map_token(hidden_uploaded), keys)

    def test_uploaded_map_token_round_trip(self):
        uploaded = UserUploadedMap.objects.create(
            user=self.user,
            name="Round trip",
            published_service_key="user-uploaded-map-4",
            processing_status=UserUploadedMap.PROCESSING_READY,
        )

        token = sources.uploaded_map_token(uploaded)

        self.assertEqual(token, f"user_uploaded:{uploaded.pk}")
        self.assertEqual(sources.parse_uploaded_map_token(token), uploaded.pk)

    @patch("display.flight_order_and_maps.map_plotter_shared_utilities.get_builtin_map_source_definitions", return_value=[])
    def test_includes_uploaded_maps_from_passed_uploaded_queryset(self, _mock_get_builtin_map_source_definitions):
        uploaded = UserUploadedMap.objects.create(
            user=self.user,
            name="Contest shared",
            published_service_key="user-uploaded-map-5",
            minimum_zoom_level=10,
            maximum_zoom_level=13,
            default_zoom_level=11,
            attribution="Uploaded attribution",
            processing_status=UserUploadedMap.PROCESSING_READY,
            minimum_longitude=10.0,
            minimum_latitude=59.0,
            maximum_longitude=11.0,
            maximum_latitude=60.0,
        )
        task = SimpleNamespace(
            route=SimpleNamespace(get_extent=lambda: (59.0, 60.0, 10.0, 11.0)),
        )

        definitions = sources.get_available_map_source_definitions_for_navigation_task(
            task,
            self.user,
            uploaded_maps=UserUploadedMap.objects.filter(pk=uploaded.pk),
        )
        keys = {item["key"] for item in definitions}

        self.assertIn(sources.uploaded_map_token(uploaded), keys)
        payload = [
            sources.map_source_definition_to_payload(definition, origin="user_upload") for definition in definitions
        ]
        uploaded_payload = next(item for item in payload if item["key"] == sources.uploaded_map_token(uploaded))
        self.assertEqual(uploaded_payload["source_group"], "uploaded_overlay")
