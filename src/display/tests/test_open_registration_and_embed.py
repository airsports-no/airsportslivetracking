import datetime

from django.test import TestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Contest, NavigationTask, Route
from display.services.open_registration import open_registration_tasks_today

URL = "/api/v1/contests/open_registration_today/"
NOW = datetime.datetime(2026, 10, 10, 12, 0, tzinfo=datetime.timezone.utc)


def make_task(contest, name, start_h, finish_h, *, self_registration=True, public=True):
    task = NavigationTask.create(
        name=name,
        original_scorecard=get_default_scorecard(),
        start_time=NOW + datetime.timedelta(hours=start_h),
        finish_time=NOW + datetime.timedelta(hours=finish_h),
        route=Route.objects.create(name=f"route-{name}"),
        contest=contest,
    )
    NavigationTask.objects.filter(pk=task.pk).update(allow_self_management=self_registration, is_public=public)
    return task


class TestOpenRegistrationToday(TestCase):
    def setUp(self):
        self.contest = Contest.objects.create(
            name="Norwegian Cup", start_time=NOW, finish_time=NOW + datetime.timedelta(days=2), is_public=True,
            location="59.9,10.7", time_zone="Europe/Oslo",
        )

    def names(self, **kwargs):
        return [t.name for t in open_registration_tasks_today(now=NOW, **kwargs)]

    def test_lists_self_registration_tasks_that_are_today_and_not_over(self):
        make_task(self.contest, "Morning (over)", -5, -3)
        make_task(self.contest, "Running now", -1, 3)
        make_task(self.contest, "This afternoon", 4, 8)
        make_task(self.contest, "Tomorrow", 20, 30)
        self.assertEqual(self.names(timezone_name="UTC"), ["Running now", "This afternoon"])

    def test_requires_self_registration_and_public_task_and_contest(self):
        make_task(self.contest, "No self registration", 1, 3, self_registration=False)
        make_task(self.contest, "Private task", 1, 3, public=False)
        private_contest = Contest.objects.create(name="Private", start_time=NOW, finish_time=NOW, is_public=False)
        make_task(private_contest, "In private contest", 1, 3)
        self.assertEqual(self.names(timezone_name="UTC"), [])

    def test_today_follows_the_callers_time_zone(self):
        # 12:00 UTC is 14:00 in Oslo (UTC+2): a task starting at 23:00 UTC is already tomorrow there.
        make_task(self.contest, "Late", 11, 14)
        self.assertEqual(self.names(timezone_name="UTC"), ["Late"])
        self.assertEqual(self.names(timezone_name="Europe/Oslo"), [])
        self.assertEqual(self.names(timezone_name="Not/AZone"), ["Late"], "unknown zones fall back to UTC")

    def test_public_endpoint_returns_what_a_pilot_needs_to_find_the_place(self):
        make_task(self.contest, "Running now", -1, 3)
        with_now = NOW  # the view uses the real clock, so build a task around the real "now" instead
        real_now = datetime.datetime.now(datetime.timezone.utc)
        NavigationTask.objects.all().delete()
        task = NavigationTask.create(
            name="Today", original_scorecard=get_default_scorecard(),
            start_time=real_now - datetime.timedelta(minutes=5), finish_time=real_now + datetime.timedelta(minutes=30),
            route=Route.objects.create(name="r2"), contest=self.contest,
        )
        NavigationTask.objects.filter(pk=task.pk).update(allow_self_management=True, is_public=True)

        response = self.client.get(URL, {"timezone": "UTC"})  # anonymous: no sign-in needed

        self.assertEqual(response.status_code, 200)
        self.assertIn("s-maxage", response["Cache-Control"])
        item = response.json()[0]
        self.assertEqual((item["contest_name"], item["navigation_task_name"]), ("Norwegian Cup", "Today"))
        self.assertEqual((item["latitude"], item["longitude"]), (59.9, 10.7))
        self.assertEqual((item["contest_id"], item["navigation_task_id"]), (self.contest.pk, task.pk))
        self.assertTrue(item["is_open_now"])
        self.assertEqual(item["time_zone"], "Europe/Oslo")

    def test_a_contest_without_a_location_reports_none_instead_of_the_ocean(self):
        nowhere = Contest.objects.create(name="Nowhere", start_time=NOW, finish_time=NOW, is_public=True, location="")
        make_task(nowhere, "T", 1, 3)
        from display.services.open_registration import describe

        item = describe(open_registration_tasks_today("UTC", NOW).get(), NOW)
        self.assertEqual((item["latitude"], item["longitude"]), (None, None))


class TestEmbedMode(TestCase):
    PAGE = "/accounts/login/"
    NAVBAR = 'class="navbar bg-neutral'

    def test_normal_pages_have_the_site_navigation_bar(self):
        self.assertContains(self.client.get(self.PAGE), self.NAVBAR)

    def test_embed_app_hides_it_and_is_remembered(self):
        first = self.client.get(self.PAGE, {"embed": "app"})
        self.assertNotContains(first, self.NAVBAR)
        self.assertEqual(first.cookies["embed"].value, "app")
        # A later full page load in the same web view (cookie only) stays embedded.
        self.assertNotContains(self.client.get(self.PAGE), self.NAVBAR)

    def test_embed_off_restores_the_navigation_bar(self):
        self.client.get(self.PAGE, {"embed": "app"})
        response = self.client.get(self.PAGE, {"embed": "off"})
        self.assertContains(response, self.NAVBAR)
        self.assertContains(self.client.get(self.PAGE), self.NAVBAR)

    def test_a_different_cookie_value_does_nothing(self):
        self.client.cookies["embed"] = "yes"
        self.assertContains(self.client.get(self.PAGE), self.NAVBAR)
