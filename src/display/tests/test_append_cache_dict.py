from django.core.cache import cache
from django.test import TestCase
from redis.client import Redis

from display.tasks import append_cache_dict
from live_tracking_map.settings import REDIS_HOST, REDIS_PORT, REDIS_PASSWORD


class TestAppendCacheDict(TestCase):
    def setUp(self) -> None:
        self.connection = Redis(REDIS_HOST, REDIS_PORT, 2, REDIS_PASSWORD)
        append_cache_dict("my_cache", "dictionary_key", "my_value")
        self.assertDictEqual({"dictionary_key": "my_value"}, cache.get("my_cache"))
