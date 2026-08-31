"""
Regression test for websocket finding #3 (2026-08-28 review): all sync-consumer dispatch on a
pod (TrackingConsumer, AirsportsPositionsConsumer, ContestResultsConsumer - every event: connect,
receive, disconnect, every group-handler call) was pinned to a single shared thread
(asgiref.sync.SyncToAsync.single_thread_executor, thread_sensitive=True is Channels'
SyncConsumer.dispatch default, and Channels never establishes a per-connection
ThreadSensitiveContext to opt out). A slow handler on one connection blocked every other
connection's message processing on the same pod, including simple ping/pong keepalives - which
can cascade into a mass-reconnect storm right when a pod rollout already closed every socket at
once.

This proves TRUE parallelism, not just that messages eventually arrive: while one connection's
connect() handler is deliberately blocked mid-flight, a completely separate connection must still
be able to connect and get a ping answered - pre-fix, that second connection's dispatch() call
would queue behind the still-blocked first one on the single shared thread and never complete in
time.
"""

import asyncio
import datetime
import json
import threading

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from display.consumers import TrackingConsumer
from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Contest, NavigationTask, Route

block_started = threading.Event()
release_block = threading.Event()


class SlowTrackingConsumer(TrackingConsumer):
    def connect(self):
        block_started.set()
        release_block.wait(timeout=5)
        super().connect()


class TestConsumerDispatchRunsInParallel(TransactionTestCase):
    def setUp(self):
        block_started.clear()
        release_block.clear()
        self.scorecard = get_default_scorecard()
        self.route = Route.objects.create(name="Parallel dispatch route")
        self.contest = Contest.objects.create(
            name="Public parallel contest",
            is_public=True,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            location="60, 11",
        )
        now = datetime.datetime.now(datetime.timezone.utc)
        self.navigation_task = NavigationTask.create(
            name="Public parallel task",
            original_scorecard=self.scorecard,
            minutes_to_starting_point=5,
            minutes_to_landing=20,
            route=self.route,
            contest=self.contest,
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
            is_public=True,
        )

    def test_a_slow_connect_does_not_block_a_different_connections_ping(self):
        async def _run():
            path = f"/ws/tracks/{self.navigation_task.pk}/"
            kwargs = {"navigation_task": self.navigation_task.pk}

            slow = WebsocketCommunicator(SlowTrackingConsumer.as_asgi(), path)
            slow.scope["user"] = AnonymousUser()
            slow.scope["url_route"] = {"kwargs": kwargs}
            slow_connect_task = asyncio.ensure_future(slow.connect())

            # Wait until the slow connection's dispatch() has actually started executing
            # (and is now blocked mid-handler) before touching the second connection.
            loop = asyncio.get_event_loop()
            started = await loop.run_in_executor(None, block_started.wait, 5)
            assert started, "slow connection's handler never started"

            fast = WebsocketCommunicator(TrackingConsumer.as_asgi(), path)
            fast.scope["user"] = AnonymousUser()
            fast.scope["url_route"] = {"kwargs": kwargs}
            # Pre-fix, this dispatch() call queues behind the still-blocked slow one on the
            # single shared thread and this would time out.
            connected, _ = await asyncio.wait_for(fast.connect(), timeout=3)
            assert connected, "second connection could not connect while the first was blocked"

            await fast.send_to(text_data=json.dumps({"type": "ping"}))
            response = await asyncio.wait_for(fast.receive_json_from(), timeout=3)
            assert response == {"type": "pong"}, response

            release_block.set()
            connected, _ = await slow_connect_task
            assert connected

            await fast.disconnect()
            await slow.disconnect()

        async_to_sync(_run)()
