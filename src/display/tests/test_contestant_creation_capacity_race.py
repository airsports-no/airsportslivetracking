"""
Regression test (CodeRabbit review of PR #734, findings #7/#8/#13): _assert_can_reserve_task_slot
reads current reservations and only afterwards persists the new contestant/team - with no lock
spanning the read and the write, two concurrent requests for a contest's last slot could both
read the pre-insert count, both pass the assertion, and both persist, exceeding the resolved
tier's contestant_limit. Even a single *rejected* request could leave its nested team
materialization (TeamNestedSerialiser.save(), Team.get_or_create_from_signup()) persisted, since
there was no rollback tying the capacity check to the earlier writes.

Fix (matching the established pattern in ContestantTrack.set_calculator_started, see
test_calculator_start_capacity_race.py): every capacity-checking write path now acquires
Contest.objects.select_for_update() before checking, inside the same transaction as the save -
in ContestantNestedTeamSerialiser.create()/update() and ContestantViewSet.create()/update()
(serialisers.py / viewsets.py) and SignupSerialiser.create() (serialisers.py).

This test exercises ContestantNestedTeamSerialiser.create() (via the create-with-team endpoint,
the most complex of the fixed call sites - nested team materialization plus the capacity check)
using TransactionTestCase and real threads, since the fix relies on a genuine cross-connection
database lock that a single wrapped test transaction can't demonstrate.
"""

import datetime
import threading

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from display import serialisers
from display.default_scorecards.create_scorecards import create_scorecards
from display.models import (
    Aeroplane,
    Contest,
    ContestTeam,
    ContestTokenAssignment,
    Contestant,
    Crew,
    EditableRoute,
    NavigationTask,
    Person,
    Route,
    Scorecard,
    Team,
    TokenType,
    UserTokenGrant,
)
from guardian.shortcuts import assign_perm
from utilities.mock_utilities import TraccarMock
from unittest.mock import patch


@override_settings(ACCESS_ENFORCEMENT_MODE="enforce", DEFAULT_FREE_CONTESTANT_LIMIT=0)
@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestContestantCreationCapacityRace(TransactionTestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        create_scorecards()
        self.owner = get_user_model().objects.create(email="race-owner2@example.com")
        self.owner_person = Person.objects.create(first_name="Owner", last_name="Pilot", email=self.owner.email)
        self.contest = Contest.objects.create(
            name="Nested Team Race Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8),
            location="60.0,11.0",
            created_by=self.owner,
        )
        assign_perm("view_contest", self.owner, self.contest)
        assign_perm("change_contest", self.owner, self.contest)
        token_type = TokenType.objects.create(name="Nested race token", contestant_limit=1)
        grant = UserTokenGrant.objects.create(
            user=self.owner, token_type=token_type, quantity_total=1, quantity_consumed=0
        )
        ContestTokenAssignment.objects.create(contest=self.contest, token_grant=grant, token_type=token_type)
        scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        self.navigation_task = NavigationTask.objects.create(
            name="Nested Race Task",
            contest=self.contest,
            route=Route.objects.create(name="Nested Race Route"),
            original_scorecard=scorecard,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8),
        )
        self.url = reverse(
            "contestants-create-with-team",
            kwargs={"contest_pk": self.contest.pk, "navigationtask_pk": self.navigation_task.pk},
        )

    def _contestant_payload(self, suffix):
        now = datetime.datetime.now(datetime.timezone.utc)
        return {
            "team": {
                "aeroplane": {"registration": f"LN-RACE{suffix}"},
                "crew": {
                    "member1": {
                        "first_name": "Guest",
                        "last_name": f"Pilot{suffix}",
                        "email": f"guest-pilot-{suffix}@example.com",
                    }
                },
                "country": "NO",
            },
            "gate_times": {},
            "takeoff_time": now.isoformat(),
            "minutes_to_starting_point": 5,
            "finished_by_time": (now + datetime.timedelta(hours=2)).isoformat(),
            "air_speed": 70,
            "contestant_number": 1 if suffix == "A" else 2,
            "tracker_device_id": f"tracker-{suffix}",
            "tracker_start_time": (now - datetime.timedelta(hours=1)).isoformat(),
            "wind_speed": 10,
            "wind_direction": 0,
        }

    def test_concurrent_create_with_team_requests_do_not_both_succeed(self, *args):
        contestant_a_reached_check = threading.Event()
        release_contestant_a = threading.Event()
        original_assert = serialisers._assert_can_reserve_task_slot

        def instrumented_assert(navigation_task, team, resolution, current_contestant=None):
            result = original_assert(navigation_task, team, resolution, current_contestant=current_contestant)
            if "RACEA" in team.aeroplane.registration:
                # At this point request A's ContestantNestedTeamSerialiser.create() is holding
                # the Contest row lock (acquired before this call) inside its open transaction -
                # pausing here, before A's transaction has saved the Contestant or committed, is
                # exactly the pre-fix race window.
                contestant_a_reached_check.set()
                release_contestant_a.wait(timeout=5)
            return result

        results = {}

        def post(suffix, key):
            client = APIClient()
            client.force_login(user=self.owner)
            response = client.post(self.url, data=self._contestant_payload(suffix), format="json")
            results[key] = response.status_code

        serialisers._assert_can_reserve_task_slot = instrumented_assert
        try:
            thread_a = threading.Thread(target=post, args=("A", "a"))
            thread_a.start()
            self.assertTrue(contestant_a_reached_check.wait(timeout=5), "request A never reached the capacity check")

            thread_b = threading.Thread(target=post, args=("B", "b"))
            thread_b.start()
            # Request B should block acquiring the Contest row lock (still held by thread A's
            # open transaction) rather than racing ahead and reading the pre-insert count.
            thread_b.join(timeout=1)
            self.assertTrue(thread_b.is_alive(), "request B was not blocked by the Contest row lock")

            release_contestant_a.set()
            thread_a.join(timeout=5)
            thread_b.join(timeout=5)
        finally:
            serialisers._assert_can_reserve_task_slot = original_assert

        status_codes = sorted([results.get("a"), results.get("b")])
        self.assertEqual(
            status_codes,
            [201, 400],
            f"Exactly one request must succeed and one must be rejected for a contest with "
            f"contestant_limit=1, got {results}",
        )
        self.assertEqual(1, Contestant.objects.filter(navigation_task=self.navigation_task).count())
