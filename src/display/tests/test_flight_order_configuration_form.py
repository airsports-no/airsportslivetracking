import datetime
from unittest.mock import patch

from django.test import TestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.forms import FlightOrderConfigurationForm, MapForm, ContestantMapForm, validate_map_zoom_level
from display.flight_order_and_maps.generate_flight_orders import build_flight_order_map_plot_kwargs
from display.flight_order_and_maps.map_plotter_shared_utilities import resolve_map_source_definition
from display.models import Contest, NavigationTask, Route


class FlightOrderConfigurationFormTests(TestCase):
    def setUp(self):
        self.contest = Contest.objects.create(
            name="Test Contest",
            start_time=datetime.datetime(2020, 1, 1, 8, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2020, 1, 1, 18, tzinfo=datetime.timezone.utc),
        )
        self.route = Route.objects.create(name="Test Route")
        self.navigation_task = NavigationTask.create(
            name="Test Task",
            original_scorecard=get_default_scorecard(),
            start_time=datetime.datetime(2020, 1, 1, 10, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2020, 1, 1, 11, tzinfo=datetime.timezone.utc),
            route=self.route,
            contest=self.contest,
        )
        self.configuration = self.navigation_task.flightorderconfiguration

    @patch("display.forms.validate_map_zoom_level")
    @patch(
        "display.forms.get_map_choices",
        return_value=[
            ("Norway250k", "Norway 250k"),
            ("osm", "OSM"),
            ("fc", "Flight Contest"),
            ("mto", "MapTiler Outdoor"),
            ("cyclosm", "CycleOSM"),
            ("openaip", "OpenAIP"),
        ],
    )
    def test_accepts_osm_map_source_from_dynamic_choices(self, _mock_choices, mock_validate_zoom):
        form = FlightOrderConfigurationForm(
            data={
                "document_size": self.configuration.document_size,
                "include_turning_point_images": self.configuration.include_turning_point_images,
                "map_include_meridians_and_parallels_lines": self.configuration.map_include_meridians_and_parallels_lines,
                "map_dpi": self.configuration.map_dpi,
                "map_zoom_level": self.configuration.map_zoom_level,
                "map_orientation": self.configuration.map_orientation,
                "map_scale": self.configuration.map_scale,
                "map_source": "osm",
                "map_include_annotations": self.configuration.map_include_annotations,
                "map_plot_track_between_waypoints": self.configuration.map_plot_track_between_waypoints,
                "map_line_width": self.configuration.map_line_width,
                "map_minute_mark_line_width": self.configuration.map_minute_mark_line_width,
                "map_line_colour": self.configuration.map_line_colour,
                "turning_point_photos_meters_across": self.configuration.turning_point_photos_meters_across,
                "turning_point_photos_zoom_level": self.configuration.turning_point_photos_zoom_level,
                "unknown_leg_photos_meters_across": self.configuration.unknown_leg_photos_meters_across,
                "unknown_leg_photos_zoom_level": self.configuration.unknown_leg_photos_zoom_level,
                "photos_meters_across": self.configuration.photos_meters_across,
                "photos_zoom_level": self.configuration.photos_zoom_level,
            },
            instance=self.configuration,
        )

        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertEqual(saved.map_source, "osm")
        mock_validate_zoom.assert_called_once()

    @patch("display.forms.validate_map_zoom_level")
    @patch("display.forms.get_map_choices", return_value=[("cyclosm", "CycleOSM")])
    def test_rejects_unknown_map_source(self, _mock_choices, mock_validate_zoom):
        form = FlightOrderConfigurationForm(
            data={
                "document_size": self.configuration.document_size,
                "include_turning_point_images": self.configuration.include_turning_point_images,
                "map_include_meridians_and_parallels_lines": self.configuration.map_include_meridians_and_parallels_lines,
                "map_dpi": self.configuration.map_dpi,
                "map_zoom_level": self.configuration.map_zoom_level,
                "map_orientation": self.configuration.map_orientation,
                "map_scale": self.configuration.map_scale,
                "map_source": "not-a-map",
                "map_include_annotations": self.configuration.map_include_annotations,
                "map_plot_track_between_waypoints": self.configuration.map_plot_track_between_waypoints,
                "map_line_width": self.configuration.map_line_width,
                "map_minute_mark_line_width": self.configuration.map_minute_mark_line_width,
                "map_line_colour": self.configuration.map_line_colour,
                "turning_point_photos_meters_across": self.configuration.turning_point_photos_meters_across,
                "turning_point_photos_zoom_level": self.configuration.turning_point_photos_zoom_level,
                "unknown_leg_photos_meters_across": self.configuration.unknown_leg_photos_meters_across,
                "unknown_leg_photos_zoom_level": self.configuration.unknown_leg_photos_zoom_level,
                "photos_meters_across": self.configuration.photos_meters_across,
                "photos_zoom_level": self.configuration.photos_zoom_level,
            },
            instance=self.configuration,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("map_source", form.errors)
        mock_validate_zoom.assert_not_called()

    @patch(
        "display.forms.get_map_choices",
        return_value=[
            ("Norway250k", "Norway 250k"),
            ("osm", "OSM"),
            ("fc", "Flight Contest"),
            ("mto", "MapTiler Outdoor"),
            ("cyclosm", "CycleOSM"),
            ("openaip", "OpenAIP"),
        ],
    )
    def test_form_exposes_dynamic_map_source_choices(self, mock_choices):
        form = FlightOrderConfigurationForm(instance=self.configuration)

        self.assertEqual(form.fields["map_source"].choices, mock_choices.return_value)

    def test_map_generation_forms_use_supplied_unified_map_choices(self):
        unified_choices = [("osm", "OSM"), ("user_uploaded:42", "Uploaded map")]

        generic_form = MapForm(map_source_choices=unified_choices)
        contestant_form = ContestantMapForm(map_source_choices=unified_choices)

        self.assertEqual(generic_form.fields["map_source"].choices, unified_choices)
        self.assertNotIn("user_map_source", generic_form.fields)
        self.assertEqual(contestant_form.fields["map_source"].choices, unified_choices)
        self.assertNotIn("user_map_source", contestant_form.fields)

    @patch(
        "display.forms.resolve_map_source_definition",
        return_value={"label": "Uploaded map", "min_zoom": 7, "max_zoom": 13},
    )
    def test_flight_order_form_accepts_uploaded_token_from_supplied_choices_even_when_model_default_choices_do_not_include_it(self, mock_resolve_map_source_definition):
        unified_choices = [("osm", "OSM"), ("user_uploaded:42", "Uploaded map")]

        form = FlightOrderConfigurationForm(
            data={
                "document_size": self.configuration.document_size,
                "include_turning_point_images": self.configuration.include_turning_point_images,
                "map_include_meridians_and_parallels_lines": self.configuration.map_include_meridians_and_parallels_lines,
                "map_dpi": self.configuration.map_dpi,
                "map_zoom_level": self.configuration.map_zoom_level,
                "map_orientation": self.configuration.map_orientation,
                "map_scale": self.configuration.map_scale,
                "map_source": "user_uploaded:42",
                "map_include_annotations": self.configuration.map_include_annotations,
                "map_plot_track_between_waypoints": self.configuration.map_plot_track_between_waypoints,
                "map_line_width": self.configuration.map_line_width,
                "map_minute_mark_line_width": self.configuration.map_minute_mark_line_width,
                "map_line_colour": self.configuration.map_line_colour,
                "turning_point_photos_meters_across": self.configuration.turning_point_photos_meters_across,
                "turning_point_photos_zoom_level": self.configuration.turning_point_photos_zoom_level,
                "unknown_leg_photos_meters_across": self.configuration.unknown_leg_photos_meters_across,
                "unknown_leg_photos_zoom_level": self.configuration.unknown_leg_photos_zoom_level,
                "photos_meters_across": self.configuration.photos_meters_across,
                "photos_zoom_level": self.configuration.photos_zoom_level,
            },
            instance=self.configuration,
            map_source_choices=unified_choices,
        )

        self.assertTrue(form.is_valid(), form.errors)
        mock_resolve_map_source_definition.assert_called_once_with("user_uploaded:42", None)

    @patch(
        "display.forms.resolve_map_source_definition",
        return_value={"label": "Norway 250k", "min_zoom": 8, "max_zoom": 14},
    )
    def test_validate_map_zoom_level_accepts_unified_builtin_mbtiles_source(self, mock_resolve_map_source_definition):
        validate_map_zoom_level("Norway250k", None, 12)
        mock_resolve_map_source_definition.assert_called_once_with("Norway250k", None)

    @patch(
        "display.forms.resolve_map_source_definition",
        return_value={"label": "OpenAIP", "min_zoom": 4, "max_zoom": 14},
    )
    def test_validate_map_zoom_level_accepts_unified_non_mbtiles_source(self, mock_resolve_map_source_definition):
        validate_map_zoom_level("openaip", None, 10)
        mock_resolve_map_source_definition.assert_called_once_with("openaip", None)

    @patch(
        "display.forms.resolve_map_source_definition",
        return_value={"label": "Uploaded map", "min_zoom": 7, "max_zoom": 13},
    )
    def test_validate_map_zoom_level_accepts_uploaded_token(self, mock_resolve_map_source_definition):
        validate_map_zoom_level("user_uploaded:42", None, 10)
        mock_resolve_map_source_definition.assert_called_once_with("user_uploaded:42", None)

    def test_build_flight_order_map_plot_kwargs_uses_only_unified_map_source(self):
        self.configuration.map_source = "user_uploaded:42"

        kwargs = build_flight_order_map_plot_kwargs(self.navigation_task, self.configuration, contestant=None)

        self.assertEqual(kwargs["map_source"], "user_uploaded:42")
        self.assertNotIn("user_map_source", kwargs)

    def test_resolve_map_source_definition_for_uploaded_map_uses_uploaded_metadata(self):
        class UploadedMap:
            pk = 42
            name = "Uploaded map"
            attribution = "Uploaded attribution"
            minimum_zoom_level = 7
            maximum_zoom_level = 13
            default_zoom_level = 10
            published_service_key = "user-uploaded-map-42"
            bounds = None

        source = resolve_map_source_definition("ignored", UploadedMap())

        self.assertEqual(source["provider"], "user_uploaded_mbtiles")
        self.assertEqual(source["key"], "user_uploaded:42")
        self.assertEqual(source["label"], "Uploaded map")
        self.assertEqual(source["min_zoom"], 7)
        self.assertEqual(source["max_zoom"], 13)
        self.assertEqual(source["default_zoom"], 10)
        self.assertEqual(
            source["tile_url"],
            "http://localhost:8001/services/user-uploaded-map-42/tiles/{z}/{x}/{y}.png",
        )
