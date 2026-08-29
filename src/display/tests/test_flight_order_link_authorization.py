"""
Regression test for a critical finding (2026-08-28/29 security review, flight-order module +
templates reviews, independently confirmed 3x): get_contestant_email_flying_orders_link had no
authorization at all - sequential integer contestant pks made every contestant's flight order
(route maps, gate times, crew details, and for unknown-legs/CIMA tasks the turning-point answer
key for an unflown task) trivially downloadable by an anonymous visitor, and each hit ran full
PDF/map generation synchronously (a free DoS lever).
"""

import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Aeroplane, Contest, Contestant, Crew, EditableRoute, NavigationTask, Person, Team
from utilities.mock_utilities import TraccarMock


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestFlightOrderLinkAuthorization(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        scorecard = get_default_scorecard()
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Test", file.readlines()[1:])
            route = editable_route.create_precision_route(True, scorecard)
        self.contest = Contest.objects.create(
            name="Private contest",
            is_public=False,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            location="60, 11",
        )
        now = datetime.datetime.now(datetime.timezone.utc)
        navigation_task = NavigationTask.create(
            name="Test task",
            original_scorecard=scorecard,
            minutes_to_starting_point=5,
            minutes_to_landing=20,
            route=route,
            contest=self.contest,
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="A", last_name="B", email="a@example.com"))
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-AAA"))
        self.contestant = Contestant.objects.create(
            team=team,
            navigation_task=navigation_task,
            takeoff_time=now + datetime.timedelta(hours=1),
            finished_by_time=now + datetime.timedelta(hours=2),
            tracker_start_time=now + datetime.timedelta(minutes=30),
            tracker_device_id="test_device",
            contestant_number=1,
        )
        self.url = reverse("email_report_link", kwargs={"pk": self.contestant.pk})

        self.outsider = get_user_model().objects.create(email="outsider@example.com")
        self.organizer = get_user_model().objects.create(email="organizer@example.com")
        assign_perm("view_contest", self.organizer, self.contest)

    def test_anonymous_user_cannot_download_flight_order(self, *args):
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 200)

    def test_authenticated_outsider_cannot_download_flight_order(self, *args):
        self.client.force_login(user=self.outsider)
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 200)

    @patch("display.views.generate_flight_orders")
    def test_organizer_with_view_permission_can_download_flight_order(self, mock_generate, *args):
        mock_generate.return_value = b"%PDF-fake"
        self.client.force_login(user=self.organizer)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        mock_generate.assert_called_once()
