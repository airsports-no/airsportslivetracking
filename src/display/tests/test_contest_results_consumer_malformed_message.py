"""
Regression test for websocket finding #9 (2026-08-28 review): ContestResultsConsumer.receive
did an unguarded json.loads(text_data) on client input - unlike TrackingConsumer.receive, which
already guards the same call. A JSONDecodeError propagated out uncaught, so
websocket_disconnect never dispatched and group_discard never ran: the dead channel stayed
registered in the contestresults_<pk> group until the 24h default group_expiry, receiving
group sends nobody reads. Trivially reachable by any client sending non-JSON text.
"""

import datetime

from asgiref.sync import async_to_sync, sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from display.consumers import ContestResultsConsumer
from display.models import Contest


class TestContestResultsConsumerMalformedMessage(TransactionTestCase):
    def setUp(self):
        self.contest = Contest.objects.create(
            name="Malformed Message Contest",
            is_public=True,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            location="60, 11",
        )

    def test_non_json_message_does_not_kill_the_connection_or_leak_it_out_of_the_group(self):
        async def _run():
            path = f"/ws/contestresults/{self.contest.pk}/"
            kwargs = {"contest_pk": self.contest.pk}

            communicator = WebsocketCommunicator(ContestResultsConsumer.as_asgi(), path)
            communicator.scope["user"] = AnonymousUser()
            communicator.scope["url_route"] = {"kwargs": kwargs}
            connected, _ = await communicator.connect()
            assert connected

            # Its own initial dump: contest.teams, contest.tasks, contest.tests.
            for _ in range(3):
                await communicator.receive_json_from()

            # Pre-fix, this raised JSONDecodeError out of receive(), which Channels'
            # dispatch treats as a crashed consumer - the socket never gets a clean
            # websocket_disconnect, so group_discard is never called.
            await communicator.send_to(text_data="not valid json")

            # The connection must still be alive and still registered in the group -
            # prove it by broadcasting to the group and confirming this socket gets it.
            from websocket_channels import WebsocketFacade

            ws = WebsocketFacade()
            await sync_to_async(ws.transmit_teams)(self.contest)
            message = await communicator.receive_json_from(timeout=2)
            assert message is not None

            await communicator.disconnect()

        async_to_sync(_run)()
