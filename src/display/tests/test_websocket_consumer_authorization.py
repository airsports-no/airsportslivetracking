"""
Regression tests for the critical finding (2026-08-28 security review): TrackingConsumer and
ContestResultsConsumer only checked that the target row existed, not its visibility - so any
anonymous websocket client could subscribe to a private/unlisted navigation task's live
positions or a private contest's results by guessing its pk. Fixed to require the same
visibility rule as the REST equivalents: public, or the connecting user holds view_contest.
"""

import datetime

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase
from guardian.shortcuts import assign_perm

from display.consumers import ContestResultsConsumer, TrackingConsumer
from display.models import Contest, NavigationTask, Route, Scorecard
from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard


def _connect(consumer_class, path, url_route_kwargs, user):
    async def _run():
        communicator = WebsocketCommunicator(consumer_class.as_asgi(), path)
        communicator.scope["user"] = user
        communicator.scope["url_route"] = {"kwargs": url_route_kwargs}
        connected, _ = await communicator.connect()
        if connected:
            await communicator.disconnect()
        return connected

    return async_to_sync(_run)()


class TestWebsocketConsumerAuthorization(TransactionTestCase):
    def setUp(self):
        self.scorecard = get_default_scorecard()
        self.route = Route.objects.create(name="Test route")
        self.contest = Contest.objects.create(
            name="Private contest",
            is_public=False,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            location="60, 11",
        )
        now = datetime.datetime.now(datetime.timezone.utc)
        self.navigation_task = NavigationTask.create(
            name="Private task",
            original_scorecard=self.scorecard,
            minutes_to_starting_point=5,
            minutes_to_landing=20,
            route=self.route,
            contest=self.contest,
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
            is_public=False,
        )
        self.outsider = get_user_model().objects.create(email="outsider@example.com")
        self.organizer = get_user_model().objects.create(email="organizer@example.com")
        assign_perm("view_contest", self.organizer, self.contest)

    def test_anonymous_user_rejected_from_private_task_tracking(self):
        connected = _connect(
            TrackingConsumer,
            f"/ws/tracks/{self.navigation_task.pk}/",
            {"navigation_task": self.navigation_task.pk},
            AnonymousUser(),
        )
        self.assertFalse(connected)

    def test_outsider_rejected_from_private_task_tracking(self):
        connected = _connect(
            TrackingConsumer,
            f"/ws/tracks/{self.navigation_task.pk}/",
            {"navigation_task": self.navigation_task.pk},
            self.outsider,
        )
        self.assertFalse(connected)

    def test_organizer_with_view_permission_allowed_into_private_task_tracking(self):
        connected = _connect(
            TrackingConsumer,
            f"/ws/tracks/{self.navigation_task.pk}/",
            {"navigation_task": self.navigation_task.pk},
            self.organizer,
        )
        self.assertTrue(connected)

    def test_anyone_allowed_into_public_task_tracking(self):
        self.navigation_task.is_public = True
        self.navigation_task.save()
        self.contest.is_public = True
        self.contest.save()
        connected = _connect(
            TrackingConsumer,
            f"/ws/tracks/{self.navigation_task.pk}/",
            {"navigation_task": self.navigation_task.pk},
            AnonymousUser(),
        )
        self.assertTrue(connected)

    def test_anonymous_user_rejected_from_private_contest_results(self):
        connected = _connect(
            ContestResultsConsumer,
            f"/ws/contestresults/{self.contest.pk}/",
            {"contest_pk": self.contest.pk},
            AnonymousUser(),
        )
        self.assertFalse(connected)

    def test_organizer_with_view_permission_allowed_into_private_contest_results(self):
        connected = _connect(
            ContestResultsConsumer,
            f"/ws/contestresults/{self.contest.pk}/",
            {"contest_pk": self.contest.pk},
            self.organizer,
        )
        self.assertTrue(connected)

    def test_anyone_allowed_into_public_contest_results(self):
        self.contest.is_public = True
        self.contest.save()
        connected = _connect(
            ContestResultsConsumer,
            f"/ws/contestresults/{self.contest.pk}/",
            {"contest_pk": self.contest.pk},
            AnonymousUser(),
        )
        self.assertTrue(connected)
