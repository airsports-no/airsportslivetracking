"""
Regression test for calculators finding #2 (2026-08-28 review): calculator_pool_scaler's
"independent floor" (running + queued) wasn't actually independent of the schedule query -
count_running(scheduled_pks) can only ever report a subset of whatever pks the schedule query
just produced, so running <= len(scheduled_pks) always. count_all_running fixes this by scanning
the cache DB directly for every CALCULATOR_RUNNING_* heartbeat key, regardless of whether its
contestant is still in any particular schedule query's result.
"""

import redis
from django.test import SimpleTestCase

from display.utilities.calculator_running_utilities import KEY_BASE, calculator_is_alive, calculator_is_terminated, count_all_running
from live_tracking_map import settings

# Deliberately implausible pks, unlikely to collide with any real Contestant heartbeat left
# behind by other tests running against the same Redis cache DB.
PK_A = 90_000_001
PK_B = 90_000_002


class TestCountAllRunning(SimpleTestCase):
    def setUp(self):
        self.redis_connection = redis.Redis.from_url(settings.REDIS_CACHE_URL)
        calculator_is_terminated(PK_A)
        calculator_is_terminated(PK_B)
        self.baseline = count_all_running(self.redis_connection)

    def tearDown(self):
        calculator_is_terminated(PK_A)
        calculator_is_terminated(PK_B)

    def test_counts_a_heartbeat_regardless_of_any_schedule_query(self):
        # count_all_running takes no pks at all - it can't be scoped down to "only the ones
        # some other query already decided to look at", unlike count_running(scheduled_pks).
        calculator_is_alive(PK_A, 30)
        calculator_is_alive(PK_B, 30)

        self.assertEqual(count_all_running(self.redis_connection), self.baseline + 2)

    def test_terminated_calculator_is_not_counted(self):
        calculator_is_alive(PK_A, 30)
        self.assertEqual(count_all_running(self.redis_connection), self.baseline + 1)

        calculator_is_terminated(PK_A)
        self.assertEqual(count_all_running(self.redis_connection), self.baseline)
