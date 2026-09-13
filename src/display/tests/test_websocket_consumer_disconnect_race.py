"""Regression test for Sentry PYTHON-DJANGO-13: a group-handler message (tracking_data,
contestresults, etc.) can still be queued on ParallelDispatchMixin's thread pool after its client
has already disconnected - by the time the handler runs and calls send(), the underlying ASGI
connection is gone, and uvicorn's asgi_send raises RuntimeError for that. This is an ordinary
disconnect race, not a bug, so ParallelDispatchMixin.send() must swallow it instead of letting it
surface as an unhandled exception for every reconnect/tab-close that happens to race a pending
message. See the matching comment in consumers.py.
"""

from unittest.mock import patch

from django.test import SimpleTestCase

from display.consumers import TrackingConsumer


class TestParallelDispatchMixinSendSwallowsDisconnectRace(SimpleTestCase):
    def test_send_after_client_disconnect_does_not_raise(self):
        consumer = TrackingConsumer()

        with patch(
            "channels.generic.websocket.WebsocketConsumer.send",
            side_effect=RuntimeError(
                "Unexpected ASGI message 'websocket.send', after sending 'websocket.close' or response already completed."
            ),
        ):
            consumer.send(text_data="{}")  # must not raise

    def test_unrelated_errors_from_send_still_propagate(self):
        # Only RuntimeError (the disconnect race) is swallowed - this is not a blanket
        # try/except around every send() call.
        consumer = TrackingConsumer()

        with patch("channels.generic.websocket.WebsocketConsumer.send", side_effect=ValueError("boom")):
            with self.assertRaises(ValueError):
                consumer.send(text_data="{}")
