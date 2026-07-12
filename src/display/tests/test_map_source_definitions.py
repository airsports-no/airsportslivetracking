from unittest.mock import patch

from django.test import TestCase

from display.flight_order_and_maps import map_plotter_shared_utilities as sources


class MapSourceDefinitionTests(TestCase):
    def test_returns_builtin_non_mbtiles_source_definition(self):
        definition = sources.get_map_source_definition("openaip")

        self.assertEqual(definition["key"], "openaip")
        self.assertEqual(definition["label"], "OpenAIP")
        self.assertEqual(definition["provider"], "openaip")
        self.assertEqual(definition["type"], "raster_xyz")
        self.assertTrue(definition["is_overlay"])
        self.assertEqual(definition["default_zoom"], 10)

    @patch("display.flight_order_and_maps.map_plotter_shared_utilities.get_map_details")
    @patch("display.flight_order_and_maps.map_plotter_shared_utilities.get_available_maps")
    def test_returns_builtin_mbtiles_source_definition(self, mock_get_available_maps, mock_get_map_details):
        mock_get_available_maps.return_value = [
            {"name": "Norway 250k", "url": "https://mbtiles.airsports.no/services/Norway250k"}
        ]
        mock_get_map_details.return_value = {"minzoom": 8, "maxzoom": 14}

        definition = sources.get_map_source_definition("Norway250k")

        self.assertEqual(definition["key"], "Norway250k")
        self.assertEqual(definition["label"], "Norway 250k")
        self.assertEqual(definition["provider"], "mbtiles")
        self.assertEqual(definition["type"], "mbtiles")
        self.assertEqual(definition["min_zoom"], 8)
        self.assertEqual(definition["max_zoom"], 14)
        mock_get_map_details.assert_called_once_with("Norway250k")

    @patch("display.flight_order_and_maps.map_plotter_shared_utilities.get_map_details")
    @patch("display.flight_order_and_maps.map_plotter_shared_utilities.get_available_maps")
    def test_get_builtin_map_source_definitions_contains_both_non_mbtiles_and_mbtiles(
        self, mock_get_available_maps, mock_get_map_details
    ):
        mock_get_available_maps.return_value = [
            {"name": "Norway 250k", "url": "https://mbtiles.airsports.no/services/Norway250k"}
        ]
        mock_get_map_details.return_value = {"minzoom": 8, "maxzoom": 14}

        definitions = sources.get_builtin_map_source_definitions()
        keys = {item["key"] for item in definitions}

        self.assertIn("osm", keys)
        self.assertIn("openaip", keys)
        self.assertIn("Norway250k", keys)
