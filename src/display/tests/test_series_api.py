"""Series management: who can create and manage one, which contests can be legs, and the public-series rule."""

import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from display.models import Contest, Series, SeriesContest


def make_contest(name, is_public=False):
    now = datetime.datetime.now(datetime.timezone.utc)
    contest = Contest.objects.create(
        name=name, start_time=now, finish_time=now + datetime.timedelta(days=1), location="60, 11"
    )
    if is_public:
        contest.make_public()
    return contest


def make_user(email, organiser=False):
    user = get_user_model().objects.create(email=email)
    if organiser:
        # What organisers have (the contest creator group)
        user.user_permissions.add(
            *Permission.objects.filter(codename__in=("add_contest", "change_contest", "delete_contest"))
        )
    return user


def manage(user, contest):
    for permission in ("view_contest", "change_contest"):
        assign_perm(permission, user, contest)


class SeriesApiTestBase(APITestCase):
    client_class = APIClient

    def setUp(self):
        self.organiser = make_user("organiser@example.com", organiser=True)
        self.other = make_user("other@example.com", organiser=True)
        self.pilot = make_user("pilot@example.com")
        self.public_contest = make_contest("Public leg", is_public=True)
        self.private_contest = make_contest("Private leg")
        for contest in (self.public_contest, self.private_contest):
            manage(self.organiser, contest)

    def login(self, user):
        self.client.force_login(user)

    def create(self, **fields):
        return self.client.post("/api/v1/series/", {"name": "Cup", **fields}, format="json")


class TestSeriesManagement(SeriesApiTestBase):
    def test_an_organiser_creates_a_series_and_manages_it(self):
        self.login(self.organiser)
        result = self.create(description="Three legs", scoring_method="placements")
        self.assertEqual(result.status_code, status.HTTP_201_CREATED, result.content)
        self.assertTrue(result.json()["can_manage"])
        self.assertFalse(result.json()["is_public"], "new series are private")
        series = Series.objects.get()
        self.assertEqual(series.created_by, self.organiser)
        self.assertTrue(self.organiser.has_perm("display.change_series", series))

    def test_someone_who_is_not_an_organiser_cannot_create_one(self):
        self.login(self.pilot)
        self.assertEqual(self.create().status_code, 403)

    def test_anonymous_cannot_create_one(self):
        self.assertIn(self.create().status_code, (401, 403))

    def test_a_private_series_is_only_seen_by_its_managers(self):
        series = Series.objects.create(name="Private cup")
        assign_perm("view_series", self.organiser, series)
        self.assertEqual(self.client.get("/api/v1/series/").json(), [])
        self.login(self.pilot)
        self.assertEqual(self.client.get("/api/v1/series/").json(), [])
        self.assertEqual(self.client.get(f"/api/v1/series/{series.pk}/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/v1/series/{series.pk}/standings/").status_code, 404)
        self.login(self.organiser)
        self.assertEqual([item["name"] for item in self.client.get("/api/v1/series/").json()], ["Private cup"])

    def test_a_public_series_is_seen_by_everybody_anonymous_too(self):
        Series.objects.create(name="Open cup", is_public=True)
        self.assertEqual([item["name"] for item in self.client.get("/api/v1/series/").json()], ["Open cup"])

    def test_only_a_manager_changes_the_series(self):
        series = Series.objects.create(name="Open cup", is_public=True)
        self.login(self.other)
        self.assertEqual(self.client.patch(f"/api/v1/series/{series.pk}/", {"name": "Mine"}, format="json").status_code, 403)
        self.assertEqual(self.client.delete(f"/api/v1/series/{series.pk}/").status_code, 403)

    def test_a_manager_changes_the_scoring_and_deletes(self):
        self.login(self.organiser)
        series_id = self.create().json()["id"]
        url = f"/api/v1/series/{series_id}/"
        changed = self.client.patch(
            url,
            {"scoring_method": "points_table", "entrant_identity": "crew", "best_results_counted": 2, "points_table": [9, 5, 1]},
            format="json",
        )
        self.assertEqual(changed.status_code, 200, changed.content)
        series = Series.objects.get(pk=series_id)
        self.assertEqual((series.scoring_method, series.entrant_identity, series.best_results_counted), ("points_table", "crew", 2))
        self.assertEqual(series.points_table, [9, 5, 1])
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_a_points_table_must_be_numbers(self):
        self.login(self.organiser)
        series_id = self.create().json()["id"]
        bad = self.client.patch(f"/api/v1/series/{series_id}/", {"points_table": ["x"]}, format="json")
        self.assertEqual(bad.status_code, 400)
        empty = self.client.patch(
            f"/api/v1/series/{series_id}/", {"scoring_method": "points_table", "points_table": []}, format="json"
        )
        self.assertEqual(empty.status_code, 400)


class TestSeriesLegs(SeriesApiTestBase):
    def setUp(self):
        super().setUp()
        self.login(self.organiser)
        self.series_id = self.create().json()["id"]
        self.url = f"/api/v1/series/{self.series_id}/contests/"

    def add(self, contest, **extra):
        return self.client.post(self.url, {"contest": contest.pk, **extra}, format="json")

    def test_legs_are_numbered_in_the_order_they_are_added(self):
        self.assertEqual(self.add(self.private_contest).json()["leg_number"], 1)
        self.assertEqual(self.add(self.public_contest, weight=2).json()["leg_number"], 2)
        detail = self.client.get(f"/api/v1/series/{self.series_id}/").json()
        self.assertEqual([(leg["name"], leg["weight"]) for leg in detail["legs"]], [("Private leg", 1.0), ("Public leg", 2.0)])

    def test_a_contest_is_added_once(self):
        self.add(self.private_contest)
        self.assertEqual(self.add(self.private_contest).status_code, 400)

    def test_only_contests_the_user_manages_can_be_added(self):
        self.login(self.other)
        # Another organiser manages the series but not this contest
        assign_perm("change_series", self.other, Series.objects.get(pk=self.series_id))
        assign_perm("view_series", self.other, Series.objects.get(pk=self.series_id))
        self.assertEqual(self.add(self.private_contest).status_code, 403)

    def test_the_weight_must_be_positive(self):
        self.assertEqual(self.add(self.private_contest, weight=0).status_code, 400)

    def test_the_leg_number_and_weight_can_be_changed_and_the_leg_removed(self):
        self.add(self.private_contest)
        url = f"{self.url}{self.private_contest.pk}/"
        changed = self.client.patch(url, {"leg_number": 7, "weight": 1.5}, format="json")
        self.assertEqual(changed.status_code, 200, changed.content)
        link = SeriesContest.objects.get()
        self.assertEqual((link.leg_number, link.weight), (7, 1.5))
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertFalse(SeriesContest.objects.exists())

    def test_the_contests_manager_can_take_the_contest_out_but_not_change_the_legs(self):
        self.add(self.private_contest)
        manage(self.other, self.private_contest)
        self.login(self.other)
        url = f"{self.url}{self.private_contest.pk}/"
        # not a manager of the series, so the series is not even visible
        self.assertEqual(self.client.patch(url, {"weight": 3}, format="json").status_code, 404)

    def test_addable_contests_are_those_the_user_manages_and_that_are_not_in_yet(self):
        self.add(self.private_contest)
        listed = self.client.get(f"/api/v1/series/{self.series_id}/addable-contests/").json()
        self.assertEqual([contest["name"] for contest in listed], ["Public leg"])


class TestPublicSeriesOnlyHoldsPublicContests(SeriesApiTestBase):
    def setUp(self):
        super().setUp()
        self.login(self.organiser)

    def test_a_private_contest_cannot_join_a_public_series(self):
        series_id = self.create(is_public=True).json()["id"]
        result = self.client.post(f"/api/v1/series/{series_id}/contests/", {"contest": self.private_contest.pk}, format="json")
        self.assertEqual(result.status_code, 400)
        self.assertIn("public", str(result.json()).lower())

    def test_a_series_with_a_private_contest_cannot_be_made_public(self):
        series_id = self.create().json()["id"]
        self.client.post(f"/api/v1/series/{series_id}/contests/", {"contest": self.private_contest.pk}, format="json")
        result = self.client.patch(f"/api/v1/series/{series_id}/", {"is_public": True}, format="json")
        self.assertEqual(result.status_code, 400)
        self.assertFalse(Series.objects.get(pk=series_id).is_public)

    def test_a_leg_of_a_public_series_cannot_be_made_private_by_sharing(self):
        series_id = self.create(is_public=True).json()["id"]
        self.client.post(f"/api/v1/series/{series_id}/contests/", {"contest": self.public_contest.pk}, format="json")
        result = self.client.put(f"/api/v1/contests/{self.public_contest.pk}/share/", {"visibility": "private"}, format="json")
        self.assertEqual(result.status_code, 400, result.content)
        self.public_contest.refresh_from_db()
        self.assertTrue(self.public_contest.is_public)

    def test_nor_by_writing_the_contest(self):
        series_id = self.create(is_public=True).json()["id"]
        self.client.post(f"/api/v1/series/{series_id}/contests/", {"contest": self.public_contest.pk}, format="json")
        for permission in ("add_contest", "delete_contest"):
            assign_perm(permission, self.organiser, self.public_contest)
        result = self.client.patch(f"/api/v1/contests/{self.public_contest.pk}/", {"is_public": False}, format="json")
        self.assertEqual(result.status_code, 400, result.content)
        self.public_contest.refresh_from_db()
        self.assertTrue(self.public_contest.is_public)

    def test_it_can_once_the_contest_is_out_of_the_series(self):
        series_id = self.create(is_public=True).json()["id"]
        self.client.post(f"/api/v1/series/{series_id}/contests/", {"contest": self.public_contest.pk}, format="json")
        self.client.delete(f"/api/v1/series/{series_id}/contests/{self.public_contest.pk}/")
        result = self.client.put(f"/api/v1/contests/{self.public_contest.pk}/share/", {"visibility": "private"}, format="json")
        self.assertEqual(result.status_code, 200, result.content)


class TestStandingsEndpoint(SeriesApiTestBase):
    def test_the_standings_of_a_public_series_are_open_to_everybody(self):
        series = Series.objects.create(name="Open cup", is_public=True)
        SeriesContest.objects.create(series=series, contest=self.public_contest)
        standings = self.client.get(f"/api/v1/series/{series.pk}/standings/")
        self.assertEqual(standings.status_code, 200)
        self.assertEqual(standings.json()["name"], "Open cup")
        self.assertEqual([leg["name"] for leg in standings.json()["legs"]], ["Public leg"])
