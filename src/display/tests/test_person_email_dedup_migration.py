import datetime
import importlib

from django.apps import apps
from django.test import TransactionTestCase

from display.models import Contest, Crew, Person
from display.models.usage_accounting import ContestUsageLedger
from utilities.mock_utilities import allow_duplicate_person_emails

dedupe_person_emails = importlib.import_module("display.migrations.0182_person_email_unique").dedupe_person_emails


class TestPersonEmailDedupMigration(TransactionTestCase):
    """
    Exercises the data migration standalone (display/migrations/0182_person_email_unique.py)
    against the real models via apps.get_model, since it only uses plain ORM calls. Covers the
    production bug it fixes (PYTHON-DJANGO-1Q): duplicate Person rows sharing an email, with
    FK references on both the surviving and losing sides.

    Each test builds its duplicate-email fixture and calls dedupe_person_emails() inside a single
    allow_duplicate_person_emails() block: that context manager prunes any email still duplicated
    back to one row as soon as it exits (so it can restore the DB constraint), so the call under
    test - which is itself what's expected to do that pruning here - must run before the block
    ends, not after.
    """

    def setUp(self):
        self.contest = Contest.objects.create(
            name="contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
        )

    def test_duplicate_person_is_removed_and_survivor_kept(self):
        with allow_duplicate_person_emails():
            Person.objects.bulk_create(
                [
                    Person(first_name="", last_name="", email="dup@example.com"),
                    Person(first_name="Real", last_name="Name", email="dup@example.com"),
                ]
            )
            survivor, duplicate = Person.objects.filter(email="dup@example.com").order_by("pk")

            dedupe_person_emails(apps, None)

            remaining = list(Person.objects.filter(email="dup@example.com"))
            self.assertEqual([survivor.pk], [p.pk for p in remaining])

    def test_crew_references_are_repointed_to_survivor(self):
        with allow_duplicate_person_emails():
            Person.objects.bulk_create(
                [
                    Person(first_name="", last_name="", email="dup@example.com"),
                    Person(first_name="Real", last_name="Name", email="dup@example.com"),
                ]
            )
            survivor, duplicate = Person.objects.filter(email="dup@example.com").order_by("pk")
            crew = Crew.objects.create(member1=duplicate)

            dedupe_person_emails(apps, None)

            crew.refresh_from_db()
            self.assertEqual(survivor.pk, crew.member1_id)

    def test_non_conflicting_ledger_reference_is_repointed_to_survivor(self):
        with allow_duplicate_person_emails():
            Person.objects.bulk_create(
                [
                    Person(first_name="", last_name="", email="dup@example.com"),
                    Person(first_name="Real", last_name="Name", email="dup@example.com"),
                ]
            )
            survivor, duplicate = Person.objects.filter(email="dup@example.com").order_by("pk")
            ledger = ContestUsageLedger.objects.create(
                contest=self.contest, pilot=duplicate, kind=ContestUsageLedger.CONTEST_PILOT_STARTED
            )

            dedupe_person_emails(apps, None)

            ledger.refresh_from_db()
            self.assertEqual(survivor.pk, ledger.pilot_id)

    def test_conflicting_ledger_reference_is_dropped_instead_of_violating_unique_constraint(self):
        with allow_duplicate_person_emails():
            Person.objects.bulk_create(
                [
                    Person(first_name="", last_name="", email="dup@example.com"),
                    Person(first_name="Real", last_name="Name", email="dup@example.com"),
                ]
            )
            survivor, duplicate = Person.objects.filter(email="dup@example.com").order_by("pk")
            # Both the survivor and the duplicate already have a "contest_pilot_started" row for
            # the same contest - repointing the duplicate's row would violate
            # unique_contest_pilot_started_usage, so it must be deleted instead.
            ContestUsageLedger.objects.create(
                contest=self.contest, pilot=survivor, kind=ContestUsageLedger.CONTEST_PILOT_STARTED
            )
            duplicate_ledger = ContestUsageLedger.objects.create(
                contest=self.contest, pilot=duplicate, kind=ContestUsageLedger.CONTEST_PILOT_STARTED
            )

            dedupe_person_emails(apps, None)

            self.assertFalse(ContestUsageLedger.objects.filter(pk=duplicate_ledger.pk).exists())
            self.assertEqual(1, ContestUsageLedger.objects.filter(contest=self.contest).count())

    def test_blank_emails_are_left_alone(self):
        with allow_duplicate_person_emails():
            Person.objects.bulk_create(
                [Person(first_name="A", last_name="A", email=""), Person(first_name="B", last_name="B", email="")]
            )

            dedupe_person_emails(apps, None)

            self.assertEqual(2, Person.objects.filter(email="").count())
            # Clean up before the context manager restores the unique constraint on exit - two
            # blank-email rows would otherwise conflict with it, same as the pair under test.
            Person.objects.filter(email="").delete()
