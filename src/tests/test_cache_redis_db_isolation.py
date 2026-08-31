"""
Regression test for the critical finding (2026-08-28 security review): Django's cache
("default", used for calculator heartbeats/dispatch-pending markers) used to share the same
Redis logical DB as the Celery broker, the Channels layer, and RedisQueue's position lists.
cache.clear() (called unconditionally on every tracker-processor start, and in tests) issues a
raw FLUSHDB, which wiped all of those alongside the cache. Fixed by giving the cache its own
Redis DB (settings.REDIS_CACHE_URL) - this locks in that cache.clear() no longer touches data
living on the broker/RedisQueue DB.
"""

from django.core.cache import cache
from django.test import TestCase

from live_tracking_map.settings import CELERY_BROKER_URL, REDIS_CACHE_URL
from redis_queue import RedisQueue


class TestCacheRedisDbIsolation(TestCase):
    def test_cache_location_is_not_the_broker_url(self):
        # Guards against someone "simplifying" CACHES back to reusing CELERY_BROKER_URL.
        self.assertNotEqual(REDIS_CACHE_URL, CELERY_BROKER_URL)
        self.assertTrue(REDIS_CACHE_URL.endswith("/1"))

    def test_cache_clear_does_not_wipe_redis_queue_data(self):
        queue = RedisQueue("test_cache_isolation_contestant")
        self.addCleanup(lambda: queue.redis_handle.delete(queue.queue_name))
        queue.append({"marker": "should survive cache.clear()"})
        self.assertEqual(queue.size, 1)

        cache.set("some_heartbeat_key", True, timeout=30)
        self.assertTrue(cache.get("some_heartbeat_key"))

        cache.clear()

        self.assertIsNone(cache.get("some_heartbeat_key"))
        self.assertEqual(queue.size, 1)
        self.assertEqual(queue.pop()["marker"], "should survive cache.clear()")
