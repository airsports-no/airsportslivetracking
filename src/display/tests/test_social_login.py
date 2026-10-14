import json
from unittest.mock import patch

from utilities.mock_utilities import TraccarMock

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from rest_framework import exceptions as drf_exceptions

from display.models import Person


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
        # the person sees this domain on the provider's consent screen
        self.assertContains(response, "auth.airsports.no")


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

    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def test_a_first_time_user_gets_a_person_profile(self, _traccar):
        self.user.first_name, self.user.last_name = "Ola", "Nordmann"
        self.user.save()
        self.assertFalse(Person.objects.filter(email="pilot@example.com").exists())
        with self.authenticate:
            self.post({"id_token": "token"})
        person = Person.objects.get(email="pilot@example.com")
        self.assertEqual((person.first_name, person.last_name), ("Ola", "Nordmann"))

    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def test_an_existing_person_is_left_alone(self, _traccar):
        Person.objects.create(first_name="Existing", last_name="Pilot", email="pilot@example.com")
        with self.authenticate:
            self.post({"id_token": "token"})
        self.assertEqual(Person.objects.get(email="pilot@example.com").first_name, "Existing")

    def test_a_failure_to_create_the_person_does_not_block_the_sign_in(self):
        with (
            self.authenticate,
            patch("display.models.Person.objects.get_or_create", side_effect=RuntimeError("traccar")),
        ):
            response = self.post({"id_token": "token"})
        self.assertEqual(response.status_code, 200)
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
        self.assertNotIn("detail", response.json())  # the reason is for developers only, see below
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(DEBUG=True)
    def test_the_reason_is_included_for_developers(self):
        with patch(
            "display.authentication.FirebaseTokenAuthentication.authenticate_credentials",
            side_effect=drf_exceptions.AuthenticationFailed("Token used too early"),
        ):
            response = self.post({"id_token": "token"})
        self.assertEqual(response.status_code, 401)
        self.assertIn("Token used too early", response.json()["detail"])

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


class DesktopSignInTest(TestCase):
    """Google / Apple sign-in for the MSFS client: browser page, loopback callback, code + verifier for a custom token."""

    VERIFIER = "v" * 50
    # base64url(sha256(VERIFIER)) without padding, as the client sends it
    CHALLENGE = __import__("base64").urlsafe_b64encode(__import__("hashlib").sha256(b"v" * 50).digest()).rstrip(b"=").decode()
    STATE = "s" * 32

    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.user = get_user_model().objects.create_user(username="pilot@example.com", email="pilot@example.com")
        self.authenticate = patch(
            "display.authentication.FirebaseTokenAuthentication.authenticate_credentials",
            return_value=(self.user, {"uid": "firebase-uid-1"}),
        )
        self.person = patch("display.views_social_login._ensure_person")
        self.person.start()
        self.addCleanup(self.person.stop)

    def query(self, **overrides):
        params = {"port": "53682", "state": self.STATE, "code_challenge": self.CHALLENGE}
        params.update(overrides)
        return "&".join(f"{k}={v}" for k, v in params.items())

    def complete(self, client=None, **overrides):
        client = client or Client(enforce_csrf_checks=False)
        with self.authenticate:
            return client.post(
                f"{reverse('desktop_sign_in_complete')}?{self.query(**overrides)}",
                json.dumps({"id_token": "token"}),
                content_type="application/json",
            )

    def code_from(self, response) -> str:
        redirect = response.json()["redirect"]
        self.assertTrue(redirect.startswith("http://127.0.0.1:53682/callback?code="), redirect)
        self.assertTrue(redirect.endswith(f"&state={self.STATE}"))
        return redirect.split("code=")[1].split("&")[0]

    def token(self, code, verifier=None):
        return self.client.post(
            reverse("desktop_sign_in_token"),
            json.dumps({"code": code, "code_verifier": verifier or self.VERIFIER}),
            content_type="application/json",
        )

    def test_the_page_has_the_buttons_and_finishes_at_the_desktop_endpoint(self):
        response = self.client.get(f"{reverse('desktop_sign_in')}?{self.query(provider='apple')}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-provider="apple"')
        self.assertNotContains(response, 'data-provider="google"')  # the client asked for Apple
        self.assertContains(response, f"{reverse('desktop_sign_in_complete')}?port=53682&amp;state={self.STATE}")
        self.assertEqual(response["Cross-Origin-Opener-Policy"], "same-origin-allow-popups")
        self.assertIn("csrftoken", response.cookies)  # SocialLogin.tsx sends it

    def test_a_bad_link_is_refused(self):
        for overrides in ({"port": "80"}, {"port": "x"}, {"state": "short"}, {"code_challenge": "abc"}, {"provider": "facebook"}):
            response = self.client.get(f"{reverse('desktop_sign_in')}?{self.query(**overrides)}")
            self.assertEqual(response.status_code, 400, overrides)
            self.assertNotContains(response, "data-provider", status_code=400)

    def test_the_client_gets_a_custom_token_for_the_same_firebase_user_once(self):
        response = self.complete()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)  # no website session: the sign-in is for the client
        code = self.code_from(response)
        with patch("display.auth_backends.FirebaseMigrationBackend._initialize_firebase"), patch(
            "firebase_admin.auth.create_custom_token", return_value=b"custom-token"
        ) as create:
            first = self.token(code)
            second = self.token(code)
        self.assertEqual(first.json(), {"custom_token": "custom-token"})
        create.assert_called_once_with("firebase-uid-1")
        self.assertEqual(second.status_code, 400)  # a code works once

    def test_the_code_is_useless_without_the_clients_secret(self):
        code = self.code_from(self.complete())
        with patch("firebase_admin.auth.create_custom_token") as create:
            response = self.token(code, verifier="w" * 50)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(self.token(code).status_code, 400)  # and it is gone after the failed try
        create.assert_not_called()

    def test_a_token_firebase_does_not_accept_is_refused(self):
        failing = patch(
            "display.authentication.FirebaseTokenAuthentication.authenticate_credentials",
            side_effect=drf_exceptions.AuthenticationFailed("bad"),
        )
        with failing:
            response = Client().post(
                f"{reverse('desktop_sign_in_complete')}?{self.query()}",
                json.dumps({"id_token": "token"}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.json())

    def test_the_complete_step_needs_the_csrf_token_like_the_login_page(self):
        response = self.complete(client=Client(enforce_csrf_checks=True))
        self.assertEqual(response.status_code, 403)

    @override_settings(SOCIAL_LOGIN_ENABLED=False)
    def test_nothing_works_when_social_login_is_off(self):
        response = self.client.get(f"{reverse('desktop_sign_in')}?{self.query()}")
        self.assertNotContains(response, "data-provider")
        self.assertEqual(self.complete().status_code, 404)

    def test_the_done_page_sends_the_person_back_to_the_client(self):
        self.assertContains(self.client.get(reverse("desktop_sign_in_done")), "Go back to the Airsports client")
