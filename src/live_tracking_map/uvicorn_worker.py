"""Gunicorn worker class for the combined HTTP + websocket app server.

Gunicorn can only pass a handful of settings through to uvicorn, and several
of uvicorn's websocket defaults differ from how daphne behaved when websockets
ran in their own deployment. This subclass pins the ones that matter so the
merge doesn't silently change on-the-wire behaviour for live tracking clients.
"""

from uvicorn_worker import UvicornWorker


class ASLTUvicornWorker(UvicornWorker):
    CONFIG_KWARGS = {
        # Both are installed via uvicorn[standard]. Pinning them avoids a
        # silent fallback to the slower asyncio/h11 implementations.
        "loop": "uvloop",
        "http": "httptools",
        "ws": "websockets",
        # live_tracking_map.asgi's ProtocolTypeRouter has no "lifespan" key and
        # raises on unknown scope types, so uvicorn's "auto" logs a spurious
        # error banner on every start.
        "lifespan": "off",
        # Daphne applied no ping-driven disconnect. uvicorn's 20s pong deadline
        # would drop marginal mobile/airborne clients that used to survive;
        # 60s keeps dead-peer detection without punishing a bad link.
        "ws_ping_interval": 20.0,
        "ws_ping_timeout": 60.0,
        # Daphne did not negotiate permessage-deflate. Leaving uvicorn's
        # default on would allocate zlib contexts per connection - real memory
        # at a few thousand concurrent tracking sockets, for little gain on
        # small JSON frames.
        "ws_per_message_deflate": False,
        "ws_max_queue": 64,
    }
