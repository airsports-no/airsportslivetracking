import datetime
from unittest.mock import MagicMock, patch

from django.core import mail
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from display.services import smtp_credit_monitor
from display.services.smtp_credit_monitor import SmtpPlanStatus, check_smtp_credits, fetch_active_plan, warnings_for

TODAY = datetime.date(2027, 11, 9)
PLANS = [
    {"smtp_limit": 50000, "smtp_count": 4, "plan_expiration": "2027-11-23", "expired": False, "active": True},
    {"smtp_limit": 50000, "smtp_count": 0, "plan_expiration": "2026-11-19", "expired": True, "active": False},
]


def plan(sent=4, expiration=datetime.date(2027, 11, 23)):
    return SmtpPlanStatus(limit=50000, sent=sent, expiration=expiration)


@override_settings(
    EMAIL_HOST="pro.turbo-smtp.com",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    SMTP_CREDIT_WARNING_EMAIL="admin@example.com",
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class SmtpCreditMonitorTest(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_fetch_active_plan_ignores_expired_plans(self):
        response = MagicMock()
        response.json.return_value = PLANS
        with patch.object(smtp_credit_monitor.requests, "get", return_value=response):
            status = fetch_active_plan()
        self.assertEqual(status, plan())
        self.assertEqual(status.remaining, 49996)

    def test_fetch_active_plan_without_an_active_plan(self):
        response = MagicMock()
        response.json.return_value = PLANS[1:]
        with patch.object(smtp_credit_monitor.requests, "get", return_value=response):
            self.assertIsNone(fetch_active_plan())

    def test_no_warning_long_before_expiry(self):
        self.assertEqual(warnings_for(plan(), datetime.date(2027, 6, 1)), [])

    def test_warns_two_weeks_before_expiry(self):
        self.assertEqual(len(warnings_for(plan(), TODAY)), 1)

    def test_no_warning_between_the_warning_days(self):
        self.assertEqual(warnings_for(plan(), TODAY + datetime.timedelta(days=1)), [])

    def test_low_credit_warns_once_per_reminder_period(self):
        low = plan(sent=46000)
        self.assertEqual(len(warnings_for(low, datetime.date(2027, 6, 1))), 1)
        self.assertEqual(warnings_for(low, datetime.date(2027, 6, 2)), [])

    def test_check_sends_the_warning_e_mail(self):
        with patch.object(smtp_credit_monitor, "fetch_active_plan", return_value=plan()):
            check_smtp_credits(TODAY)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["admin@example.com"])
        self.assertIn("2027-11-23", mail.outbox[0].body)

    def test_check_logs_an_error_without_a_plan(self):
        with patch.object(smtp_credit_monitor, "fetch_active_plan", return_value=None):
            with self.assertLogs(smtp_credit_monitor.logger, level="ERROR"):
                check_smtp_credits(TODAY)
        self.assertEqual(mail.outbox, [])

    @override_settings(EMAIL_HOST="")
    def test_check_does_nothing_without_turbosmtp(self):
        with patch.object(smtp_credit_monitor, "fetch_active_plan") as fetch:
            self.assertEqual(check_smtp_credits(TODAY), [])
        fetch.assert_not_called()
