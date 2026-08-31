"""
Regression tests for the templates-section finding #7 (2026-08-28 review): several destructive
actions were exposed as plain GET links with no CSRF protection (GET isn't covered by Django's
CSRF middleware) - a one-click <img src="..."> on any page a logged-in editor visited could
silently mutate live competition state. All were already permission-checked server-side; only
the CSRF protection was missing.

Covers: contestant_remove_score_item (delete_score_item), contestant_stop_calculator
(terminate_contestant_calculator), contestant_restart_calculator (restart_contestant_calculator),
clear_profile_image_background, remove_team, renewtoken (renew_token).

navigationtask_refresheditableroute (refresh_editable_route_navigation_task) is the same finding
class, discovered separately while investigating the scorecard-system review roadmap's Phase 0
follow-ups - missed by the original batch above.
"""

import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework.authtoken.models import Token

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import (
    Aeroplane,
    Contest,
    Contestant,
    ContestTeam,
    Crew,
    NavigationTask,
    Person,
    Route,
    ScoreLogEntry,
    Team,
)
from utilities.mock_utilities import TraccarMock


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestDestructiveViewsRequirePost(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        self.contest = Contest.objects.create(
            name="CSRF Contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            location="60, 11",
        )
        route = Route.objects.create(name="Route")
        now = datetime.datetime.now(datetime.timezone.utc)
        self.navigation_task = NavigationTask.create(
            name="CSRF Task",
            original_scorecard=get_default_scorecard(),
            route=route,
            contest=self.contest,
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
        )
        self.member1 = Person.objects.create(first_name="A", last_name="B", email="csrf@example.com")
        crew = Crew.objects.create(member1=self.member1)
        self.team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-CSRF"))
        self.contest_team = ContestTeam.objects.create(contest=self.contest, team=self.team, air_speed=70)
        self.contestant = Contestant.objects.create(
            team=self.team,
            navigation_task=self.navigation_task,
            takeoff_time=now + datetime.timedelta(hours=1),
            finished_by_time=now + datetime.timedelta(hours=2),
            tracker_start_time=now + datetime.timedelta(minutes=30),
            tracker_device_id="test_device",
            contestant_number=1,
        )
        self.score_log_entry = ScoreLogEntry.objects.create(
            contestant=self.contestant, time=now, gate="", message="", string="", points=5
        )

        self.manager = get_user_model().objects.create(email="csrf-manager@example.com")
        assign_perm("view_contest", self.manager, self.contest)
        assign_perm("change_contest", self.manager, self.contest)
        self.client.force_login(user=self.manager)

    def test_delete_score_item_rejects_get(self, *args):
        url = reverse("contestant_remove_score_item", kwargs={"pk": self.score_log_entry.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)
        self.assertTrue(ScoreLogEntry.objects.filter(pk=self.score_log_entry.pk).exists())

    def test_delete_score_item_post_succeeds(self, *args):
        url = reverse("contestant_remove_score_item", kwargs={"pk": self.score_log_entry.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ScoreLogEntry.objects.filter(pk=self.score_log_entry.pk).exists())

    def test_terminate_calculator_rejects_get(self, *args):
        url = reverse("contestant_stop_calculator", kwargs={"pk": self.contestant.pk})
        with patch("display.models.contestant.Contestant.blocking_request_calculator_termination") as mock_terminate:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 405)
            mock_terminate.assert_not_called()

    def test_terminate_calculator_post_succeeds(self, *args):
        url = reverse("contestant_stop_calculator", kwargs={"pk": self.contestant.pk})
        with patch("display.models.contestant.Contestant.blocking_request_calculator_termination") as mock_terminate:
            response = self.client.post(url)
            self.assertEqual(response.status_code, 302)
            mock_terminate.assert_called_once()

    def test_restart_calculator_rejects_get(self, *args):
        url = reverse("contestant_restart_calculator", kwargs={"pk": self.contestant.pk})
        with patch("display.models.contestant.Contestant.blocking_request_calculator_termination") as mock_terminate:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 405)
            mock_terminate.assert_not_called()

    def test_restart_calculator_post_succeeds(self, *args):
        url = reverse("contestant_restart_calculator", kwargs={"pk": self.contestant.pk})
        with patch("display.models.contestant.Contestant.blocking_request_calculator_termination") as mock_terminate:
            response = self.client.post(url)
            self.assertEqual(response.status_code, 302)
            mock_terminate.assert_called_once()

    def test_clear_profile_image_background_rejects_get(self, *args):
        url = reverse("clear_profile_image_background", kwargs={"contest_pk": self.contest.pk, "pk": self.member1.pk})
        with patch("display.models.team_structure.Person.remove_profile_picture_background") as mock_remove_bg:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 405)
            mock_remove_bg.assert_not_called()

    def test_clear_profile_image_background_post_succeeds(self, *args):
        url = reverse("clear_profile_image_background", kwargs={"contest_pk": self.contest.pk, "pk": self.member1.pk})
        with patch("display.models.team_structure.Person.remove_profile_picture_background", return_value=None) as mock_remove_bg:
            response = self.client.post(url)
            self.assertEqual(response.status_code, 302)
            mock_remove_bg.assert_called_once()

    def test_remove_team_rejects_get(self, *args):
        url = reverse("remove_team", kwargs={"contest_pk": self.contest.pk, "team_pk": self.team.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)
        self.assertTrue(ContestTeam.objects.filter(pk=self.contest_team.pk).exists())

    def test_remove_team_post_succeeds(self, *args):
        url = reverse("remove_team", kwargs={"contest_pk": self.contest.pk, "team_pk": self.team.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ContestTeam.objects.filter(pk=self.contest_team.pk).exists())

    def test_renew_token_rejects_get(self, *args):
        from django.contrib.auth.models import Permission

        self.manager.user_permissions.add(Permission.objects.get(codename="change_contest"))
        url = reverse("renewtoken")
        existing = Token.objects.create(user=self.manager)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)
        self.assertTrue(Token.objects.filter(pk=existing.pk).exists())

    def test_renew_token_post_succeeds(self, *args):
        from django.contrib.auth.models import Permission

        self.manager.user_permissions.add(Permission.objects.get(codename="change_contest"))
        url = reverse("renewtoken")
        existing = Token.objects.create(user=self.manager)
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Token.objects.filter(pk=existing.pk).exists())
        self.assertTrue(Token.objects.filter(user=self.manager).exists())

    def test_refresh_editable_route_rejects_get(self, *args):
        url = reverse("navigationtask_refresheditableroute", kwargs={"pk": self.navigation_task.pk})
        with patch("display.models.navigation_task.NavigationTask.refresh_editable_route") as mock_refresh:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 405)
            mock_refresh.assert_not_called()

    def test_refresh_editable_route_post_succeeds(self, *args):
        url = reverse("navigationtask_refresheditableroute", kwargs={"pk": self.navigation_task.pk})
        with patch("display.models.navigation_task.NavigationTask.refresh_editable_route") as mock_refresh:
            response = self.client.post(url)
            self.assertEqual(response.status_code, 302)
            mock_refresh.assert_called_once()

    def test_refresh_editable_route_cross_site_post_without_csrf_token_is_rejected(self, *args):
        # A same-origin POST (Django's test Client attaches a valid CSRF cookie+token
        # automatically) still works via the test above; this proves the missing ingredient - a
        # valid CSRF token - is actually enforced now that this is POST, i.e. the view isn't
        # accidentally @csrf_exempt (which would silently defeat the whole point of this fix).
        from django.test import Client

        strict_client = Client(enforce_csrf_checks=True)
        strict_client.force_login(user=self.manager)
        url = reverse("navigationtask_refresheditableroute", kwargs={"pk": self.navigation_task.pk})
        with patch("display.models.navigation_task.NavigationTask.refresh_editable_route") as mock_refresh:
            response = strict_client.post(url)
            self.assertEqual(response.status_code, 403)
            mock_refresh.assert_not_called()
