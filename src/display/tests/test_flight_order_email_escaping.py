"""
The flight order email puts user-controlled names (pilot first name, task name, contest name) into an
HTML body. They must be escaped there, while the plain-text body keeps them verbatim.
"""

import datetime
import uuid
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from display.models.email_map_link import EmailMapLink


class TestFlightOrderEmailEscaping(SimpleTestCase):
    def _send(self, task_name, contest_name, first_name):
        when = datetime.datetime(2026, 5, 1, 9, 30, tzinfo=datetime.timezone.utc)
        link = MagicMock()
        link.id = uuid.uuid4()
        link.PLAINTEXT_SIGNATURE = "-- plain"
        link.HTML_SIGNATURE = "-- html"
        link.contestant.adaptive_start = False
        link.contestant.starting_point_time_local = when
        link.contestant.tracker_start_time_local = when
        link.contestant.navigation_task.name = task_name
        link.contestant.navigation_task.contest.name = contest_name
        with patch("display.models.email_map_link.send_mail") as send_mail:
            EmailMapLink.send_email(link, "pilot@example.com", first_name)
        return send_mail.call_args

    def test_html_body_escapes_names(self):
        call = self._send("<b>Task</b>", "<script>alert(1)</script>", "<i>Eve</i>")
        html = call.kwargs["html_message"]
        self.assertNotIn("<script>", html)
        self.assertNotIn("<b>Task</b>", html)
        self.assertNotIn("<i>Eve</i>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_plain_text_body_keeps_names_verbatim(self):
        call = self._send("<b>Task</b>", "Cup & Co", "Eve")
        plain = call.args[1]
        self.assertIn("<b>Task</b>", plain)
        self.assertIn("Cup & Co", plain)
        self.assertNotIn("&amp;", plain)

    def test_html_body_has_a_single_link_and_the_contest_name(self):
        call = self._send("Task", "Spring Cup", "Eve")
        html = call.kwargs["html_message"]
        self.assertEqual(html.count("<a href="), 1)
        self.assertIn("Spring Cup", html)
