"""
Regression test for Sentry issue PYTHON-DJANGO-M: FirebaseMigrationBackend._initialize_firebase
logged "Failed to initialize Firebase Admin app: The default Firebase app already exists" as an
error whenever two concurrent requests raced each other into initialization (most likely right
after a worker cold-starts post-deploy, when the first requests to hit auth code all still see
Firebase as uninitialized).

Root cause: _initialize_firebase does a check-then-act - firebase_admin.get_app() raises
ValueError if not yet initialized, then it calls firebase_admin.initialize_app(cred) - and those
two calls aren't atomic across concurrent requests. If a second request wins the race between
them, its own initialize_app() call raises ValueError("The default Firebase app already exists"),
which was being logged at error level even though the outcome (a default app existing) is exactly
what the method is trying to achieve.
"""

from unittest.mock import patch

from django.test import TestCase

from display.auth_backends import FirebaseMigrationBackend


@patch("os.path.exists", return_value=True)
@patch("display.auth_backends.credentials.Certificate")
@patch("display.auth_backends.firebase_admin.get_app", side_effect=ValueError("not initialized"))
class TestFirebaseMigrationBackendInitRace(TestCase):
    @patch(
        "display.auth_backends.firebase_admin.initialize_app",
        side_effect=ValueError("The default Firebase app already exists."),
    )
    @patch("display.auth_backends.logger")
    def test_already_exists_race_is_logged_as_benign_not_error(
        self, mock_logger, mock_initialize_app, mock_get_app, mock_certificate, mock_exists
    ):
        FirebaseMigrationBackend()._initialize_firebase()

        mock_logger.error.assert_not_called()
        mock_logger.info.assert_any_call("Firebase Admin app was already initialized by a concurrent request")

    @patch(
        "display.auth_backends.firebase_admin.initialize_app", side_effect=RuntimeError("credential file is corrupt")
    )
    @patch("display.auth_backends.logger")
    def test_other_initialize_errors_are_still_logged_as_error(
        self, mock_logger, mock_initialize_app, mock_get_app, mock_certificate, mock_exists
    ):
        FirebaseMigrationBackend()._initialize_firebase()

        mock_logger.error.assert_called_once()
        self.assertIn("Failed to initialize Firebase Admin app", mock_logger.error.call_args[0][0])
