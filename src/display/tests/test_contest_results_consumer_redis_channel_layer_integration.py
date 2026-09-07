"""
Integration test for the real Redis-backed Channels layer (channels_redis.core.RedisChannelLayer).

Every other websocket consumer test in this project runs under IS_UNIT_TESTING, which swaps
CHANNEL_LAYERS to channels.layers.InMemoryChannelLayer (see settings.py) to avoid Redis I/O in
the rest of the suite. That means none of them ever exercise the real redis-py client's async
blocking-pop path - exactly the path that broke in production when redis-py 7.1.0 was bumped to
8.1.0 (RESP3-by-default) in #767.

Root cause (confirmed by direct reproduction, not guessed): channels_redis.core.RedisChannelLayer
polls each channel with a plain blocking BZPOPMIN with brpop_timeout=5s
(_brpop_with_clean -> connection.bzpopmin(channel, timeout=5)), and its receive() loop treats a
timed-out pop (Redis returning nil after 5s of nothing to read - completely normal for an idle
websocket) as "no message yet, keep waiting". Under redis-py 8.1.0, that same legitimate 5s
timeout instead surfaces as redis.exceptions.TimeoutError propagating out of receive(), because
redis-py 8's async client no longer distinguishes "server replied nil after the requested
blocking timeout" from "the socket read itself timed out". Every idle connected websocket hits
this every ~5 seconds, which is exactly the "23 events in 3 minutes, escalating" pattern Sentry
reported: channels.utils.await_many_dispatch (consumer.py's per-connection receive loop, wrapping
this same call) raising TimeoutError: Timeout reading from <host>:6379.

This test forces the real RedisChannelLayer (the actual settings.CHANNEL_LAYERS config, not the
in-memory test override), leaves a channel idle past the 5s brpop_timeout, and asserts receive()
does NOT raise - so a future redis-py bump that reintroduces this fails here in ~5 seconds
instead of in production websocket delivery.
"""

import asyncio

from django.test import SimpleTestCase, override_settings

from live_tracking_map.settings import CELERY_BROKER_URL

REAL_REDIS_CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [CELERY_BROKER_URL],
            "capacity": 100,
            "expiry": 30,
        },
    }
}


@override_settings(CHANNEL_LAYERS=REAL_REDIS_CHANNEL_LAYERS)
class TestRedisChannelLayerIdlePollTimeout(SimpleTestCase):
    def test_idle_channel_receive_does_not_raise_past_the_brpop_timeout(self):
        from channels_redis.core import RedisChannelLayer

        async def _run():
            layer = RedisChannelLayer(hosts=[CELERY_BROKER_URL])
            self.assertEqual(layer.brpop_timeout, 5)
            channel = await layer.new_channel()

            # Nothing is ever published to this channel. A correctly-behaving layer just
            # keeps polling forever; the production regression raised
            # redis.exceptions.TimeoutError right around the 5s brpop_timeout mark instead.
            with self.assertRaises(asyncio.TimeoutError):
                # asyncio.TimeoutError here means receive() is still waiting after
                # brpop_timeout + margin - the correct, healthy behavior. Any other
                # exception (in particular redis.exceptions.TimeoutError) is the bug.
                await asyncio.wait_for(layer.receive(channel), timeout=layer.brpop_timeout + 2)

        asyncio.run(_run())
