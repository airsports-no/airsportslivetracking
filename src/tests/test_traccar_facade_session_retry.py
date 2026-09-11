"""
Regression test for Sentry issue PYTHON-DJANGO-X: get_positions_for_device_id (and every other
Traccar._request call site) logged an error and returned an empty/default result whenever
Traccar rejected our cached session with 401 - e.g. because Traccar restarted mid-flight and
invalidated every in-memory session immediately, while Traccar.session's own cache is purely
time-based (SESSION_LIFETIME) and has no way to notice that early. Every call using the stale
session then failed with 401 until SESSION_LIFETIME (1 hour) naturally elapsed.

Fixed by having Traccar._request re-authenticate and retry once whenever the server responds
with 401, instead of treating it like any other failure.
"""

import datetime
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from traccar_facade import Traccar


def _make_response(status_code, json_data=None):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data if json_data is not None else []
    response.url = "http://traccar.example/api/positions"
    response.text = ""
    return response


class TestTraccarSessionRetryOn401(SimpleTestCase):
    def setUp(self):
        self.traccar = Traccar("http", "traccar.example", "user@example.com", "password")

    @patch.object(Traccar, "get_authenticated_session")
    def test_401_triggers_reauthentication_and_retry(self, mock_get_authenticated_session):
        stale_session = MagicMock()
        stale_session.get.return_value = _make_response(401)
        fresh_session = MagicMock()
        fresh_session.get.return_value = _make_response(200, json_data=[{"id": 1}])
        mock_get_authenticated_session.side_effect = [stale_session, fresh_session]

        result = self.traccar.get_positions_for_device_id(
            14565,
            datetime.datetime.now(datetime.timezone.utc),
            datetime.datetime.now(datetime.timezone.utc),
        )

        self.assertEqual(result, [{"id": 1}])
        self.assertEqual(mock_get_authenticated_session.call_count, 2)
        stale_session.get.assert_called_once()
        fresh_session.get.assert_called_once()

    @patch.object(Traccar, "get_authenticated_session")
    def test_401_on_retry_is_not_retried_again(self, mock_get_authenticated_session):
        # Both attempts get 401 (e.g. genuinely wrong credentials) - must not loop forever.
        session_a = MagicMock()
        session_a.get.return_value = _make_response(401)
        session_b = MagicMock()
        session_b.get.return_value = _make_response(401)
        mock_get_authenticated_session.side_effect = [session_a, session_b]

        result = self.traccar.get_positions_for_device_id(
            14565,
            datetime.datetime.now(datetime.timezone.utc),
            datetime.datetime.now(datetime.timezone.utc),
        )

        self.assertEqual(result, [])
        self.assertEqual(mock_get_authenticated_session.call_count, 2)
        session_a.get.assert_called_once()
        session_b.get.assert_called_once()

    @patch.object(Traccar, "get_authenticated_session")
    def test_non_401_failure_is_not_retried(self, mock_get_authenticated_session):
        session = MagicMock()
        session.get.return_value = _make_response(500)
        mock_get_authenticated_session.return_value = session

        result = self.traccar.get_positions_for_device_id(
            14565,
            datetime.datetime.now(datetime.timezone.utc),
            datetime.datetime.now(datetime.timezone.utc),
        )

        self.assertEqual(result, [])
        mock_get_authenticated_session.assert_called_once()
        session.get.assert_called_once()
