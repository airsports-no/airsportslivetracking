"""
The signup form against bots (display/utilities/signup_protection.py): a bot made over seventy "Test User" accounts in
two days, each a Firebase account with a verification email sent to a stranger's address and, at the time, a local
user and person row. A signup now makes only the unverified Firebase account, the local profile coming with the first
verified sign-in.
"""

import time
from unittest.mock import MagicMock, patch

from django.core import signing
from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from display.models import MyUser, Person
from utilities.mock_utilities import TraccarMock
from display.utilities import signup_protection
from display.utilities.person_provisioning import split_display_name

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "signup-protection-tests"}}


class TestSplitDisplayName(SimpleTestCase):
    def test_the_last_word_is_the_last_name(self):
        self.assertEqual(split_display_name("Jane Doe"), ("Jane", "Doe"))
        self.assertEqual(split_display_name("Mary Ann Smith"), ("Mary Ann", "Smith"))

    def test_one_word_is_a_first_name_and_nothing_gives_nothing(self):
        self.assertEqual(split_display_name("Jane"), ("Jane", ""))
        self.assertEqual(split_display_name(""), ("", ""))
        self.assertEqual(split_display_name(None), ("", ""))


class TestFormToken(SimpleTestCase):
    def test_a_form_submitted_at_once_is_too_fast(self):
        self.assertEqual(signup_protection.token_problem(signup_protection.new_form_token()), "too_fast")

    def test_a_form_filled_in_at_a_human_pace_is_fine(self):
        token = signup_protection.new_form_token()
        self.assertIsNone(signup_protection.token_problem(token, now=time.time() + 30))

    def test_missing_forged_and_old_tokens(self):
        self.assertEqual(signup_protection.token_problem(""), "missing")
        self.assertEqual(signup_protection.token_problem(None), "missing")
        self.assertEqual(signup_protection.token_problem("not-a-token"), "invalid")
        token = signup_protection.new_form_token()
        with patch("time.time", return_value=time.time() + signup_protection.MAXIMUM_SECONDS + 60):
            self.assertEqual(signup_protection.token_problem(token), "expired")
        self.assertEqual(signup_protection.token_problem(signing.dumps(5, salt="another-salt")), "invalid")


class TestClientIp(SimpleTestCase):
    def test_behind_the_load_balancer_it_is_the_address_before_the_last(self):
        request = RequestFactory().get("/", HTTP_X_FORWARDED_FOR="6.6.6.6, 203.0.113.9, 130.211.0.1")
        self.assertEqual(signup_protection.client_ip(request), "203.0.113.9")

    def test_without_a_proxy_it_is_the_remote_address(self):
        request = RequestFactory().get("/", REMOTE_ADDR="198.51.100.4")
        self.assertEqual(signup_protection.client_ip(request), "198.51.100.4")


@override_settings(CACHES=LOCMEM)
class TestRateLimit(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_the_sixth_signup_within_the_hour_from_one_address_is_refused(self):
        results = [signup_protection.over_limit("203.0.113.50") for _ in range(6)]
        self.assertEqual(results, [False] * 5 + [True])

    def test_another_address_is_not_affected(self):
        for _ in range(6):
            signup_protection.over_limit("203.0.113.51")
        self.assertFalse(signup_protection.over_limit("203.0.113.52"))


@override_settings(CACHES=LOCMEM)
class TestSignupView(TestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse("signup")

    def data(self, **overrides):
        data = {
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "jane.doe@example.com",
            "country": "NO",
            "password": "longenough",
            "password_confirm": "longenough",
            "form_started": signing.dumps(int(time.time()) - 30, salt=signup_protection.SALT),
            "website": "",
        }
        data.update(overrides)
        return data

    def post(self, data, ip="203.0.113.7"):
        firebase_user = MagicMock()
        response_ok = MagicMock()
        response_ok.json.return_value = {"idToken": "token"}
        with (
            patch("display.auth_backends.FirebaseMigrationBackend._initialize_firebase"),
            patch("firebase_admin.auth.create_user", return_value=firebase_user) as create_user,
            patch("requests.post", return_value=response_ok),
        ):
            response = self.client.post(self.url, data, REMOTE_ADDR=ip)
        return response, create_user

    def test_a_signup_makes_the_firebase_account_and_no_local_rows(self):
        response, create_user = self.post(self.data())
        create_user.assert_called_once()
        self.assertEqual(create_user.call_args.kwargs["display_name"], "Jane Doe")
        self.assertTemplateUsed(response, "registration/signup_success.html")
        self.assertFalse(MyUser.objects.filter(email="jane.doe@example.com").exists())
        self.assertFalse(Person.objects.filter(email="jane.doe@example.com").exists())

    def test_the_form_shows_the_hidden_field_and_a_time_stamp(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'name="form_started"')
        self.assertContains(response, 'name="website"')

    def test_a_filled_in_honeypot_is_told_it_worked_and_nothing_is_made(self):
        response, create_user = self.post(self.data(website="https://spam.example"))
        create_user.assert_not_called()
        self.assertTemplateUsed(response, "registration/signup_success.html")

    def test_a_form_without_a_time_stamp_is_refused_and_given_a_fresh_one(self):
        response, create_user = self.post(self.data(form_started=""))
        create_user.assert_not_called()
        self.assertTemplateUsed(response, "registration/signup.html")
        self.assertContains(response, "expired")
        self.assertContains(response, 'name="form_started"')

    def test_a_form_submitted_at_once_is_refused(self):
        response, create_user = self.post(self.data(form_started=signup_protection.new_form_token()))
        create_user.assert_not_called()
        self.assertContains(response, "That was quick")

    def test_the_sixth_signup_from_one_address_is_refused(self):
        for index in range(5):
            _, create_user = self.post(self.data(email=f"user{index}@example.com"), ip="203.0.113.99")
            create_user.assert_called_once()
        response, create_user = self.post(self.data(email="user5@example.com"), ip="203.0.113.99")
        create_user.assert_not_called()
        self.assertContains(response, "Too many sign-ups")


class TestFirstVerifiedSignIn(TestCase):
    """The local user and person are made when the verified address first signs in, with the names of the signup."""

    def sign_in(self, display_name, email_verified=True):
        from django.contrib.auth import authenticate

        firebase_user = MagicMock(email_verified=email_verified, display_name=display_name)
        with (
            patch("display.auth_backends.FirebaseMigrationBackend._initialize_firebase"),
            patch("display.auth_backends.FirebaseMigrationBackend._verify_firebase_password", return_value={"idToken": "x"}),
            patch("firebase_admin.auth.get_user_by_email", return_value=firebase_user),
            patch("display.signals.get_traccar_instance", return_value=TraccarMock),
        ):
            return authenticate(request=None, username="New.Pilot@Example.com", password="longenough")

    def test_a_verified_first_sign_in_makes_the_user_and_person_with_the_names(self):
        user = self.sign_in("Mary Ann Smith")
        self.assertIsNotNone(user)
        self.assertEqual((user.first_name, user.last_name), ("Mary Ann", "Smith"))
        person = Person.objects.get(email="new.pilot@example.com")
        self.assertEqual((person.first_name, person.last_name), ("Mary Ann", "Smith"))

    def test_an_unverified_address_gets_nothing(self):
        self.assertIsNone(self.sign_in("Test User", email_verified=False))
        self.assertFalse(MyUser.objects.filter(email="new.pilot@example.com").exists())
        self.assertFalse(Person.objects.filter(email="new.pilot@example.com").exists())
