from contextlib import contextmanager
from unittest.mock import Mock

from django.db import connection, models
from django.db.models import Count


def build_traccar_mock() -> Mock:
    """
    A stand-in for Traccar that mirrors the shapes the real client returns.

    get_device must return None rather than an auto-created child Mock: callers do
    `if original_device is not None: traccar.delete_device(original_device["id"])`,
    and a bare Mock is both truthy and not subscriptable, so it would raise TypeError.
    """
    mock = Mock()
    mock.get_or_create_device.return_value = ({}, False)
    mock.get_device_ids_for_contestant.return_value = []
    mock.get_device.return_value = None
    return mock


TraccarMock = build_traccar_mock()


@contextmanager
def allow_duplicate_person_emails():
    """
    Temporarily drops Person.email's DB-level uniqueness constraint, to reproduce in a test the
    "already duplicated" data state that constraint now prevents (see Sentry PYTHON-DJANGO-1Q:
    Person.email had no DB-level constraint, so a get_or_create race could leave two Person rows
    sharing an email).

    Must only be used from a django.test.TransactionTestCase, not TestCase: this ALTER TABLE
    causes an implicit commit on MySQL (this project's database), which would otherwise both
    defeat TestCase's rollback-based cleanup (permanently committing the test's fixtures) and
    leave the constraint dropped for every later test (ALTER TABLE isn't rolled back either).
    TransactionTestCase instead truncates tables after each test, which cleans up regardless.

    The off/on fields must each be freshly constructed, not a mutated copy of the live field -
    schema_editor decides whether a column needs altering by comparing Field.deconstruct()
    output, which Field caches from its original constructor call and does not refresh on a
    later `field.unique = False` assignment.

    On exit, any non-blank email still duplicated (the test's own code is not expected to clean
    these up - that's the whole point of the fixture) is pruned back to one row per email, purely
    so the constraint below can be restored; TransactionTestCase's post-test truncation is what
    actually cleans up the test's data. Blank-email duplicates are left as the caller made them -
    a shared blank doesn't mean two Person rows are the same physical person, so a caller testing
    that case (like dedupe_person_emails leaving them alone) must clean those up itself before
    this context manager exits.
    """
    from display.models import Person

    live_email_field = Person._meta.get_field("email")
    non_unique_email_field = models.EmailField(max_length=254, unique=False)
    non_unique_email_field.set_attributes_from_name("email")
    with connection.schema_editor() as editor:
        editor.alter_field(Person, live_email_field, non_unique_email_field)
    try:
        yield
    finally:
        duplicate_emails = (
            Person.objects.exclude(email="")
            .values("email")
            .annotate(total=Count("id"))
            .filter(total__gt=1)
            .values_list("email", flat=True)
        )
        for email in duplicate_emails:
            _survivor, *extras = Person.objects.filter(email=email).order_by("pk")
            Person.objects.filter(pk__in=[p.pk for p in extras]).delete()
        with connection.schema_editor() as editor:
            editor.alter_field(Person, non_unique_email_field, live_email_field)
