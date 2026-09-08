"""
Regression test for Sentry issue PYTHON-DJANGO-G: notify_flight_order (dispatched independently
of generate_flight_order - see broadcast_navigation_task_orders in views_api.py, which resends
orders to already-selected contestants) crashed with
AttributeError: 'NoneType' object has no attribute 'send_email' whenever no EmailMapLink existed
yet for the contestant (flight order never generated, or its link deleted by a later regeneration
racing with this call). Fixed to fail with a clear ValueError instead.
"""

import datetime
from unittest.mock import patch

from django.core.cache import cache
from django.test import TransactionTestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Aeroplane, Contest, Contestant, Crew, EmailMapLink, NavigationTask, Person, Route, Team
from display.tasks import notify_flight_order
from utilities.mock_utilities import TraccarMock


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestNotifyFlightOrderMissingMailLink(TransactionTestCase):
    # TransactionTestCase, not TestCase: notify_flight_order's success path calls
    # connections.all()[...].close_if_unusable_or_obsolete() (real Celery-worker connection
    # hygiene), which conflicts with TestCase's savepoint-based per-test isolation - the next
    # test's setUp fails with TransactionManagementError otherwise. Same reasoning as
    # test_idempotent_restart.py for similarly connection-managing task code.
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        self.contest = Contest.objects.create(
            name="Notify Contest",
            is_public=False,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            location="60, 11",
        )
        route = Route.objects.create(name="Route")
        now = datetime.datetime.now(datetime.timezone.utc)
        self.navigation_task = NavigationTask.create(
            name="Notify Task",
            original_scorecard=get_default_scorecard(),
            route=route,
            contest=self.contest,
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="A", last_name="B", email="pilot@example.com"))
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-NFO"))
        self.contestant = Contestant.objects.create(
            team=team,
            navigation_task=self.navigation_task,
            takeoff_time=now + datetime.timedelta(hours=1),
            finished_by_time=now + datetime.timedelta(hours=2),
            tracker_start_time=now + datetime.timedelta(minutes=30),
            tracker_device_id="test_device",
            contestant_number=1,
        )

    def test_notify_without_a_generated_flight_order_fails_clearly_not_with_attributeerror(self, *args):
        self.assertFalse(EmailMapLink.objects.filter(contestant=self.contestant).exists())

        # notify_flight_order catches everything internally (it's a Celery task; the failure
        # is recorded via append_cache_dict rather than propagated) - it never raises out to
        # the caller, matching its behavior before this fix too. What matters is *what* got
        # logged/recorded: a clear ValueError naming the contestant, not an opaque
        # AttributeError from calling send_email on None.
        with self.assertLogs("display.tasks", level="ERROR") as logs:
            notify_flight_order(self.contestant.pk, "pilot@example.com", "A")

        log_output = "\n".join(logs.output)
        self.assertIn(str(self.contestant.pk), log_output)
        self.assertIn("ValueError", log_output)
        self.assertNotIn("AttributeError", log_output)

        failures = cache.get(f"transmit_failed_flight_orders_map_{self.navigation_task.pk}") or {}
        self.assertIn(self.contestant.pk, failures)

    def test_notify_with_a_generated_flight_order_still_sends(self, *args):
        mail_link = EmailMapLink.objects.create(contestant=self.contestant, orders=b"%PDF-existing")
        with patch.object(EmailMapLink, "send_email") as mock_send_email:
            notify_flight_order(self.contestant.pk, "pilot@example.com", "A")
        mock_send_email.assert_called_once_with("pilot@example.com", "A")
