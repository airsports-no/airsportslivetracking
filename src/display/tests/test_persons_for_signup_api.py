"""
Coverage for get_persons_for_signup's exclude_self behavior. Self-registration's copilot search
(ContestRegistrationForm.tsx) relies on the default (exclude the requester - you can't be your own
copilot), while the admin team-registration flow (TeamRegistrationFlow.tsx) passes
exclude_self=false, since an organizer who is also a competitor must be selectable as a pilot too -
including when re-editing a registration where they're already the pilot, otherwise their name
can't be resolved from the list and the form falls back to showing their raw Person id (the bug
this endpoint change fixes).
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from display.models import Person


class TestGetPersonsForSignup(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="self@example.com", password="secret")
        self.self_person = Person.objects.create(first_name="Self", last_name="Person", email="self@example.com")
        self.other_person = Person.objects.create(first_name="Other", last_name="Person", email="other@example.com")
        self.client.force_login(self.user)

    def test_excludes_self_by_default(self):
        response = self.client.get("/display/api/person/signuplist/")

        self.assertEqual(response.status_code, 200)
        ids = {p["id"] for p in response.json()}
        self.assertNotIn(self.self_person.id, ids)
        self.assertIn(self.other_person.id, ids)

    def test_exclude_self_false_includes_the_requester(self):
        response = self.client.get("/display/api/person/signuplist/?exclude_self=false")

        self.assertEqual(response.status_code, 200)
        ids = {p["id"] for p in response.json()}
        self.assertIn(self.self_person.id, ids)
        self.assertIn(self.other_person.id, ids)

    def test_exclude_self_true_is_equivalent_to_the_default(self):
        response = self.client.get("/display/api/person/signuplist/?exclude_self=true")

        self.assertEqual(response.status_code, 200)
        ids = {p["id"] for p in response.json()}
        self.assertNotIn(self.self_person.id, ids)
