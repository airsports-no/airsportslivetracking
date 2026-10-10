from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db.models import ProtectedError
from django.test import TestCase
from rest_framework.test import APIClient

from display.models import Person
from utilities.mock_utilities import TraccarMock

URL = "/api/v1/userprofile/delete_account/"


class TestAccountDeletionApi(TestCase):
    def setUp(self):
        for target in ("display.signals.get_traccar_instance",):
            patcher = patch(target, return_value=TraccarMock)
            patcher.start()
            self.addCleanup(patcher.stop)
        firebase = patch("display.services.account_deletion._delete_firebase_user", return_value=True)
        self.firebase_delete = firebase.start()
        self.addCleanup(firebase.stop)
        email = patch("display.models.MyUser.send_deletion_email")
        self.deletion_email = email.start()
        self.addCleanup(email.stop)

        self.User = get_user_model()
        self.user = self.User.objects.create(username="pilot", email="pilot@example.com", first_name="Pi", last_name="Lot")
        self.person = Person.objects.create(first_name="Pi", last_name="Lot", email="pilot@example.com", validated=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_deletes_login_profile_and_firebase_account(self):
        response = self.client.delete(URL, {"email": "Pilot@Example.com"}, format="json")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(self.User.objects.filter(email="pilot@example.com").exists())
        self.assertFalse(Person.objects.filter(email="pilot@example.com").exists())
        self.firebase_delete.assert_called_once_with("pilot@example.com")
        self.deletion_email.assert_called_once()

    def test_requires_matching_email_confirmation(self):
        for body in ({}, {"email": "someone@else.com"}):
            response = self.client.delete(URL, body, format="json")
            self.assertEqual(response.status_code, 400)
        self.assertTrue(self.User.objects.filter(email="pilot@example.com").exists())
        self.assertTrue(Person.objects.filter(email="pilot@example.com").exists())
        self.firebase_delete.assert_not_called()

    def test_person_referenced_by_a_team_is_anonymized_not_deleted(self):
        with patch("display.services.account_deletion.Person.delete", side_effect=ProtectedError("protected", set())):
            response = self.client.delete(URL, {"email": "pilot@example.com"}, format="json")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(self.User.objects.filter(email="pilot@example.com").exists())
        self.person.refresh_from_db()
        self.assertEqual((self.person.first_name, self.person.last_name), ("Unknown", "Unknown"))
        self.assertEqual(self.person.email, f"internal_{self.person.pk}@airsports.no")
        self.assertFalse(self.person.is_public)

    def test_staff_and_organizer_accounts_cannot_self_delete(self):
        self.user.is_staff = True
        self.user.save()
        response = self.client.delete(URL, {"email": "pilot@example.com"}, format="json")

        self.assertEqual(response.status_code, 409)
        self.assertTrue(self.User.objects.filter(email="pilot@example.com").exists())
        self.firebase_delete.assert_not_called()

    def test_requires_authentication(self):
        response = APIClient().delete(URL, {"email": "pilot@example.com"}, format="json")
        self.assertIn(response.status_code, (401, 403))
        self.assertTrue(self.User.objects.filter(email="pilot@example.com").exists())
