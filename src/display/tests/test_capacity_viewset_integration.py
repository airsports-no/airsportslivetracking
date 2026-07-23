from unittest.mock import patch
import datetime

from django.contrib.auth import get_user_model
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Contest, NavigationTask, EditableRoute, ContestTeam, Crew, Person, Team, Aeroplane
from rest_framework.exceptions import ValidationError as DRFValidationError
from utilities.mock_utilities import TraccarMock


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestCapacityViewsetIntegration(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="owner@example.com")
        self.client.force_login(self.user)
        self.contest = Contest.objects.create(
            name="Integration Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 4, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 4, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
        )
        self.contest.make_public()
        self.contest.created_by = self.user
        self.contest.save(update_fields=["created_by"])
        assign_perm("view_contest", self.user, self.contest)
        assign_perm("change_contest", self.user, self.contest)
        self.person = Person.objects.create(first_name="Pilot", last_name="One", email=self.user.email)
        self.team = Team.objects.create(
            crew=Crew.objects.create(member1=self.person),
            aeroplane=Aeroplane.objects.create(registration="LN-INT"),
        )
        self.contest_team = ContestTeam.objects.create(contest=self.contest, team=self.team)
        self.scorecard = get_default_scorecard()
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Test", file.readlines()[1:])
            self.route = editable_route.create_precision_route(True, self.scorecard)
        self.navigation_task = NavigationTask.create(
            name="Integration Task",
            original_scorecard=self.scorecard,
            contest=self.contest,
            route=self.route,
            start_time="2026-04-01T09:00:00+00:00",
            finish_time="2026-04-01T17:00:00+00:00",
            allow_self_management=True,
        )
        self.navigation_task.is_public = True
        self.navigation_task.save()

    @patch("display.viewsets.assert_can_register_team")
    def test_signup_no_longer_calls_capacity_guard(self, mock_guard, *_args):
        url = reverse("contests-signup", kwargs={"pk": self.contest.id})
        response = self.client.post(
            url,
            {
                "club_name": "Club",
                "aircraft_registration": "LN-INT",
                "airspeed": 70,
                "copilot_id": None,
            },
            format="json",
        )

        self.assertNotEqual(status.HTTP_500_INTERNAL_SERVER_ERROR, response.status_code)
        mock_guard.assert_not_called()

    @patch("display.viewsets.scheduling_capacity_preview")
    def test_schedule_capacity_preview_endpoint_returns_authoritative_preview(self, mock_preview, *_args):
        mock_preview.return_value = {
            "contestant_limit": 2,
            "reserved_before_count": 1,
            "reserved_after_count": 3,
            "additional_selected_count": 2,
            "remaining_before_count": 1,
            "remaining_after_count": 0,
            "would_exceed": True,
        }
        url = reverse(
            "navigationtasks-schedule-capacity-preview",
            kwargs={"contest_pk": self.contest.id, "pk": self.navigation_task.id},
        )
        response = self.client.get(
            url,
            {
                "contest_teams": str(self.contest_team.pk),
                "first_takeoff_time": "2026-04-01T10:00:00Z",
            },
        )

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(True, response.data["would_exceed"])
        self.assertEqual(3, response.data["reserved_after_count"])

    @patch("display.viewsets._assert_can_reserve_task_slot")
    @patch("display.viewsets.assert_can_self_register_contestant")
    def test_self_registration_calls_capacity_guard(self, mock_guard, mock_task_guard, *_args):
        url = reverse(
            "navigationtasks-contestant-self-registration",
            kwargs={"contest_pk": self.contest.id, "pk": self.navigation_task.id},
        )
        response = self.client.put(
            url,
            {
                "starting_point_time": "2026-04-01T10:00:00Z",
                "contest_team": self.contest_team.pk,
                "adaptive_start": False,
                "wind_speed": 5,
                "wind_direction": 170,
            },
            format="json",
        )

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        mock_guard.assert_called_once()
        mock_task_guard.assert_not_called()
