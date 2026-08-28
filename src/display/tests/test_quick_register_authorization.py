"""
Regression tests for the critical finding (2026-08-28 security review): quick_register had no
authorization or capacity-enforcement check at all - any authenticated user could self-enrol in
ANY poker-run task regardless of is_public/allow_self_management, bypassing every access-tier
limit.
"""

import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework.exceptions import ValidationError as DRFValidationError

from display.models import (
    Aeroplane,
    Contest,
    Contestant,
    Crew,
    NavigationTask,
    Person,
    Route,
    Scorecard,
    Team,
)
from display.utilities.navigation_task_type_definitions import POKER


def _make_poker_task(**kwargs):
    scorecard = Scorecard.objects.create(name="Test Poker Scorecard", task_type=[POKER])
    route = Route.objects.create(name="Test Poker Route")
    contest = Contest.objects.create(
        name="Poker contest",
        is_public=kwargs.pop("contest_is_public", True),
        start_time=datetime.datetime.now(datetime.timezone.utc),
        finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
        location="60, 11",
    )
    now = datetime.datetime.now(datetime.timezone.utc)
    defaults = dict(
        name="Poker task",
        original_scorecard=scorecard,
        minutes_to_starting_point=5,
        minutes_to_landing=20,
        route=route,
        contest=contest,
        start_time=now,
        finish_time=now + datetime.timedelta(days=1),
        allow_self_management=True,
        is_public=True,
    )
    defaults.update(kwargs)
    return NavigationTask.create(**defaults)


class TestQuickRegisterAuthorization(TestCase):
    def setUp(self):
        self.pilot_person = Person.objects.create(first_name="A", last_name="Pilot", email="pilot@example.com")
        self.pilot_user = get_user_model().objects.create(email="pilot@example.com")

    def test_private_task_returns_404_for_ordinary_user(self):
        navigation_task = _make_poker_task(is_public=False)
        self.client.force_login(user=self.pilot_user)
        url = reverse("quick_register", kwargs={"pk": navigation_task.pk})

        get_response = self.client.get(url)
        self.assertEqual(get_response.status_code, 404)

        post_response = self.client.post(url, data={"tail_number": "LN-TAS"})
        self.assertEqual(post_response.status_code, 404)
        self.assertEqual(0, Contestant.objects.filter(navigation_task=navigation_task).count())

    def test_task_with_self_management_disabled_returns_404(self):
        navigation_task = _make_poker_task(allow_self_management=False)
        self.client.force_login(user=self.pilot_user)
        url = reverse("quick_register", kwargs={"pk": navigation_task.pk})

        response = self.client.post(url, data={"tail_number": "LN-TAS"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(0, Contestant.objects.filter(navigation_task=navigation_task).count())

    def test_public_self_managed_task_allows_registration(self):
        navigation_task = _make_poker_task()
        self.client.force_login(user=self.pilot_user)
        url = reverse("quick_register", kwargs={"pk": navigation_task.pk})

        response = self.client.post(url, data={"tail_number": "LN-TAS"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(1, Contestant.objects.filter(navigation_task=navigation_task).count())
        contestant = Contestant.objects.get(navigation_task=navigation_task)
        self.assertEqual(contestant.team.aeroplane.registration, "LN-TAS")

    def test_contest_manager_can_reach_private_task(self):
        navigation_task = _make_poker_task(is_public=False, contest_is_public=False)
        Person.objects.create(first_name="Manager", last_name="Person", email="manager@example.com")
        manager_user = get_user_model().objects.create(email="manager@example.com")
        assign_perm("change_contest", manager_user, navigation_task.contest)
        self.client.force_login(user=manager_user)
        url = reverse("quick_register", kwargs={"pk": navigation_task.pk})

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_invalid_tail_number_rejected(self):
        navigation_task = _make_poker_task()
        self.client.force_login(user=self.pilot_user)
        url = reverse("quick_register", kwargs={"pk": navigation_task.pk})

        response = self.client.post(url, data={"tail_number": "LN TAS <script>"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "alphanumeric")
        self.assertEqual(0, Contestant.objects.filter(navigation_task=navigation_task).count())
        self.assertFalse(Aeroplane.objects.filter(registration__icontains="script").exists())

    @patch("display.views._assert_can_reserve_task_slot")
    def test_capacity_limit_blocks_registration_and_surfaces_error(self, mock_assert):
        mock_assert.side_effect = DRFValidationError("Contestant limit reached")
        navigation_task = _make_poker_task()
        self.client.force_login(user=self.pilot_user)
        url = reverse("quick_register", kwargs={"pk": navigation_task.pk})

        response = self.client.post(url, data={"tail_number": "LN-TAS"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(0, Contestant.objects.filter(navigation_task=navigation_task).count())
