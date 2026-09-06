"""Regression test for #742: publish the gate-scorecard cache token only after commit.

bump_gate_scorecard_cache_version (display/signals.py) used to write the
`gate_scorecard_version_<pk>` cache token synchronously from Scorecard's post_save
signal. post_save fires while the enclosing transaction is still open, so a concurrent
reader connection could observe the new token - and cache a fresh GateScoreValue under
it via Scorecard.get_gate_scorecard() - before it could observe the committed
Scorecard.config that token is supposed to describe. That GateScoreValue then stayed
wrongly cached until the token changed again.

This needs two genuinely concurrent DB connections (Django connections are
thread-local, so two real threads suffice) to prove the ordering, which requires
TransactionTestCase rather than TestCase - TestCase wraps the whole test in one
transaction that a second thread's connection can't see into regardless of when the
signal fires, which would make the pre-#742 bug invisible to the test.
"""

import threading

from django.core.cache import cache
from django.db import close_old_connections, transaction
from django.test import TransactionTestCase

from display.models import Scorecard
from display.utilities.gate_definitions import TURNPOINT


class TestGateScorecardCacheVersionPublishedAfterCommit(TransactionTestCase):
    def setUp(self):
        Scorecard.SCORECARD_CACHE.clear()
        self.scorecard = Scorecard.objects.create(
            name="Cache version transaction test", shortcut_name="cache-version-txn-test"
        )
        self.scorecard.config["gates"] = {TURNPOINT: {"penalty_per_second": 2}}
        self.scorecard.save(update_fields=["config"])
        self.version_key = f"gate_scorecard_version_{self.scorecard.pk}"
        cache.delete(self.version_key)

    def tearDown(self):
        Scorecard.SCORECARD_CACHE.clear()
        cache.delete(self.version_key)

    def test_reader_cannot_see_new_token_before_writer_commits_config(self):
        writer_saved = threading.Event()
        allow_commit = threading.Event()
        observed_token_mid_transaction = {}

        def writer():
            try:
                with transaction.atomic():
                    scorecard = Scorecard.objects.get(pk=self.scorecard.pk)
                    scorecard.config["gates"][TURNPOINT]["penalty_per_second"] = 99
                    scorecard.save(update_fields=["config"])
                    writer_saved.set()
                    # Hold the transaction open so the reader thread's check below is
                    # guaranteed to land while the config write is still uncommitted.
                    allow_commit.wait(timeout=5)
            finally:
                close_old_connections()

        def reader():
            writer_saved.wait(timeout=5)
            observed_token_mid_transaction["token"] = cache.get(self.version_key)

        writer_thread = threading.Thread(target=writer)
        reader_thread = threading.Thread(target=reader)
        writer_thread.start()
        reader_thread.start()
        reader_thread.join(timeout=5)
        allow_commit.set()
        writer_thread.join(timeout=5)

        # Fails under synchronous (pre-#742) publication: that code set the token from
        # post_save before the writer's transaction committed, so this would already
        # observe the new token here.
        self.assertIsNone(observed_token_mid_transaction["token"])

        # Once the writer's transaction actually commits, on_commit fires and the token
        # is published - describing config that is now genuinely visible to readers.
        after_commit_token = cache.get(self.version_key)
        self.assertIsNotNone(after_commit_token)

        self.scorecard.refresh_from_db()
        self.assertEqual(self.scorecard.config["gates"][TURNPOINT]["penalty_per_second"], 99)
        refreshed = self.scorecard.get_gate_scorecard(TURNPOINT)
        self.assertEqual(refreshed.penalty_per_second, 99)
