"""
Regression test for websocket finding #4 (2026-08-28 review): ContestResultsConsumer.connect
sent the initial teams/tasks/tests dump via WebsocketFacade.transmit_teams/tasks/tests, which
group_send to the whole contestresults_<pk> group - every already-connected viewer got a
redundant full dump whenever *anyone* else connected, O(N^2) messages for N simultaneous
viewers. Combined with a flat no-backoff reconnect retry and a bounded channel-layer capacity,
this self-amplifies into a reconnect storm exactly when a pod rollout closes every socket at once
during a live contest.
"""

import datetime

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from display.consumers import ContestResultsConsumer
from display.models import Contest


class TestContestResultsConsumerNoBroadcastAmplification(TransactionTestCase):
    def setUp(self):
        self.contest = Contest.objects.create(
            name="Public Results Contest",
            is_public=True,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            location="60, 11",
        )

    def test_a_new_connection_does_not_re_broadcast_to_already_connected_viewers(self):
        async def _run():
            path = f"/ws/contestresults/{self.contest.pk}/"
            kwargs = {"contest_pk": self.contest.pk}

            first = WebsocketCommunicator(ContestResultsConsumer.as_asgi(), path)
            first.scope["user"] = AnonymousUser()
            first.scope["url_route"] = {"kwargs": kwargs}
            connected, _ = await first.connect()
            assert connected

            # The first viewer's own initial dump: contest.teams, contest.tasks, contest.tests.
            for _ in range(3):
                await first.receive_json_from()

            second = WebsocketCommunicator(ContestResultsConsumer.as_asgi(), path)
            second.scope["user"] = AnonymousUser()
            second.scope["url_route"] = {"kwargs": kwargs}
            connected, _ = await second.connect()
            assert connected

            # The second viewer gets its own initial dump...
            for _ in range(3):
                await second.receive_json_from()

            # ...but the first viewer must NOT receive anything more - the pre-fix bug
            # group_send the second viewer's dump to the whole group, including viewer one.
            assert await first.receive_nothing(timeout=1), "first viewer received an unexpected extra message"

            await first.disconnect()
            await second.disconnect()

        async_to_sync(_run)()
