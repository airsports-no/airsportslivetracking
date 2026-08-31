"""
Regression test (ultrareview bug_002): ParallelDispatchMixin re-wrapped
SyncConsumer.dispatch's raw function with plain asgiref.sync.sync_to_async instead of
channels.db.database_sync_to_async - dropping the close_old_connections() cleanup the
original @database_sync_to_async decorator runs before/after every dispatch. Combined
with CONN_MAX_AGE=60 (persistent MySQL connections) and thread_sensitive=False reusing
long-lived asgiref pool threads, a connection idle past MySQL's wait_timeout on one of
those threads would never get recycled, and the next query on it would hit
"MySQL server has gone away" - exactly the intermittent websocket-handler failure this
mixin was meant to reduce.
"""

from channels.db import DatabaseSyncToAsync
from django.test import TestCase

from display.consumers import ParallelDispatchMixin


class TestParallelDispatchMixinKeepsConnectionCleanup(TestCase):
    def test_dispatch_is_wrapped_with_database_sync_to_async_not_plain_sync_to_async(self):
        # __dict__ access (not attribute access) is deliberate - accessing .dispatch normally
        # triggers SyncToAsync's own descriptor protocol and returns a bound partial, not the
        # SyncToAsync/DatabaseSyncToAsync instance itself.
        dispatch = ParallelDispatchMixin.__dict__["dispatch"]
        self.assertIs(
            type(dispatch),
            DatabaseSyncToAsync,
            "ParallelDispatchMixin.dispatch must be wrapped with channels.db.database_sync_to_async "
            "(DatabaseSyncToAsync), not plain asgiref.sync.sync_to_async (SyncToAsync) - the plain "
            "version skips close_old_connections(), letting CONN_MAX_AGE=60 persistent MySQL "
            "connections on the asgiref thread pool go stale.",
        )
