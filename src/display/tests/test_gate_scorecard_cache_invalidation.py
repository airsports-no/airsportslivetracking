"""Regression test for Scorecard.SCORECARD_CACHE never being invalidated.

get_gate_scorecard() memoized gate config in a plain class-level dict keyed by
(scorecard_pk, gate_type), with nothing anywhere clearing it. An organizer editing
scoring rules (penalty_per_second, graceperiod_after, missed_penalty, ...) mid-event
was silently ignored by anything that had already called get_gate_scorecard() once -
in-process forever, and cross-process until the worker happened to restart.

Two bugs, fixed together: get_gate_scorecard() itself never invalidated, and
ScorecardNestedSerialiser.update() updated gate rows via a queryset .update(),
which skips post_save entirely - so even the new signal-based invalidation would
never have fired on the real API write path.

Phase 2e of the scorecard-system review roadmap retired GateScore - gate config now
lives directly in Scorecard.config["gates"][gate_type], written and saved on the
Scorecard itself (no more separate row/signal-mirror indirection), so these tests
mutate config and call scorecard.save() directly instead of going through a GateScore
instance.

#742 moved the version-token publish in bump_gate_scorecard_cache_version onto
transaction.on_commit (so another connection can't observe a fresh token before it can
observe the committed Scorecard.config it's supposed to describe - see
test_gate_scorecard_cache_version_transactions.py for the regression test proving that).
Django's TestCase wraps each test in a transaction it rolls back rather than commits, so
on_commit callbacks registered during a test never fire on their own; every save() here
that depends on the token actually being rewritten runs inside
captureOnCommitCallbacks(execute=True) to run them synchronously instead.
"""

from django.core.cache import cache
from django.test import TestCase

from display.models import Scorecard
from display.serialisers import ScorecardNestedSerialiser
from display.utilities.gate_definitions import TURNPOINT


class TestGateScorecardCacheInvalidation(TestCase):
    def setUp(self):
        Scorecard.SCORECARD_CACHE.clear()
        self.scorecard = Scorecard.objects.create(name="Cache invalidation test", shortcut_name="cache-inv-test")
        self.scorecard.config["gates"] = {TURNPOINT: {"penalty_per_second": 2}}
        self.scorecard.save(update_fields=["config"])

    def tearDown(self):
        Scorecard.SCORECARD_CACHE.clear()
        cache.delete(f"gate_scorecard_version_{self.scorecard.pk}")

    def test_get_gate_scorecard_reflects_a_direct_save_instead_of_returning_a_stale_cached_copy(self):
        cached = self.scorecard.get_gate_scorecard(TURNPOINT)
        self.assertEqual(cached.penalty_per_second, 2)

        with self.captureOnCommitCallbacks(execute=True):
            self.scorecard.config["gates"][TURNPOINT]["penalty_per_second"] = 99
            self.scorecard.save(update_fields=["config"])

        refreshed = self.scorecard.get_gate_scorecard(TURNPOINT)
        self.assertEqual(refreshed.penalty_per_second, 99)

    def test_get_gate_scorecard_reflects_a_delete(self):
        self.scorecard.get_gate_scorecard(TURNPOINT)  # populate the cache
        with self.captureOnCommitCallbacks(execute=True):
            del self.scorecard.config["gates"][TURNPOINT]
            self.scorecard.save(update_fields=["config"])

        # Deleting invalidates the memoized entry too - the next lookup must hit the
        # DB again (and raise the documented ValueError) rather than keep returning
        # the deleted gate's stale in-memory copy forever.
        with self.assertRaises(ValueError):
            self.scorecard.get_gate_scorecard(TURNPOINT)

    def test_scorecard_nested_serialiser_update_saves_config_and_invalidates_the_cache(self):
        # Populate the cache first, exactly like a live-calculator process that
        # already scored a gate before an organizer edits the scorecard mid-event.
        self.scorecard.get_gate_scorecard(TURNPOINT)

        with self.captureOnCommitCallbacks(execute=True):
            serialiser = ScorecardNestedSerialiser(
                self.scorecard,
                data={
                    "gatescore_set": [{"gate_type": TURNPOINT, "penalty_per_second": 42}],
                },
                partial=True,
            )
            serialiser.is_valid(raise_exception=True)
            serialiser.save()
        self.scorecard.refresh_from_db()

        # A bulk .update() would have written the new value to the DB while
        # leaving both the version token and the in-process cache untouched -
        # get_gate_scorecard() would keep returning the pre-edit object forever.
        refreshed = self.scorecard.get_gate_scorecard(TURNPOINT)
        self.assertEqual(refreshed.penalty_per_second, 42)

    def test_saving_a_gate_config_change_rewrites_the_shared_cache_version_token(self):
        # This token (display/signals.py's bump_gate_scorecard_cache_version) is what
        # makes invalidation cross-process: it lives in the shared Redis-backed
        # Django cache, not this process's memory, so every daphne/celery/
        # live-calculator process's next get_gate_scorecard() call notices the
        # edit via a cheap Redis GET instead of only this process's dict changing.
        version_key = f"gate_scorecard_version_{self.scorecard.pk}"
        self.scorecard.get_gate_scorecard(TURNPOINT)  # ensures the token exists
        before = cache.get(version_key)
        self.assertIsNotNone(before)

        with self.captureOnCommitCallbacks(execute=True):
            self.scorecard.config["gates"][TURNPOINT]["penalty_per_second"] = 7
            self.scorecard.save(update_fields=["config"])

        after = cache.get(version_key)
        self.assertIsNotNone(after)
        self.assertNotEqual(before, after)

    def test_repeated_edits_do_not_accumulate_stale_entries_in_scorecard_cache(self):
        # ultrareview bug_004: SCORECARD_CACHE used to be keyed by (pk, gate_type, version),
        # so a version bump never evicted the old entry - it just stopped being read,
        # leaking one retained instance per edit for the process's lifetime.
        for penalty in (10, 20, 30, 40):
            with self.captureOnCommitCallbacks(execute=True):
                self.scorecard.config["gates"][TURNPOINT]["penalty_per_second"] = penalty
                self.scorecard.save(update_fields=["config"])
            self.scorecard.get_gate_scorecard(TURNPOINT)

        matching_keys = [key for key in Scorecard.SCORECARD_CACHE if key[:2] == (self.scorecard.pk, TURNPOINT)]
        self.assertEqual(
            len(matching_keys),
            1,
            "SCORECARD_CACHE must hold at most one entry per (scorecard, gate_type) - "
            "repeated edits should replace it in place, not accumulate one stale entry per edit.",
        )
