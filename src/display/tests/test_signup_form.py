"""
Regression coverage for SignUpForm's password length validation.

Sentry PYTHON-DJANGO-11: signup crashed with an unhandled
"Invalid password string. Password must be a string at least 6 characters long." error from
Firebase's auth.create_user, because SignUpForm.password (display/forms.py) had no min_length -
a too-short password passed Django's form validation and only failed once it reached Firebase,
deep inside display.views.signup's try/except, surfacing as a generic "An error occurred during
signup" message instead of a clean inline form error.
"""

from django.test import TestCase

from display.forms import SignUpForm


class TestSignUpFormPasswordLength(TestCase):
    def _form_data(self, password="longenough", password_confirm="longenough"):
        return {
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "jane.doe@example.com",
            "country": "NO",
            "password": password,
            "password_confirm": password_confirm,
        }

    def test_password_shorter_than_six_characters_is_rejected(self):
        form = SignUpForm(data=self._form_data(password="abc12", password_confirm="abc12"))

        self.assertFalse(form.is_valid())
        self.assertIn("Password must be at least 6 characters long.", form.errors["password"])

    def test_password_of_exactly_six_characters_is_accepted(self):
        form = SignUpForm(data=self._form_data(password="abc123", password_confirm="abc123"))

        self.assertTrue(form.is_valid(), form.errors)
