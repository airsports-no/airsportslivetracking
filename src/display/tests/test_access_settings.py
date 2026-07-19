from django.test import SimpleTestCase, override_settings

from live_tracking_map.settings import _parse_optional_int_env


class TestAccessSettings(SimpleTestCase):
    @override_settings()
    def test_parser_returns_none_for_unlimited_markers(self):
        self.assertIsNone(_parse_optional_int_env("MISSING_LIMIT"))

    def test_parser_converts_numeric_string(self):
        import os

        os.environ["TEST_LIMIT"] = "42"
        try:
            self.assertEqual(42, _parse_optional_int_env("TEST_LIMIT"))
        finally:
            os.environ.pop("TEST_LIMIT", None)
