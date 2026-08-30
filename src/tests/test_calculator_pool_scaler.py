from unittest.mock import MagicMock, patch

import pytest
import redis

import calculator_pool_scaler
from calculator_pool_scaler import _reconcile_once, desired_replicas, wake_pool_if_cold
from display.utilities.calculator_running_utilities import calculator_is_alive, calculator_is_terminated
from live_tracking_map import settings


class TestDesiredReplicas:
    """
    desired_replicas() is the pure sizing function driving
    src/calculator_pool_scaler.py, which replaced the KEDA ScaledObject that
    used to autoscale the live-calculator pool. Its one hard invariant: the
    result must only ever be 0 when scheduled, running and queued are all 0 -
    a shrink can never evict a pod that is actually holding a live
    contestant, even if the schedule query (scheduled) momentarily disagrees
    with the broker/heartbeat signals (running, queued).
    """

    def test_all_zero_scales_to_zero(self):
        assert desired_replicas(scheduled=0, running=0, queued=0, slots=12, maximum=4) == 0

    def test_single_contestant_needs_one_pod(self):
        assert desired_replicas(scheduled=1, running=0, queued=0, slots=12, maximum=4) == 1

    def test_exact_multiple_of_slots(self):
        assert desired_replicas(scheduled=12, running=0, queued=0, slots=12, maximum=4) == 1

    def test_one_over_a_multiple_of_slots_rounds_up(self):
        assert desired_replicas(scheduled=13, running=0, queued=0, slots=12, maximum=4) == 2

    def test_running_plus_queued_floor_can_exceed_scheduled(self):
        # The schedule query can lag reality (DB replication, a
        # finished_by_time extension) - running+queued is the independent
        # floor that protects against scaling down out from under live work.
        assert desired_replicas(scheduled=0, running=5, queued=8, slots=12, maximum=4) == 2

    def test_scheduled_can_exceed_running_plus_queued(self):
        # The common case: contestants are scheduled (prewarm window open)
        # but none has actually started yet.
        assert desired_replicas(scheduled=20, running=0, queued=0, slots=12, maximum=4) == 2

    def test_demand_above_max_replicas_is_clamped(self):
        assert desired_replicas(scheduled=100, running=0, queued=0, slots=12, maximum=4) == 4

    def test_any_nonzero_signal_alone_prevents_scaling_to_zero(self):
        assert desired_replicas(scheduled=0, running=1, queued=0, slots=12, maximum=4) == 1
        assert desired_replicas(scheduled=0, running=0, queued=1, slots=12, maximum=4) == 1

    def test_nonpositive_slots_is_rejected(self):
        with pytest.raises(ValueError):
            desired_replicas(scheduled=1, running=0, queued=0, slots=0, maximum=4)


class TestWakePoolIfCold:
    """
    wake_pool_if_cold() is the eager counterpart to desired_replicas()/
    run_forever()'s periodic reconcile: called synchronously from
    add_positions_to_calculator (position_processor_process.py) the instant a
    brand-new calculator task is dispatched, so a contestant with an
    immediate tracker_start_time (no lead time for the periodic scaler to
    have already prewarmed the pool) doesn't sit queued for up to
    CALCULATOR_POOL_POLL_SECONDS before anything reacts.
    """

    def setup_method(self):
        # _apps_api is a process-local lazy-init cache shared with
        # run_forever() - reset it so tests don't leak state into each other
        # or depend on run order.
        calculator_pool_scaler._apps_api = None

    @patch("calculator_pool_scaler.scaling_enabled", return_value=False)
    @patch("calculator_pool_scaler._build_apps_api")
    def test_does_nothing_when_scaling_disabled(self, mock_build_api, mock_enabled):
        wake_pool_if_cold()
        mock_build_api.assert_not_called()

    @patch("calculator_pool_scaler.scaling_enabled", return_value=True)
    @patch("calculator_pool_scaler._patch_replicas")
    @patch("calculator_pool_scaler._current_replicas", return_value=0)
    @patch("calculator_pool_scaler._build_apps_api")
    def test_wakes_pool_when_at_zero(self, mock_build_api, mock_current, mock_patch, mock_enabled):
        wake_pool_if_cold()
        mock_patch.assert_called_once()
        assert mock_patch.call_args.args[-1] == 1

    @patch("calculator_pool_scaler.scaling_enabled", return_value=True)
    @patch("calculator_pool_scaler._patch_replicas")
    @patch("calculator_pool_scaler._current_replicas", return_value=3)
    @patch("calculator_pool_scaler._build_apps_api")
    def test_does_not_patch_when_already_warm(self, mock_build_api, mock_current, mock_patch, mock_enabled):
        # A warm pool is run_forever()'s job to size correctly - the eager
        # nudge only ever unsticks from zero, never second-guesses a
        # positive replica count.
        wake_pool_if_cold()
        mock_patch.assert_not_called()

    @patch("calculator_pool_scaler.scaling_enabled", return_value=True)
    @patch("calculator_pool_scaler._build_apps_api", side_effect=RuntimeError("kubernetes API unreachable"))
    def test_kubernetes_failure_is_swallowed(self, mock_build_api, mock_enabled):
        # Must never raise - this runs inline in the position-ingest hot path
        # (add_positions_to_calculator), and a transient Kubernetes API error
        # must not break position ingestion. The periodic scaler still
        # catches this contestant on its next poll.
        wake_pool_if_cold()


class TestRunForeverStartup:
    """
    run_forever() is spawned as a daemon process with no restart supervision
    (see the Process(...) call in position_processor.py), so an unhandled
    exception during its one-time Kubernetes/Redis client setup would kill
    schedule-aware scaling for the rest of the pod's life - potentially
    days - with nothing else noticing. It must retry instead of propagating.
    """

    def setup_method(self):
        calculator_pool_scaler._apps_api = None

    @patch("calculator_pool_scaler.scaling_enabled", return_value=True)
    @patch("calculator_pool_scaler._build_apps_api")
    @patch("calculator_pool_scaler.redis.Redis")
    @patch("calculator_pool_scaler._reconcile_once")
    @patch("calculator_pool_scaler.time.sleep")
    def test_retries_initial_setup_failure_instead_of_crashing(
        self, mock_sleep, mock_reconcile, mock_redis, mock_build_api, mock_enabled
    ):
        class StopLoop(Exception):
            pass

        mock_build_api.side_effect = [RuntimeError("kubernetes API unreachable"), object()]
        mock_sleep.side_effect = [None, StopLoop]

        with pytest.raises(StopLoop):
            calculator_pool_scaler.run_forever()

        assert mock_build_api.call_count == 2
        mock_reconcile.assert_called_once()


class TestReconcileOnceIndependentFloor:
    """
    Regression test for the "independent floor" finding: _reconcile_once must not shrink the
    pool out from under a calculator that's still genuinely running, even when the schedule query
    no longer includes its contestant (e.g. it's draining its position queue past
    finished_by_time, or should_i_terminate() advanced finished_by_time to an inferred landing
    time). count_running(scheduled_pks) could never catch this, since it can only report a subset
    of whatever pks the schedule query itself just produced.
    """

    PK = 90_000_101

    def setup_method(self):
        calculator_is_terminated(self.PK)

    def teardown_method(self):
        calculator_is_terminated(self.PK)

    @patch("calculator_pool_scaler._current_replicas", return_value=0)
    @patch("calculator_pool_scaler._scheduled_contestant_pks", return_value=[])
    def test_a_calculator_missing_from_the_schedule_query_still_holds_the_pool_open(
        self, mock_scheduled, mock_current
    ):
        calculator_is_alive(self.PK, 30)

        cache_redis_connection = redis.Redis.from_url(settings.REDIS_CACHE_URL)
        mock_apps_api = MagicMock()
        mock_broker_redis = MagicMock()
        mock_broker_redis.llen.return_value = 0

        with patch("calculator_pool_scaler._patch_replicas") as mock_patch:
            _reconcile_once(
                mock_apps_api,
                mock_broker_redis,
                cache_redis_connection,
                {
                    "deployment": "live-calculator",
                    "namespace": "default",
                    "slots_per_pod": 12,
                    "max_replicas": 4,
                    "prewarm_minutes": 15,
                },
            )

        # scheduled=0 and queued=0, but the still-running calculator must have kept the
        # target above zero - a bare count_running(scheduled_pks=[]) would always be 0 here.
        mock_patch.assert_called_once()
        assert mock_patch.call_args.args[-1] >= 1
