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

    @patch("display.authentication.FirebaseTokenAuthentication.authenticate_credentials")
    def test_accepts_lowercase_authorization_scheme(self, mock_authenticate_credentials):
        # RFC 9110: HTTP auth-scheme names are case-insensitive - "jwt" must be treated the
        # same as "JWT", not silently fall back to the (stale/absent) query string.
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create(email="firebase-case-test@example.com")
        mock_authenticate_credentials.return_value = (user, {})

        self.client.get(
            "/firebase_login/",
            data={"token": "stale-query-token"},
            HTTP_AUTHORIZATION="jwt lowercase-scheme-token",
        )

        mock_authenticate_credentials.assert_called_once_with("lowercase-scheme-token")


class TestFirebaseTokenLoginNextRedirect(TestCase):
    def _login(self, next_value):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create(email="firebase-next-test@example.com")
        with patch(
            "display.authentication.FirebaseTokenAuthentication.authenticate_credentials",
            return_value=(user, {}),
        ):
            return self.client.get(
                "/firebase_login/",
                data={"next": next_value},
                HTTP_AUTHORIZATION="JWT some-token",
            )

    def test_redirects_to_same_host_relative_path(self):
        response = self._login("/competition-map/1/2?mode=realtime")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/competition-map/1/2?mode=realtime")

    def test_rejects_absolute_external_url(self):
        response = self._login("https://evil.example.com/phish")
        self.assertEqual(response.url, "/")

    def test_rejects_protocol_relative_url(self):
        response = self._login("//evil.example.com/phish")
        self.assertEqual(response.url, "/")

    def test_defaults_to_root_without_next(self):
        response = self._login("")
        self.assertEqual(response.url, "/")
