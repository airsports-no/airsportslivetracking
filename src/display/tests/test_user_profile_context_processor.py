"""
Coverage for display.context_processors.user_profile - the navbar's profile menu trigger (see
base_tailwind.html) shows the logged-in user's picture instead of the word "Profile" when one is
available via their matching Person, falling back to an initials avatar otherwise.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase

from display.context_processors import user_profile
from display.models import Person

# A minimal valid 1x1 GIF - real enough for ImageField's Pillow-backed content validation.
_TINY_GIF = bytes.fromhex("47494638396101000100800000000000ffffff21f90401000000002c00000000010001000002024401003b")


class TestUserProfileContextProcessor(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _request_for(self, user):
        request = self.factory.get("/")
        request.user = user
        return request

    def test_anonymous_user_has_no_picture(self):
        context = user_profile(self._request_for(AnonymousUser()))
        self.assertIsNone(context["user_profile_picture_url"])

    def test_authenticated_user_with_no_matching_person_has_no_picture(self):
        user = get_user_model().objects.create_user(email="no-person@example.com", password="secret")
        context = user_profile(self._request_for(user))
        self.assertIsNone(context["user_profile_picture_url"])

    def test_authenticated_user_whose_person_has_no_picture_has_no_picture(self):
        user = get_user_model().objects.create_user(email="no-picture@example.com", password="secret")
        Person.objects.create(first_name="No", last_name="Picture", email="no-picture@example.com")
        context = user_profile(self._request_for(user))
        self.assertIsNone(context["user_profile_picture_url"])

    def test_authenticated_user_with_a_pictured_person_gets_the_picture_url(self):
        user = get_user_model().objects.create_user(email="pictured@example.com", password="secret")
        person = Person.objects.create(
            first_name="Has",
            last_name="Picture",
            email="pictured@example.com",
            picture=SimpleUploadedFile("avatar.gif", _TINY_GIF, content_type="image/gif"),
        )
        context = user_profile(self._request_for(user))
        self.assertEqual(context["user_profile_picture_url"], person.picture.url)

    def test_email_match_is_case_insensitive(self):
        # Matches Person.objects.filter(email=...) conventions used elsewhere (e.g.
        # get_persons_for_signup) - MyUser and Person emails aren't guaranteed identical case.
        user = get_user_model().objects.create_user(email="Mixed-Case@example.com", password="secret")
        Person.objects.create(
            first_name="Mixed",
            last_name="Case",
            email="mixed-case@example.com",
            picture=SimpleUploadedFile("avatar.gif", _TINY_GIF, content_type="image/gif"),
        )
        context = user_profile(self._request_for(user))
        self.assertIsNotNone(context["user_profile_picture_url"])
