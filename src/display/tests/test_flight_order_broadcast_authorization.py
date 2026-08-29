"""
Regression test for REST API finding #12 (2026-08-28 review): generate_navigation_task_orders
and broadcast_navigation_task_orders only required display.view_contest, despite deleting every
selected contestant's existing flight-order links and (re-)triggering generation/notification
emails to the whole start list. A read-only collaborator could invalidate all distributed
flight-order links and mail-bomb every contestant.
"""

import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Aeroplane, Contest, Contestant, Crew, EmailMapLink, NavigationTask, Person, Route, Team
from utilities.mock_utilities import TraccarMock


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestFlightOrderBroadcastAuthorization(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        self.contest = Contest.objects.create(
            name="Broadcast Contest",
            is_public=False,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            location="60, 11",
        )
        route = Route.objects.create(name="Route")
        now = datetime.datetime.now(datetime.timezone.utc)
        self.navigation_task = NavigationTask.create(
            name="Broadcast Task",
            original_scorecard=get_default_scorecard(),
            route=route,
            contest=self.contest,
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="A", last_name="B", email="pilot@example.com"))
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-BCT"))
        self.contestant = Contestant.objects.create(
            team=team,
            navigation_task=self.navigation_task,
            takeoff_time=now + datetime.timedelta(hours=1),
            finished_by_time=now + datetime.timedelta(hours=2),
            tracker_start_time=now + datetime.timedelta(minutes=30),
            tracker_device_id="test_device",
            contestant_number=1,
        )
        self.email_link = EmailMapLink.objects.create(contestant=self.contestant, orders=b"%PDF-existing")

        self.viewer = get_user_model().objects.create(email="viewer@example.com")
        assign_perm("view_contest", self.viewer, self.contest)
        self.manager = get_user_model().objects.create(email="manager@example.com")
        assign_perm("view_contest", self.manager, self.contest)
        assign_perm("change_contest", self.manager, self.contest)

        self.generate_url = (
            reverse("navigationtask_generateflightorders", kwargs={"pk": self.navigation_task.pk})
            + f"?contestant_pks={self.contestant.pk}"
        )
        self.broadcast_url = (
            reverse("navigationtask_broadcastflightorders", kwargs={"pk": self.navigation_task.pk})
            + f"?contestant_pks={self.contestant.pk}"
        )

    def test_viewer_cannot_generate_flight_orders(self, *args):
        self.client.force_login(user=self.viewer)
        response = self.client.get(self.generate_url)
        self.assertNotEqual(response.status_code, 200)
        self.assertTrue(EmailMapLink.objects.filter(pk=self.email_link.pk).exists())

    def test_viewer_cannot_broadcast_flight_orders(self, *args):
        self.client.force_login(user=self.viewer)
        response = self.client.get(self.broadcast_url)
        self.assertNotEqual(response.status_code, 200)

    @patch("display.views_api.generate_and_maybe_notify_flight_order")
    def test_manager_can_generate_flight_orders(self, mock_generate, *args):
        self.client.force_login(user=self.manager)
        response = self.client.get(self.generate_url)
        self.assertEqual(response.status_code, 200, response.content)
        mock_generate.apply_async.assert_called_once()

    @patch("display.views_api.notify_flight_order")
    def test_manager_can_broadcast_flight_orders(self, mock_notify, *args):
        self.client.force_login(user=self.manager)
        response = self.client.get(self.broadcast_url)
        self.assertEqual(response.status_code, 200, response.content)
        mock_notify.apply_async.assert_called_once()
