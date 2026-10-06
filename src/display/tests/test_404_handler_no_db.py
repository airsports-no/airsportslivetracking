"""
A 404 must not touch the database: scanner probes of nonexistent paths (e.g. /api.php) used to
raise "MySQL server has gone away" from guardian's permission lookup while rendering the 404 page.
"""

from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection

from display.views import page_not_found


class PageNotFoundHandlerTest(TestCase):
    def test_renders_404_without_queries(self):
        with CaptureQueriesContext(connection) as queries:
            response = page_not_found(None)
        self.assertEqual(404, response.status_code)
        self.assertIn(b"does not exist", response.content)
        self.assertEqual([], list(queries))

    def test_handler404_is_registered(self):
        from live_tracking_map import urls

        self.assertIs(page_not_found, urls.handler404)
