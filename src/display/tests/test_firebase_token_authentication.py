"""
Regression tests for FirebaseTokenAuthentication (display/authentication.py), the replacement
for the third-party drf_firebase_auth package. Firebase itself (verify_id_token/get_user) is
mocked throughout - there's no way to mint a real Firebase ID token in a unit test - so these
tests confirm the class's own logic (user lookup/creation/rejection branches) matches the
original package's observed behavior; a real end-to-end token flow still needs manual
verification against a live Firebase project before this is trusted in production (see the
approved migration plan).
"""

from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import AuthenticationFailed

from display.authentication import FirebaseTokenAuthentication

User = get_user_model()


def _make_firebase_user(email="pilot@example.com", uid="firebase-uid-123", email_verified=True, display_name=None):
    firebase_user = MagicMock()
    firebase_user.email = email
    firebase_user.uid = uid
    firebase_user.email_verified = email_verified
    firebase_user.display_name = display_name
    firebase_user.provider_data = []
    return firebase_user


@patch("display.authentication.FirebaseMigrationBackend._initialize_firebase", return_value=None)
@patch("display.authentication.firebase_auth.verify_id_token")
@patch("display.authentication.firebase_auth.get_user")
class TestFirebaseTokenAuthentication(TestCase):
    def test_existing_active_user_is_authenticated(self, mock_get_user, mock_verify, mock_init):
        existing = User.objects.create(email="pilot@example.com", is_active=True)
        mock_verify.return_value = {"uid": "firebase-uid-123"}
        mock_get_user.return_value = _make_firebase_user()

        auth = FirebaseTokenAuthentication()
        user, decoded_token = auth.authenticate_credentials("some-token")

        self.assertEqual(user.pk, existing.pk)
        self.assertEqual(decoded_token, {"uid": "firebase-uid-123"})
        existing.refresh_from_db()
        self.assertIsNotNone(existing.last_login)

    def test_existing_inactive_user_is_rejected(self, mock_get_user, mock_verify, mock_init):
        User.objects.create(email="pilot@example.com", is_active=False)
        mock_verify.return_value = {"uid": "firebase-uid-123"}
        mock_get_user.return_value = _make_firebase_user()

        auth = FirebaseTokenAuthentication()
        with self.assertRaises(AuthenticationFailed):
            auth.authenticate_credentials("some-token")

    def test_unknown_email_auto_creates_local_user(self, mock_get_user, mock_verify, mock_init):
        mock_verify.return_value = {"uid": "firebase-uid-123"}
        mock_get_user.return_value = _make_firebase_user(
            email="newpilot@example.com", display_name="Jane Doe"
        )

        auth = FirebaseTokenAuthentication()
        user, _ = auth.authenticate_credentials("some-token")

        self.assertEqual(user.email, "newpilot@example.com")
        self.assertEqual(user.username, "firebase-uid-123")
        self.assertEqual(user.first_name, "Jane")
        self.assertEqual(user.last_name, "Doe")
        self.assertTrue(User.objects.filter(email="newpilot@example.com").exists())

    def test_display_name_with_more_than_two_parts_is_not_split(self, mock_get_user, mock_verify, mock_init):
        mock_verify.return_value = {"uid": "firebase-uid-123"}
        mock_get_user.return_value = _make_firebase_user(
            email="newpilot@example.com", display_name="Jane Middle Doe"
        )

        auth = FirebaseTokenAuthentication()
        user, _ = auth.authenticate_credentials("some-token")

        self.assertEqual(user.first_name, "")
        self.assertEqual(user.last_name, "")

    def test_unverified_email_is_rejected(self, mock_get_user, mock_verify, mock_init):
        mock_verify.return_value = {"uid": "firebase-uid-123"}
        mock_get_user.return_value = _make_firebase_user(email_verified=False)

        auth = FirebaseTokenAuthentication()
        with self.assertRaises(AuthenticationFailed):
            auth.authenticate_credentials("some-token")

    def test_invalid_or_revoked_token_is_rejected(self, mock_get_user, mock_verify, mock_init):
        mock_verify.side_effect = Exception("Token revoked")

        auth = FirebaseTokenAuthentication()
        with self.assertRaises(AuthenticationFailed):
            auth.authenticate_credentials("some-token")

    def test_email_falls_back_to_provider_data_when_missing(self, mock_get_user, mock_verify, mock_init):
        existing = User.objects.create(email="provider@example.com", is_active=True)
        mock_verify.return_value = {"uid": "firebase-uid-123"}
        firebase_user = _make_firebase_user(email=None)
        provider = MagicMock()
        provider.email = "provider@example.com"
        firebase_user.provider_data = [provider]
        mock_get_user.return_value = firebase_user

        auth = FirebaseTokenAuthentication()
        user, _ = auth.authenticate_credentials("some-token")

        self.assertEqual(user.pk, existing.pk)


@patch("display.authentication.FirebaseTokenAuthentication.authenticate_credentials")
class TestFirebaseTokenLoginView(TestCase):
    def test_successful_token_logs_user_in_and_redirects(self, mock_authenticate):
        user = User.objects.create(email="pilot@example.com", is_active=True)
        mock_authenticate.return_value = (user, {"uid": "x"})

        response = self.client.get("/firebase_login/?token=valid-token")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_failed_token_redirects_with_error_message_and_no_login(self, mock_authenticate):
        mock_authenticate.side_effect = AuthenticationFailed("bad token")

        response = self.client.get("/firebase_login/?token=invalid-token")

        self.assertEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)
