"""The navigation bar: everyday things one click away, personal things in the user menu, platform administration under Admin."""

import re

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase


def make_user(email, organiser=False, staff=False):
    user = get_user_model().objects.create(email=email, username=email, is_staff=staff, is_superuser=staff)
    if organiser:
        user.user_permissions.add(Permission.objects.get(codename="add_contest"))
    return user


class TestNavbar(TestCase):
    def navbar(self, user=None):
        if user:
            self.client.force_login(user)
        html = self.client.get("/").content.decode()
        header = re.search(r"<header.*?</header>", html, re.S).group(0)
        top_level = re.sub(r"<details>.*?</details>", "", header, flags=re.S)
        menus = {}
        for summary, body in re.findall(r"<summary[^>]*>(.*?)</summary>(.*?)</details>", header, re.S):
            # The user menu's summary is the avatar, so it is known by what is in it
            name = "user" if "Change password" in body else re.sub(r"<[^>]+>|\s+", " ", summary).strip()
            menus[name] = body
        return top_level, menus

    def test_an_organiser_has_contests_and_the_route_editor_on_the_bar_and_maps_in_the_user_menu(self):
        top_level, menus = self.navbar(make_user("org@example.com", organiser=True))
        for link in ("My flights", "My contests", "Route editor", "Squadrons", "Series"):
            self.assertIn(f">{link}", top_level)
        self.assertNotIn("Management", top_level + "".join(menus.values()))
        self.assertNotIn("Become an Organizer", top_level)
        self.assertNotIn("Admin", menus)
        self.assertIn("My maps", menus["user"])
        self.assertNotIn("My maps", top_level)

    def test_a_pilot_is_offered_to_become_an_organiser_and_has_no_organiser_tools(self):
        top_level, menus = self.navbar(make_user("pilot@example.com"))
        self.assertIn("Become an Organizer", top_level)
        self.assertIn(">My flights", top_level)
        for link in ("My contests", "Route editor", "My maps"):
            self.assertNotIn(link, top_level + "".join(menus.values()))

    def test_platform_administration_is_together_under_admin(self):
        top_level, menus = self.navbar(make_user("staff@example.com", organiser=True, staff=True))
        admin = menus["Admin"]
        for link in ("Statistics", "User emails", "Welcome email", "Contest creation email", "Django admin"):
            self.assertIn(link, admin)
        self.assertNotIn('href="/admin/"', top_level)
        self.assertIn(">My contests", top_level)

    def test_somebody_who_is_not_logged_in_sees_series_help_and_log_in(self):
        top_level, menus = self.navbar()
        self.assertIn(">Series", top_level)
        self.assertIn(">Log in", top_level)
        self.assertEqual(set(menus), {"Help"})
