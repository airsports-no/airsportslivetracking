"""
Regression test for the scheduling/poker-review finding (2026-08-28 review): every calculator
restart mid-flight dealt a duplicate set of poker cards. PokerCalculator.passed_gates (in-memory
only) rebuilds empty on restart, and idempotent-restart replays the whole position track from
the beginning, so every already-passed gate re-fired its PokerGatePassedEvent and
PlayingCard.add_contestant_card did an unconditional create() - doubling a contestant's cards
(and since best-5-of-N hand evaluation is used, this can only ever improve their hand) plus
duplicate score-log entries.

Also covers the DB-level unique_together added alongside the fix (migration 0169): the
application-level get_or_create in add_contestant_card is race-prone on its own if two writers
ever run concurrently for the same contestant - the constraint is the real backstop, matching the
established ScoreLogEntry.get_or_create_and_push pattern.
"""

import datetime
import threading
from unittest.mock import patch

from django.test import TransactionTestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Aeroplane, Contest, Contestant, Crew, NavigationTask, Person, PlayingCard, Route, Team
from utilities.mock_utilities import TraccarMock


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestPlayingCardIdempotency(TransactionTestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        self.contest = Contest.objects.create(
            name="Poker Idempotency Contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            location="60, 11",
        )
        route = Route.objects.create(name="Route")
        now = datetime.datetime.now(datetime.timezone.utc)
        self.navigation_task = NavigationTask.create(
            name="Poker Idempotency Task",
            original_scorecard=get_default_scorecard(),
            route=route,
            contest=self.contest,
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="A", last_name="B", email="poker@example.com"))
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-PKR"))
        self.contestant = Contestant.objects.create(
            team=team,
            navigation_task=self.navigation_task,
            takeoff_time=now + datetime.timedelta(hours=1),
            finished_by_time=now + datetime.timedelta(hours=2),
            tracker_start_time=now + datetime.timedelta(minutes=30),
            tracker_device_id="test_device",
            contestant_number=1,
        )

    def test_replaying_the_same_gate_does_not_deal_a_second_card(self, *args):
        card = PlayingCard.get_random_unique_card(self.contestant)
        PlayingCard.add_contestant_card(self.contestant, card, "TP1", 0)
        self.assertEqual(self.contestant.playingcard_set.count(), 1)

        # Simulates a calculator restart replaying the already-passed TP1 gate: the caller
        # picks a (possibly different) random card again since PokerCalculator.passed_gates
        # was rebuilt empty, but add_contestant_card itself must still be a no-op.
        another_card = PlayingCard.get_random_unique_card(self.contestant)
        PlayingCard.add_contestant_card(self.contestant, another_card, "TP1", 0)

        self.assertEqual(self.contestant.playingcard_set.count(), 1)
        self.assertEqual(self.contestant.playingcard_set.get().card, card)

    def test_different_waypoints_each_still_deal_a_card(self, *args):
        card1 = PlayingCard.get_random_unique_card(self.contestant)
        PlayingCard.add_contestant_card(self.contestant, card1, "TP1", 0)
        card2 = PlayingCard.get_random_unique_card(self.contestant)
        PlayingCard.add_contestant_card(self.contestant, card2, "TP2", 1)

        self.assertEqual(self.contestant.playingcard_set.count(), 2)

    def test_concurrent_add_for_the_same_waypoint_creates_exactly_one_card(self, *args):
        results = []

        def add_card():
            try:
                card = PlayingCard.get_random_unique_card(self.contestant)
            except ValueError:
                card = "2s"
            results.append(PlayingCard.add_contestant_card(self.contestant, card, "TP1", 0))

        threads = [threading.Thread(target=add_card) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(self.contestant.playingcard_set.count(), 1)
