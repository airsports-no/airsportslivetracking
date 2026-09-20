"""
Coverage for ContestViewSet.teams' Cache-Control header. Regression test for a "read your own
writes" bug: for a public+featured contest, this endpoint used to send
"stale-while-revalidate=600" unconditionally - stale-while-revalidate is honored by modern
browsers' own HTTP disk cache, not just shared/CDN caches, so an authenticated organizer who had
just edited a team (TeamRegistrationFlow's onSaved refetching this same URL) could get served
their own pre-edit response straight from disk cache instead of a real network round-trip,
appearing to "not update" the second time they reopened Edit.
"""

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from display.models import Contest


class TestContestTeamsCacheControl(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(email="cache-owner@example.com", password="secret")
        self.contest = Contest.objects.create(
            name="Cache Control Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 10, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 10, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
        )
        self.contest.initialise(self.owner)
        self.contest.is_public = True
        self.contest.is_featured = True
        self.contest.save(update_fields=["is_public", "is_featured"])
        self.url = f"/api/v1/contests/{self.contest.pk}/teams/"

    def test_authenticated_request_on_a_public_featured_contest_gets_private_no_cache(self):
        # The exact scenario that broke: an organizer (necessarily authenticated) refetching this
        # same URL right after editing a team must never get a stale-while-revalidate response.
        self.client.force_login(self.owner)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-cache")

    def test_anonymous_request_on_a_public_featured_contest_still_gets_cdn_friendly_caching(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("stale-while-revalidate", response["Cache-Control"])

    def test_authenticated_request_on_a_private_contest_gets_private_no_cache(self):
        self.contest.is_public = False
        self.contest.is_featured = False
        self.contest.save(update_fields=["is_public", "is_featured"])
        self.client.force_login(self.owner)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-cache")
