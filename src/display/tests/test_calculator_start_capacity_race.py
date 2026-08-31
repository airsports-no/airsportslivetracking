"""
Regression test for the SENSITIVE finding (2026-08-28 review, models+services finding #5):
ContestantTrack.set_calculator_started() called assert_can_start_contestant() (which counts
existing ContestUsageLedger rows) and only afterwards wrote its own ledger rows, with no lock
spanning the read and the write. Live calculators run as one prefork worker process per
contestant, so a mass-simultaneous start (many contestants sharing a tracker_start_time) could
have every worker read the same pre-insert count and all pass the capacity check before any of
them had written their row, letting a contest exceed its resolved tier's contestant limit.

This uses TransactionTestCase (not TestCase) and real threads because the fix relies on a real
cross-connection database lock (Contest.objects.select_for_update()) - a single wrapped test
transaction can't demonstrate that two independent DB connections actually serialize.
"""

import datetime
import threading

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase, override_settings
from rest_framework.exceptions import ValidationError
from django.utils import timezone

from display.models import (
    Aeroplane,
    Contest,
    ContestTokenAssignment,
    Contestant,
    ContestantTrack,
    Crew,
    NavigationTask,
    Person,
    Route,
    Scorecard,
    Team,
    TokenType,
    UserTokenGrant,
)
from display.services import capacity_enforcement


@override_settings(ACCESS_ENFORCEMENT_MODE="enforce", DEFAULT_FREE_CONTESTANT_LIMIT=0)
class TestSetCalculatorStartedCapacityRace(TransactionTestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create(email="race-owner@example.com")
        self.owner_person = Person.objects.create(first_name="Owner", last_name="Pilot", email=self.owner.email)
        self.contest = Contest.objects.create(
            name="Race Contest",
            time_zone="Europe/Oslo",
            start_time=timezone.now(),
            finish_time=timezone.now() + datetime.timedelta(hours=8),
            location="60.0,11.0",
            created_by=self.owner,
        )
        token_type = TokenType.objects.create(name="Race token", contestant_limit=1)
        grant = UserTokenGrant.objects.create(user=self.owner, token_type=token_type, quantity_total=1, quantity_consumed=0)
        ContestTokenAssignment.objects.create(contest=self.contest, token_grant=grant, token_type=token_type)
        scorecard = Scorecard.objects.create(name="Race card", shortcut_name="race-card")
        task = NavigationTask.objects.create(
            name="Race Task",
            contest=self.contest,
            route=Route.objects.create(name="Race Route"),
            original_scorecard=scorecard,
            start_time=timezone.now(),
            finish_time=timezone.now() + datetime.timedelta(hours=8),
        )

        def make_contestant(number, email, registration):
            pilot = Person.objects.create(first_name="Pilot", last_name=str(number), email=email)
            team = Team.objects.create(crew=Crew.objects.create(member1=pilot), aeroplane=Aeroplane.objects.create(registration=registration))
            takeoff = timezone.now()
            return Contestant.objects.create(
                team=team,
                navigation_task=task,
                contestant_number=number,
                takeoff_time=takeoff,
                tracker_start_time=takeoff - datetime.timedelta(minutes=10),
                finished_by_time=takeoff + datetime.timedelta(hours=2),
                air_speed=70,
                minutes_to_starting_point=5,
                wind_speed=0,
                wind_direction=0,
                gate_times={},
            )

        self.contestant_a = make_contestant(1, "racer-a@example.com", "LN-RACE-A")
        self.contestant_b = make_contestant(2, "racer-b@example.com", "LN-RACE-B")

    def test_concurrent_starts_do_not_exceed_capacity_limit(self):
        contestant_a_reached_check = threading.Event()
        release_contestant_a = threading.Event()
        original_assert_can_start_contestant = capacity_enforcement.assert_can_start_contestant

        def instrumented_assert_can_start_contestant(contestant):
            result = original_assert_can_start_contestant(contestant)
            if contestant.pk == self.contestant_a.pk:
                # At this point contestant A's set_calculator_started() is holding the
                # Contest row lock (acquired before this call) inside its open transaction.
                # Pausing here - before A's transaction has written its ledger rows or
                # committed - is exactly the pre-fix race window.
                contestant_a_reached_check.set()
                release_contestant_a.wait(timeout=5)
            return result

        results = {}

        def start(contestant, key):
            try:
                ContestantTrack.objects.get(contestant=contestant).set_calculator_started()
                results[key] = "started"
            except ValidationError as e:
                results[key] = e

        capacity_enforcement.assert_can_start_contestant = instrumented_assert_can_start_contestant
        try:
            thread_a = threading.Thread(target=start, args=(self.contestant_a, "a"))
            thread_a.start()
            self.assertTrue(contestant_a_reached_check.wait(timeout=5), "contestant A never reached the capacity check")

            thread_b = threading.Thread(target=start, args=(self.contestant_b, "b"))
            thread_b.start()
            # Contestant B's set_calculator_started() should block acquiring the Contest row
            # lock (still held by thread A) rather than racing ahead and reading the
            # pre-insert ledger count.
            thread_b.join(timeout=1)
            self.assertTrue(thread_b.is_alive(), "contestant B was not blocked by the Contest row lock")

            release_contestant_a.set()
            thread_a.join(timeout=5)
            thread_b.join(timeout=5)
        finally:
            capacity_enforcement.assert_can_start_contestant = original_assert_can_start_contestant

        self.assertEqual("started", results.get("a"))
        self.assertIsInstance(results.get("b"), ValidationError)

        self.contestant_a.refresh_from_db()
        self.contestant_b.refresh_from_db()
        self.assertTrue(self.contestant_a.contestanttrack.calculator_started)
        self.assertFalse(self.contestant_b.contestanttrack.calculator_started)
