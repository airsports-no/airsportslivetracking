"""
Regression test (local code review, management-commands section, finding #8): flushredis ran
r.flushall() - wiping every Redis DB on the host, including the Celery broker, Channels layer,
and live-calculator heartbeats - with no confirmation prompt and no way to skip it for
scripted/automated use.
"""

from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase


class TestFlushredisConfirmation(TestCase):
    @patch("display.management.commands.flushredis.redis.Redis")
    @patch("builtins.input", return_value="no")
    def test_declining_the_prompt_does_not_flush(self, mock_input, mock_redis_cls):
        out = StringIO()
        call_command("flushredis", stdout=out)

        mock_redis_cls.return_value.flushall.assert_not_called()
        self.assertIn("Aborted", out.getvalue())

    @patch("display.management.commands.flushredis.redis.Redis")
    @patch("builtins.input", return_value="yes")
    def test_confirming_the_prompt_flushes(self, mock_input, mock_redis_cls):
        out = StringIO()
        call_command("flushredis", stdout=out)

        mock_redis_cls.return_value.flushall.assert_called_once()

    @patch("display.management.commands.flushredis.redis.Redis")
    @patch("builtins.input")
    def test_yes_flag_skips_the_prompt(self, mock_input, mock_redis_cls):
        out = StringIO()
        call_command("flushredis", "--yes", stdout=out)

        mock_input.assert_not_called()
        mock_redis_cls.return_value.flushall.assert_called_once()
