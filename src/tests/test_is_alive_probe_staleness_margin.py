"""
Regression test for GDL90/probes finding #2 (2026-08-28 review): the tracker-processor
liveness probe (probes/is_alive.py) defaulted its staleness threshold to 30 seconds -
exactly equal to CONNECTION_CHECK_INTERVAL, the period position_processor.py's
check_connection() refreshes the liveness file at. check_connection() reschedules its
own next run *after* doing its work (including a Redis cache.get round trip), so the
true refresh period is always CONNECTION_CHECK_INTERVAL+epsilon - meaning the file's age
immediately before each refresh always exceeded the threshold, failing a genuinely
healthy pod. Compare celery_liveness.py's 10s-touch/60s-threshold (6x margin).
"""

import probes.is_alive as is_alive
import position_processor


def test_liveness_threshold_has_real_margin_over_the_refresh_interval():
    assert is_alive.sec > position_processor.CONNECTION_CHECK_INTERVAL, (
        f"is_alive.py's default staleness threshold ({is_alive.sec}s) must leave real margin "
        f"over how often the liveness file is actually refreshed "
        f"({position_processor.CONNECTION_CHECK_INTERVAL}s) - a threshold equal to (or below) "
        f"the refresh interval can fail a healthy pod, since the true refresh period is always "
        f"CONNECTION_CHECK_INTERVAL plus however long check_connection()'s own work takes."
    )
