"""
Regression test (CodeRabbit follow-up review of PR #734): firebase_token_login read the
Firebase token only from ?token=, a query string logged by browser history and reverse
proxy/CDN/load-balancer access logs. Fixed to prefer Authorization: JWT <token> while still
falling back to the query string, so already-deployed app builds keep working.
"""

from unittest.mock import patch

from django.test import TestCase


class TestFirebaseTokenLoginHeaderSource(TestCase):
    @patch("display.authentication.FirebaseTokenAuthentication.authenticate_credentials")
    def test_prefers_authorization_header_over_query_string(self, mock_authenticate_credentials):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create(email="firebase-header-test@example.com")
        mock_authenticate_credentials.return_value = (user, {})

        self.client.get(
            "/firebase_login/",
            data={"token": "stale-query-token"},
            HTTP_AUTHORIZATION="JWT header-token-value",
        )

        mock_authenticate_credentials.assert_called_once_with("header-token-value")

    @patch("display.authentication.FirebaseTokenAuthentication.authenticate_credentials")
    def test_falls_back_to_query_string_when_no_header_present(self, mock_authenticate_credentials):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create(email="firebase-fallback-test@example.com")
        mock_authenticate_credentials.return_value = (user, {})

        self.client.get("/firebase_login/", data={"token": "legacy-query-token"})

        mock_authenticate_credentials.assert_called_once_with("legacy-query-token")
