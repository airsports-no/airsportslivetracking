"""
Regression test (CodeRabbit review of PR #734, finding on map_plotter.py:380): MyGoogleWTS.
get_image() disk-caches every successfully-decoded image, including the blank fallback tile
produced after a fetch failure/429. A later get_image() call for the same tile coordinate would
then load that cached blank tile via the `if cached_file in self.cache` branch - incrementing
_tile_fetch_count but not _blank_tile_count, since that branch never runs the failure-handling
code that increments it. A map built entirely from such cached fallback tiles would silently
pass check_tile_fetch_health() (see test_map_tile_fetch_health.py) instead of being rejected.

cache_path is never enabled by any caller in map_plotter.py today (no instantiation passes
cache=), so this is currently unreachable in production - fixed anyway so it stays correct if
that ever changes, since it would otherwise silently defeat the finding #3 fix.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from django.test import TestCase

from display.flight_order_and_maps.map_plotter import AirsportsOSM


class TestMapTileFallbackNotCached(TestCase):
    def test_a_fallback_blank_tile_is_not_written_to_the_disk_cache(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            imagery = AirsportsOSM(user_agent="airsports.no, support@airsports.no", cache=tmp_dir)

            response = MagicMock()
            response.status_code = 429
            response.content = b""

            import display.flight_order_and_maps.map_plotter as map_plotter_module

            original_requests_get = map_plotter_module.requests.get
            map_plotter_module.requests.get = MagicMock(return_value=response)
            try:
                imagery.get_image((1, 2, 3))
            finally:
                map_plotter_module.requests.get = original_requests_get

            self.assertEqual(imagery._blank_tile_count, 1)
            cached_files = list(Path(tmp_dir).rglob("*.npy"))
            self.assertEqual(
                cached_files,
                [],
                "A fallback/blank tile must never be written to the disk cache - a later "
                "get_image() call for the same coordinate would load it as if it were real "
                "imagery, silently under-counting _blank_tile_count on that later call.",
            )
