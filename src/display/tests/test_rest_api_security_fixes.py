"""
Regression tests for the 5 critical authorization/data-exposure fixes found by the REST API
layer review on 2026-08-28 (see .review-notes/codebase_review.md, not committed - local only).
"""

import datetime

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import (
    Aeroplane,
    Contest,
    ContestTeam,
    Contestant,
    Crew,
    EditableRoute,
    NavigationTask,
    Person,
    Photo,
    Route,
    Team,
)
from utilities.mock_utilities import TraccarMock


def _make_navigation_task(contest, route, scorecard, **kwargs):
    now = datetime.datetime.now(datetime.timezone.utc)
    defaults = dict(
        name="Test task",
        original_scorecard=scorecard,
        minutes_to_starting_point=5,
        minutes_to_landing=20,
        route=route,
        contest=contest,
        start_time=now,
        finish_time=now + datetime.timedelta(days=1),
    )
    defaults.update(kwargs)
    return NavigationTask.create(**defaults)


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestDeleteSelfManagedContestantOwnership(APITestCase):
    """Finding #1: any authenticated user could delete/terminate any other pilot's contestant
    on a public self-managed task. Fix: delete_self_managed_contestant now requires the caller
    either be the contestant's own pilot, or hold delete_contest on the underlying contest."""

    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        self.scorecard = get_default_scorecard()
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Test", file.readlines()[1:])
            self.route = editable_route.create_precision_route(True, self.scorecard)
        self.contest = Contest.objects.create(
            name="contest",
            is_public=True,
            time_zone="Europe/Oslo",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            location="60, 11",
        )
        self.navigation_task = _make_navigation_task(
            self.contest, self.route, self.scorecard, allow_self_management=True, is_public=True
        )

        pilot_person = Person.objects.create(first_name="Owner", last_name="Pilot", email="owner@example.com")
        crew = Crew.objects.create(member1=pilot_person)
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-AAA"))
        self.contestant = Contestant.objects.create(
            team=team,
            navigation_task=self.navigation_task,
            takeoff_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
            finished_by_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2),
            tracker_start_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=30),
            tracker_device_id="test_device",
            contestant_number=1,
        )

        self.owner_user = get_user_model().objects.create(email="owner@example.com")
        self.stranger_user = get_user_model().objects.create(email="stranger@example.com")

        self.organizer_user = get_user_model().objects.create(email="organizer@example.com")
        assign_perm("view_contest", self.organizer_user, self.contest)
        assign_perm("change_contest", self.organizer_user, self.contest)
        assign_perm("delete_contest", self.organizer_user, self.contest)

        self.url = f"/api/v1/contests/{self.contest.pk}/navigationtasks/{self.navigation_task.pk}/delete_self_managed_contestant/{self.contestant.pk}/"

    def test_stranger_cannot_delete_someone_elses_contestant(self, *args):
        self.client.force_login(user=self.stranger_user)
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Contestant.objects.filter(pk=self.contestant.pk).exists())

    def test_owner_can_delete_own_contestant(self, *args):
        self.client.force_login(user=self.owner_user)
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Contestant.objects.filter(pk=self.contestant.pk).exists())

    def test_organizer_can_delete_any_contestant(self, *args):
        self.client.force_login(user=self.organizer_user)
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Contestant.objects.filter(pk=self.contestant.pk).exists())


class TestClearContestantsRequiresChangePermission(APITestCase):
    """Finding #2: clear_contestants required only view_contest but deleted every contestant.
    Fix: now requires change_contest, matching its sibling destructive views."""

    def setUp(self):
        self.contest = Contest.objects.create(
            name="contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            location="60, 11",
        )
        scorecard = get_default_scorecard()
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Test", file.readlines()[1:])
            route = editable_route.create_precision_route(True, scorecard)
        self.navigation_task = _make_navigation_task(self.contest, route, scorecard)

        crew = Crew.objects.create(member1=Person.objects.create(first_name="A", last_name="B", email="a@example.com"))
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-BBB"))
        Contestant.objects.create(
            team=team,
            navigation_task=self.navigation_task,
            takeoff_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
            finished_by_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2),
            tracker_start_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=30),
            tracker_device_id="test_device",
            contestant_number=1,
        )

        self.viewer_user = get_user_model().objects.create(email="viewer@example.com")
        assign_perm("view_contest", self.viewer_user, self.contest)

        self.manager_user = get_user_model().objects.create(email="manager@example.com")
        assign_perm("view_contest", self.manager_user, self.contest)
        assign_perm("change_contest", self.manager_user, self.contest)

        self.url = f"/display/navigationtask/{self.navigation_task.pk}/remove_contestants/"

    def test_view_only_user_cannot_clear_contestants(self):
        self.client.force_login(user=self.viewer_user)
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(1, self.navigation_task.contestant_set.count())

    def test_manager_can_clear_contestants(self):
        self.client.force_login(user=self.manager_user)
        self.client.get(self.url)
        self.assertEqual(0, self.navigation_task.contestant_set.count())


class TestContestListCacheDoesNotLeakAcrossUsers(APITestCase):
    """Finding #3: public_only=true hardcoded the cache/ETag key to "global" even for
    authenticated requests, so one authenticated user's personalized response (including their
    own token-grant inventory) got cached and served to every other caller, anonymous included.
    Fix: only an actually-anonymous public_only request uses the shared "global" key."""

    def setUp(self):
        self.contest = Contest.objects.create(
            name="Public contest",
            is_public=True,
            is_featured=True,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            location="60, 11",
        )
        self.user_a = get_user_model().objects.create(email="a@example.com")
        self.user_b = get_user_model().objects.create(email="b@example.com")

    def test_authenticated_public_only_requests_get_distinct_cache_entries(self):
        from django.core.cache import cache

        cache.clear()
        self.client.force_login(user=self.user_a)
        response_a = self.client.get("/api/v1/contests/?public_only=true")
        self.assertEqual(response_a.status_code, status.HTTP_200_OK)
        etag_a = response_a["ETag"]
        self.assertEqual(response_a["Cache-Control"], "private, no-cache")

        self.client.force_login(user=self.user_b)
        response_b = self.client.get("/api/v1/contests/?public_only=true")
        self.assertEqual(response_b.status_code, status.HTTP_200_OK)
        etag_b = response_b["ETag"]
        self.assertEqual(response_b["Cache-Control"], "private, no-cache")

        # Different users must not collide on the same ETag/cache entry.
        self.assertNotEqual(etag_a, etag_b)

        self.client.logout()
        response_anon = self.client.get("/api/v1/contests/?public_only=true")
        self.assertEqual(response_anon.status_code, status.HTTP_200_OK)
        self.assertEqual(response_anon["Cache-Control"], "public, no-cache, stale-while-revalidate=86400")


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestPhotoViewSetScoping(APITestCase):
    """Finding #5: PhotoViewSet had no scoping on list/create - any authenticated user could
    fetch the observation-photo answer key for a private task, or inject photos into another
    organiser's route."""

    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        scorecard = get_default_scorecard()
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Test", file.readlines()[1:])
            self.private_route = editable_route.create_precision_route(True, scorecard)
        self.private_contest = Contest.objects.create(
            name="Private contest",
            is_public=False,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            location="60, 11",
        )
        self.private_task = _make_navigation_task(
            self.private_contest, self.private_route, scorecard, is_public=False
        )
        self.private_photo = Photo.objects.create(
            name="Answer key photo", route=self.private_route, latitude=60.0, longitude=11.0
        )

        self.outsider_user = get_user_model().objects.create(email="outsider@example.com")
        self.organizer_user = get_user_model().objects.create(email="organizer@example.com")
        assign_perm("view_contest", self.organizer_user, self.private_contest)
        assign_perm("change_contest", self.organizer_user, self.private_contest)

    def test_outsider_cannot_list_photos_for_private_route(self, *args):
        self.client.force_login(user=self.outsider_user)
        response = self.client.get(f"/api/v1/photos/?route={self.private_route.pk}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([], response.json())

    def test_organizer_can_list_photos_for_own_private_route(self, *args):
        self.client.force_login(user=self.organizer_user)
        response = self.client.get(f"/api/v1/photos/?route={self.private_route.pk}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(1, len(response.json()))

    def test_outsider_cannot_create_photo_on_someone_elses_route(self, *args):
        self.client.force_login(user=self.outsider_user)
        response = self.client.post(
            "/api/v1/photos/",
            data={"name": "Injected", "route": self.private_route.pk, "latitude": 60.0, "longitude": 11.0},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(1, Photo.objects.filter(route=self.private_route).count())


class TestTeamViewSetScoping(APITestCase):
    """Finding #11: TeamViewSet had no queryset scoping, so any authenticated user could list
    every pilot's name/email/phone system-wide via GET /api/v1/teams/."""

    def setUp(self):
        self.contest = Contest.objects.create(
            name="Private contest",
            is_public=False,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            location="60, 11",
        )
        crew = Crew.objects.create(
            member1=Person.objects.create(first_name="Secret", last_name="Pilot", email="secret@example.com")
        )
        self.team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-CCC"))
        ContestTeam.objects.create(team=self.team, contest=self.contest, air_speed=70)

        self.outsider_user = get_user_model().objects.create(email="outsider@example.com")
        self.member_user = get_user_model().objects.create(email="secret@example.com")
        self.organizer_user = get_user_model().objects.create(email="organizer@example.com")
        assign_perm("view_contest", self.organizer_user, self.contest)

    def test_outsider_cannot_see_team_in_private_contest(self):
        self.client.force_login(user=self.outsider_user)
        response = self.client.get("/api/v1/teams/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        team_ids = [t["id"] for t in response.json()]
        self.assertNotIn(self.team.pk, team_ids)

    def test_team_member_can_see_own_team(self):
        self.client.force_login(user=self.member_user)
        response = self.client.get("/api/v1/teams/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        team_ids = [t["id"] for t in response.json()]
        self.assertIn(self.team.pk, team_ids)

    def test_organizer_with_view_permission_can_see_team(self):
        self.client.force_login(user=self.organizer_user)
        response = self.client.get("/api/v1/teams/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        team_ids = [t["id"] for t in response.json()]
        self.assertIn(self.team.pk, team_ids)
