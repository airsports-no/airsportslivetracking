import datetime
import threading
from unittest.mock import patch

from django.db import IntegrityError, transaction
from django.test import TransactionTestCase

from display.default_scorecards.create_scorecards import create_scorecards
from display.models import (
    Aeroplane,
    Contest,
    Contestant,
    Crew,
    EditableRoute,
    NavigationTask,
    Person,
    ScoreLogEntry,
    Scorecard,
    Team,
)
from utilities.mock_utilities import TraccarMock


class TestScoreLogEntryIdempotencyConstraint(TransactionTestCase):
    """Covers the DB-level unique_together added alongside the
    94782a91/0122c7e0 idempotent-scoring fix (migrations 0163/0164): the
    application-level get_or_create in ScoreLogEntry.get_or_create_and_push
    is race-prone on its own if two writers ever run concurrently for the
    same contestant - the constraint is the real backstop, and Django's
    get_or_create() is specifically designed to recover from the resulting
    IntegrityError by falling back to a get().
    """

    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        create_scorecards()
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        with open("display/tests/NM.csv", "r") as file:
            editable_route, _ = EditableRoute.create_from_csv("Idempotency constraint test", file.readlines()[1:])
            self.route = editable_route.create_precision_route(True, self.scorecard)
        self.contest = Contest.objects.create(
            name="Idempotency constraint contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
            time_zone="Europe/Oslo",
        )
        self.navigation_task = NavigationTask.create(
            name="Idempotency constraint task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Constraint", last_name="Pilot"))
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-IDEM"))
        start_time = datetime.datetime(2020, 8, 1, 8, 5, tzinfo=datetime.timezone.utc)
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_device_id="idempotency-constraint-test",
            contestant_number=1,
            minutes_to_starting_point=6,
            air_speed=75,
            wind_direction=165,
            wind_speed=8,
        )

    def _entry_kwargs(self):
        return dict(
            contestant=self.contestant,
            time=datetime.datetime(2020, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            gate="SP",
            message="passing gate",
            points=10.0,
            planned=datetime.datetime(2020, 8, 1, 9, 0, tzinfo=datetime.timezone.utc),
            actual=datetime.datetime(2020, 8, 1, 9, 0, 1, tzinfo=datetime.timezone.utc),
            type="anomaly",
        )

    def test_db_rejects_a_direct_duplicate_insert(self):
        ScoreLogEntry.objects.create(**self._entry_kwargs())
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ScoreLogEntry.objects.create(**self._entry_kwargs())
        self.assertEqual(1, ScoreLogEntry.objects.filter(contestant=self.contestant).count())

    def test_a_row_differing_only_in_a_non_idempotency_field_still_violates_the_constraint(self):
        # string/offset_string/times_string are deliberately NOT part of the
        # constraint (get_or_create_and_push treats them as `defaults` to
        # update in place on an existing row, not as idempotency
        # differentiators - see get_idempotency_fields) - so two rows that
        # only differ in `string` are still duplicates as far as the DB is
        # concerned, exactly like get_or_create_and_push already treats them.
        ScoreLogEntry.objects.create(**self._entry_kwargs())
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ScoreLogEntry.objects.create(**{**self._entry_kwargs(), "string": "a different display string"})
        self.assertEqual(1, ScoreLogEntry.objects.filter(contestant=self.contestant).count())

    def test_a_row_differing_in_an_idempotency_field_is_allowed(self):
        ScoreLogEntry.objects.create(**self._entry_kwargs())
        second = ScoreLogEntry.objects.create(**{**self._entry_kwargs(), "gate": "TP1"})
        self.assertIsNotNone(second.pk)
        self.assertEqual(2, ScoreLogEntry.objects.filter(contestant=self.contestant).count())

    @patch.object(ScoreLogEntry, "push")
    def test_concurrent_get_or_create_and_push_for_the_same_event_creates_exactly_one_row(self, mock_push):
        # Two threads racing get_or_create_and_push with the identical
        # idempotency key - simulating two calculators briefly alive for the
        # same contestant. Without the DB constraint, both could see "no
        # existing row" before either commits and both insert. With it,
        # Django's get_or_create() catches the resulting IntegrityError from
        # whichever thread loses the race and falls back to a get().
        kwargs = self._entry_kwargs()
        results = []
        errors = []
        start_barrier = threading.Barrier(2)

        def worker():
            try:
                start_barrier.wait(timeout=5)
                entry, created = ScoreLogEntry.get_or_create_and_push(**kwargs)
                results.append((entry.pk, created))
            except Exception as exc:  # noqa: BLE001 - want to see any failure from the thread
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual([], errors, f"worker thread(s) raised: {errors}")
        self.assertEqual(2, len(results))
        self.assertEqual(1, ScoreLogEntry.objects.filter(contestant=self.contestant).count())
        # Both threads must agree on the same row.
        pks = {pk for pk, _ in results}
        self.assertEqual(1, len(pks))
        # Exactly one of the two calls should have actually created it.
        created_flags = [created for _, created in results]
        self.assertEqual(1, sum(1 for c in created_flags if c))
