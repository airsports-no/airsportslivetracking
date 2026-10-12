import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from rest_framework import exceptions as drf_exceptions


class SocialLoginPagesTest(TestCase):
    def test_the_login_page_has_the_google_and_apple_buttons_and_lets_popups_talk_back(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, 'data-provider="google"')
        self.assertContains(response, 'data-provider="apple"')
        self.assertContains(response, 'id="firebase-web-config"')
        self.assertEqual(response["Cross-Origin-Opener-Policy"], "same-origin-allow-popups")
        self.assertContains(response, 'name="username"')  # the password form is still there

    def test_apple_hide_my_email_is_explained_on_both_pages(self):
        for name in ("login", "signup"):
            response = self.client.get(reverse(name))
            self.assertContains(response, "data-apple-hide-email-note")
            self.assertContains(response, "Hide My Email")
            self.assertContains(response, "Share My Email")

    def test_the_signup_page_has_the_buttons_too(self):
        response = self.client.get(reverse("signup"))
        self.assertContains(response, 'data-provider="google"')
        self.assertEqual(response["Cross-Origin-Opener-Policy"], "same-origin-allow-popups")

    @override_settings(SOCIAL_LOGIN_ENABLED=False)
    def test_the_buttons_and_the_header_are_off_when_switched_off(self):
        response = self.client.get(reverse("login"))
        self.assertNotContains(response, 'data-provider="google"')
        self.assertEqual(response["Cross-Origin-Opener-Policy"], "same-origin")

    def test_the_web_config_is_the_public_firebase_config(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, "airsports-613ce")


class FirebaseWebLoginTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="pilot@example.com", email="pilot@example.com")
        self.url = reverse("firebase_web_login")
        self.authenticate = patch(
            "display.authentication.FirebaseTokenAuthentication.authenticate_credentials",
            return_value=(self.user, {"uid": "abc"}),
        )

    def post(self, body, client=None):
        return (client or self.client).post(self.url, json.dumps(body), content_type="application/json")

    def test_a_valid_token_starts_the_session(self):
        with self.authenticate as authenticate:
            response = self.post({"id_token": "token", "next": "/mission-dashboard/"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"redirect": "/mission-dashboard/"})
        authenticate.assert_called_once_with("token")
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_the_session_is_valid_on_the_next_request(self):
        with self.authenticate:
            self.post({"id_token": "token"})
        # the recorded backend must be one of AUTHENTICATION_BACKENDS or Django drops the session
        self.assertEqual(self.client.get("/api/v1/userprofile/my_contest_teams/").status_code, 200)

    def test_it_never_redirects_to_another_site(self):
        with self.authenticate:
            for next_url in ("https://evil.example/", "//evil.example/", "javascript:alert(1)", ""):
                self.client.logout()
                self.assertEqual(self.post({"id_token": "token", "next": next_url}).json(), {"redirect": "/"})

    def test_a_rejected_token_does_not_log_in(self):
        with patch(
            "display.authentication.FirebaseTokenAuthentication.authenticate_credentials",
            side_effect=drf_exceptions.AuthenticationFailed("Email address of this user has not been verified."),
        ):
            response = self.post({"id_token": "token"})
        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.json())
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_missing_or_malformed_requests(self):
        self.assertEqual(self.post({}).status_code, 400)
        self.assertEqual(self.post({"id_token": 5}).status_code, 400)
        self.assertEqual(self.client.post(self.url, "not json", content_type="application/json").status_code, 400)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_it_needs_the_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        with self.authenticate:
            response = client.post(self.url, json.dumps({"id_token": "token"}), content_type="application/json")
        self.assertEqual(response.status_code, 403)

    @override_settings(SOCIAL_LOGIN_ENABLED=False)
    def test_it_is_off_when_switched_off(self):
        with self.authenticate:
            self.assertEqual(self.post({"id_token": "token"}).status_code, 404)
