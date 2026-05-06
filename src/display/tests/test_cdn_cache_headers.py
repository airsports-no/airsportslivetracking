"""Tests covering Cache-Control / Vary semantics that the CDN relies on.

Key invariants exercised here:
- Public slice responses must NOT carry `Vary: Cookie` (would defeat
  CDN caching by fragmenting per-user).
- Private slice responses MUST carry `Vary: Cookie` and a private
  Cache-Control so they cannot leak through the shared cache.
- Live slices must not 304 from ETag alone, since `track_version`
  doesn't bump on every position append.
"""
import datetime
from unittest.mock import patch

from django.test import TransactionTestCase
from guardian.shortcuts import assign_perm

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import (
    Aeroplane,
    Contest,
    Contestant,
    ContestantReceivedPosition,
    Crew,
    MyUser,
    NavigationTask,
    Person,
    Route,
    Team,
)
from utilities.mock_utilities import TraccarMock


def _far_past_minute_index() -> int:
    """Return a minute_index whose window ends well before 'now - 1 minute'."""
    return 0


def _live_minute_index() -> int:
    """Return a minute_index whose window straddles 'now' (so it is treated as live)."""
    now = datetime.datetime.now(datetime.timezone.utc)
    return int(now.timestamp() // 60)


class CDNCacheHeadersTests(TransactionTestCase):
    def setUp(self):
        self.traccar_patcher = patch("display.utilities.traccar_factory.Traccar")
        self.mock_traccar_class = self.traccar_patcher.start()
        self.mock_traccar_class.create_from_configuration.return_value = TraccarMock

        now = datetime.datetime.now(datetime.timezone.utc)
        self.contest = Contest.objects.create(
            name="TestContest",
            start_time=now - datetime.timedelta(days=1),
            finish_time=now + datetime.timedelta(days=1),
            is_public=True,
        )
        route = Route.objects.create(name="Route")
        self.navigation_task = NavigationTask.create(
            name="NavigationTask",
            original_scorecard=get_default_scorecard(),
            start_time=now - datetime.timedelta(hours=2),
            finish_time=now + datetime.timedelta(hours=2),
            route=route,
            contest=self.contest,
            is_public=True,
        )
        aeroplane = Aeroplane.objects.create(registration="LN-TEST")
        person = Person.objects.create(first_name="A", last_name="B", email="a@b.test")
        user = MyUser.objects.create(email="a@b.test", first_name="A", last_name="B")
        assign_perm("display.view_contest", user, self.contest)
        assign_perm("display.change_contest", user, self.contest)
        crew = Crew.objects.create(member1=person)
        team = Team.objects.create(crew=crew, aeroplane=aeroplane)

        self.contestant = Contestant.objects.create(
            team=team,
            navigation_task=self.navigation_task,
            takeoff_time=now - datetime.timedelta(hours=1),
            contestant_number=1,
            tracker_start_time=now - datetime.timedelta(hours=1),
            finished_by_time=now + datetime.timedelta(hours=1),
        )
        # Authenticate so private contests are visible to this user (as they are the pilot/owner)
        self.client.force_login(user)

    def tearDown(self):
        self.traccar_patcher.stop()

    def _slice_url(self, minute_index: int, count: int = 1) -> str:
        url = f"/api/v1/contestant/{self.contestant.pk}/slice/{minute_index}/"
        if count != 1:
            url += f"?count={count}"
        return url

    def _make_public(self):
        self.navigation_task.is_public = True
        self.navigation_task.save(update_fields=["is_public"])
        self.contest.is_public = True
        self.contest.save(update_fields=["is_public"])

    def _make_private(self):
        self.navigation_task.is_public = False
        self.navigation_task.save(update_fields=["is_public"])
        self.contest.is_public = False
        self.contest.save(update_fields=["is_public"])

    # --- 1. Public slice is CDN-cacheable ---
    def test_public_finished_slice_is_publicly_cacheable_without_cookie_vary(self):
        self._make_public()
        response = self.client.get(self._slice_url(_far_past_minute_index()))
        self.assertEqual(response.status_code, 200)
        cache_control = response["Cache-Control"]
        self.assertIn("public", cache_control)
        self.assertIn("immutable" if "immutable" in cache_control else "max-age=", cache_control)
        # Vary: Cookie on a public response would shatter the CDN cache.
        vary = response.get("Vary", "")
        self.assertNotIn("Cookie", vary)
        self.assertNotIn("Authorization", vary)

    def test_public_live_slice_has_short_max_age_without_cookie_vary(self):
        self._make_public()
        response = self.client.get(self._slice_url(_live_minute_index()))
        self.assertEqual(response.status_code, 200)
        self.assertIn("max-age=5", response["Cache-Control"])
        self.assertIn("public", response["Cache-Control"])
        self.assertNotIn("Cookie", response.get("Vary", ""))

    # --- 2. Private slice never leaks through CDN ---
    def test_private_slice_returns_private_cache_control_with_cookie_vary(self):
        self._make_private()
        response = self.client.get(self._slice_url(_far_past_minute_index()))
        self.assertEqual(response.status_code, 200)
        self.assertIn("private", response["Cache-Control"])
        # Private endpoints must Vary on Cookie so the CDN never serves
        # one user's response to another.
        self.assertIn("Cookie", response.get("Vary", ""))

    # --- 3. ETag short-circuit only fires for finished slices ---
    def test_live_slice_can_304_if_data_unchanged(self):
        """With data-dependent ETags (including position count), even a live 
        slice can safely return 304 if no new positions have arrived."""
        self._make_public()
        live_index = _live_minute_index()

        # Add a position inside the live window.
        window_start = datetime.datetime.fromtimestamp(live_index * 60, tz=datetime.timezone.utc)
        ContestantReceivedPosition.objects.create(
            contestant=self.contestant,
            time=window_start + datetime.timedelta(seconds=10),
            latitude=60.0,
            longitude=11.0,
        )

        first = self.client.get(self._slice_url(live_index))
        self.assertEqual(first.status_code, 200)
        etag = first["ETag"]

        # If data hasn't changed, 304 is now allowed.
        second = self.client.get(self._slice_url(live_index), HTTP_IF_NONE_MATCH=etag)
        self.assertEqual(second.status_code, 304)

        # But if data IS added, ETag MUST change and return 200.
        ContestantReceivedPosition.objects.create(
            contestant=self.contestant,
            time=window_start + datetime.timedelta(seconds=20),
            latitude=60.1,
            longitude=11.1,
        )
        third = self.client.get(self._slice_url(live_index), HTTP_IF_NONE_MATCH=etag)
        self.assertEqual(third.status_code, 200)
        self.assertEqual(len(third.json()), 2)

    def test_finished_slice_returns_304_with_matching_etag(self):
        self._make_public()
        first = self.client.get(self._slice_url(_far_past_minute_index()))
        self.assertEqual(first.status_code, 200)
        etag = first["ETag"]

        second = self.client.get(
            self._slice_url(_far_past_minute_index()), HTTP_IF_NONE_MATCH=etag
        )
        self.assertEqual(second.status_code, 304)

    # --- 4. count parameter is bounded ---
    def test_count_above_60_is_rejected(self):
        self._make_public()
        response = self.client.get(self._slice_url(0, count=120))
        self.assertEqual(response.status_code, 400)
        # Error responses must not be cacheable.
        self.assertIn("no-store", response["Cache-Control"])

    def test_count_zero_or_negative_is_rejected(self):
        self._make_public()
        response = self.client.get(self._slice_url(0, count=0))
        self.assertEqual(response.status_code, 400)


class CDNSafetyMiddlewareDefaultsTests(TransactionTestCase):
    """Covers the middleware's defaulting behaviour for endpoints that
    don't set Cache-Control explicitly."""

    def test_unknown_api_path_defaults_to_private_no_cache_with_vary(self):
        # A 404 from /api/... still goes through the middleware.
        response = self.client.get("/api/v1/does-not-exist/")
        self.assertEqual(response.status_code, 404)
        cache_control = response["Cache-Control"]
        # 404 falls through the auth-error branch only for 400/401/403, so
        # we only assert the broader "not publicly cacheable" property.
        self.assertNotIn("public", cache_control)
        # Vary must include Cookie so the CDN doesn't cache cross-user.
        self.assertIn("Cookie", response.get("Vary", ""))

    def test_non_api_path_is_not_touched_by_middleware(self):
        # Middleware should leave non-/api responses alone — Cache-Control
        # may be absent, and that's fine.
        response = self.client.get("/")
        # We don't assert specific headers, only that no CDN safety logic
        # crashed. A 200, 302, or 404 are all acceptable here.
        self.assertIn(response.status_code, (200, 301, 302, 404))
