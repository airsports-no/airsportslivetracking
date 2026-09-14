"""
Coverage for ContestViewSet.remove_person_picture_background - restores the classic
clear_profile_image_background view's capability (deleted as seemingly-orphaned during the
RegisterTeamWizard->SPA migration) as a REST action, now surfaced from the admin team
registration form when an existing pilot/copilot is selected.
"""

import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from display.models import Contest, Person

_TINY_GIF = bytes.fromhex("47494638396101000100800000000000ffffff21f90401000000002c00000000010001000002024401003b")


def _make_contest(owner):
    contest = Contest.objects.create(
        name="Remove background contest",
        time_zone="Europe/Oslo",
        start_time=datetime.datetime(2026, 10, 1, 9, 0, tzinfo=datetime.timezone.utc),
        finish_time=datetime.datetime(2026, 10, 1, 17, 0, tzinfo=datetime.timezone.utc),
        location="60.0,11.0",
    )
    contest.initialise(owner)
    return contest


class TestRemovePersonPictureBackgroundApi(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(email="bg-owner@example.com", password="secret")
        self.contest = _make_contest(self.owner)
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.person = Person.objects.create(
            first_name="Has",
            last_name="Picture",
            email="bg-pilot@example.com",
            picture=SimpleUploadedFile("original.gif", _TINY_GIF, content_type="image/gif"),
        )
        self.url = f"/api/v1/contests/{self.contest.pk}/remove-person-picture-background/{self.person.pk}/"

    @patch("display.models.team_structure.requests.post")
    def test_successful_background_removal_updates_the_picture(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.content = b"processed-image-bytes"

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.person.refresh_from_db()
        self.assertIn("nobg_", self.person.picture.name)
        self.assertEqual(self.person.picture.read(), b"processed-image-bytes")
        self.assertIn(self.person.picture.url, response.json()["picture"])

    @patch("display.models.team_structure.requests.post")
    def test_remove_bg_failure_returns_400_not_500(self, mock_post):
        mock_post.return_value.status_code = 403
        mock_post.return_value.text = "quota exceeded"

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
        self.person.refresh_from_db()
        self.assertNotIn("nobg_", self.person.picture.name)

    def test_person_with_no_picture_returns_400(self):
        person_without_picture = Person.objects.create(
            first_name="No", last_name="Picture", email="no-picture@example.com"
        )
        url = f"/api/v1/contests/{self.contest.pk}/remove-person-picture-background/{person_without_picture.pk}/"

        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_editor_gets_404_not_403(self):
        other_user = get_user_model().objects.create_user(email="bg-other@example.com", password="secret")
        client = APIClient()
        client.force_authenticate(other_user)

        response = client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unknown_person_returns_404(self):
        url = f"/api/v1/contests/{self.contest.pk}/remove-person-picture-background/999999/"

        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
