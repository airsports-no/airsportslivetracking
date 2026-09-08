"""
Integration test for the real Redis-backed Channels layer (channels_redis.core.RedisChannelLayer).

Every other websocket consumer test in this project runs under IS_UNIT_TESTING, which swaps
CHANNEL_LAYERS to channels.layers.InMemoryChannelLayer (see settings.py) to avoid Redis I/O in
the rest of the suite. That means none of them ever exercise the real redis-py client's async
blocking-pop path - exactly the path that broke in production when redis-py 7.1.0 was first
bumped to 8.1.0 (RESP3-by-default) in #767.

Root cause (confirmed upstream: redis/redis-py#4091, closed as completed): redis-py 8.0 changed
its default socket_timeout from None (wait indefinitely) to 5 seconds. channels_redis separately
defaults its own blocking-pop timeout to 5 seconds too (_brpop_with_clean ->
connection.bzpopmin(channel, timeout=5)). Those two timers race: when a channel is idle, the
client's own socket-read timeout can fire at essentially the same moment the server would have
returned its normal empty BZPOPMIN response, so redis-py raises
redis.exceptions.TimeoutError instead of channels_redis's receive() loop getting the clean "no
message yet" result it expects. Every idle connected websocket hit this every ~5 seconds, which
is exactly the "23 events in 3 minutes, escalating" pattern Sentry reported.

Fix: CHANNEL_LAYERS' hosts entry in settings.py explicitly sets socket_timeout=None, restoring
the pre-8.0 default so only the server-side BZPOPMIN timeout ever fires.

This test uses live_tracking_map.settings.REDIS_CHANNEL_LAYER_HOSTS directly - the actual
connection config CHANNEL_LAYERS is built from (not a hand-copied duplicate, so it can never
drift out of sync with the real fix; CHANNEL_LAYERS itself isn't usable here since
IS_UNIT_TESTING swaps it to the in-memory backend) - leaves a channel idle past the 5s
brpop_timeout, and asserts receive() does NOT raise - so losing the socket_timeout fix, or a
future redis-py bump that reintroduces this race some other way, fails here in ~5 seconds instead
of in production websocket delivery.
"""

import asyncio

from django.test import SimpleTestCase

from live_tracking_map.settings import REDIS_CHANNEL_LAYER_HOSTS


class TestRedisChannelLayerIdlePollTimeout(SimpleTestCase):
    def test_idle_channel_receive_does_not_raise_past_the_brpop_timeout(self):
        from channels_redis.core import RedisChannelLayer

        assert REDIS_CHANNEL_LAYER_HOSTS[0].get("socket_timeout") is None, (
            "CHANNEL_LAYERS hosts must set socket_timeout=None (see redis/redis-py#4091) - "
            "otherwise this test can't tell the fix from the bug it's guarding against."
        )

        async def _run():
            layer = RedisChannelLayer(hosts=REDIS_CHANNEL_LAYER_HOSTS)
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
