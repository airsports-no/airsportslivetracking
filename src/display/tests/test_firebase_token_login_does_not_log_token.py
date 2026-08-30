"""
Regression test (CodeRabbit review of PR #734): firebase_token_login logged the raw Firebase
bearer token via logger.debug(f"Token {token}") - an active credential written to application
logs, replayable by anyone with log access until it expires.
"""

from unittest.mock import patch

from django.test import TestCase
from rest_framework.exceptions import AuthenticationFailed


class TestFirebaseTokenLoginDoesNotLogToken(TestCase):
    @patch(
        "display.authentication.FirebaseTokenAuthentication.authenticate_credentials",
        side_effect=AuthenticationFailed("invalid token"),
    )
    def test_the_raw_token_never_appears_in_logs(self, mock_authenticate):
        secret_token = "super-secret-firebase-bearer-token-value"
        with self.assertLogs("display.views", level="DEBUG") as captured:
            self.client.get("/firebase_login/", data={"token": secret_token})

        joined_output = "\n".join(captured.output)
        self.assertNotIn(
            secret_token,
            joined_output,
            "The raw Firebase token must never be written to logs - it's a live credential.",
        )
