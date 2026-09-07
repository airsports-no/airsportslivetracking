"""
Regression test for PYTHON-DJANGO-4 (Sentry, 2026-09-07): a stray websocket connection to an
unrouted path (e.g. "" - a health-check probe or bot hitting "/" with a websocket Upgrade
header) made channels.routing.URLRouter.__call__ raise ValueError("No route found for path %r"),
which Sentry logged as an unhandled-looking production exception for a request that was never
going to be valid. UnroutedWebsocketConsumer is a catch-all (last entry in
display.routing.websocket_urlpatterns) that closes the handshake cleanly instead.
"""

from asgiref.sync import async_to_sync
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator

from display.routing import websocket_urlpatterns


class TestUnroutedWebsocketPath:
    def test_empty_path_is_closed_cleanly_not_raised(self):
        async def _run():
            router = URLRouter(websocket_urlpatterns)
            communicator = WebsocketCommunicator(router, "")
            connected, subprotocol_or_close_code = await communicator.connect()
            assert connected is False
            await communicator.disconnect()

        async_to_sync(_run)()

    def test_random_unrouted_path_is_closed_cleanly_not_raised(self):
        async def _run():
            router = URLRouter(websocket_urlpatterns)
            communicator = WebsocketCommunicator(router, "some/random/path")
            connected, subprotocol_or_close_code = await communicator.connect()
            assert connected is False
            await communicator.disconnect()

        async_to_sync(_run)()
