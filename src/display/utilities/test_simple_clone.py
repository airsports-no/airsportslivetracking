from django.test import TestCase
from django_countries.fields import Country

from display.models import Club
from display.utilities.clone_object import simple_clone


class TestSimpleClone(TestCase):
    def test_new_clone(self):
        Club.objects.all().delete()
        club = Club.objects.create(name="My club", country="no")
        new_club = simple_clone(club, {"name": "My cloned club"})
        self.assertEqual(2, Club.objects.all().count())
        self.assertIsNotNone(new_club.pk)
        self.assertNotEqual(club.pk, new_club.pk)
        self.assertEqual("My cloned club", new_club.name)
        self.assertEqual(Country(code="NO"), new_club.country)

    def test_existing_clone(self):
        Club.objects.all().delete()
        club = Club.objects.create(name="My club", country="no")
        club_clone = Club.objects.create(name="My cloned club", country="dk")
        new_club = simple_clone(club, {"name": "My new cloned club"}, existing_clone=club_clone)
        self.assertEqual(2, Club.objects.all().count())
        self.assertIsNotNone(new_club.pk)
        self.assertNotEqual(club.pk, new_club.pk)
        self.assertEqual(club_clone.pk, new_club.pk)
        self.assertEqual("My new cloned club", new_club.name)
        self.assertEqual(Country(code="NO"), new_club.country)
