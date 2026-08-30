"""
Schedule-aware replica scaler for the live-calculator Celery pool
(helm/templates/deployment_live_calculator.yaml).

Replaces the KEDA ScaledObject that used to autoscale that pool: KEDA's own
operator/metrics-server cost a fixed Autopilot CPU floor regardless of usage,
and its redis-queue-depth trigger can only react *after* a task is already
queued - it cannot pre-warm ahead of a known contest start. This module reads
the schedule the database already has (Contestant.tracker_start_time) and
scales the Deployment directly via the Kubernetes API, from a third child
process spawned by position_processor.py alongside the existing ingest
processes - no separate autoscaler component, no idle cost.

Runs only in production (see `scaling_enabled`); in dev, live calculators run
as local forked processes (position_processor_process.py) and there is no
Deployment to scale.
"""

import datetime
import logging
import math
import os
import time

import redis
from django.utils import timezone

from display.models.contestant import Contestant
from display.utilities.calculator_running_utilities import count_all_running
from live_tracking_map import settings

logger = logging.getLogger(__name__)

# The Redis list Celery uses as the live_calculator queue for the default
# Redis transport - the same key KEDA's redis trigger used to poll
# (listName: live_calculator in the now-removed ScaledObject).
LIVE_CALCULATOR_QUEUE_KEY = "live_calculator"


def scaling_enabled() -> bool:
    return settings.PRODUCTION and os.environ.get("CALCULATOR_POOL_SCALING_ENABLED", "0") == "1"


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        logger.warning(f"Invalid value for {name}, falling back to {default}")
        return default


def desired_replicas(scheduled: int, running: int, queued: int, slots: int, maximum: int) -> int:
    """
    Pure sizing function - kept free of Django/Redis/Kubernetes so it is
    trivially unit-testable.

    `scheduled` is contestants whose tracking window has opened (including
    the prewarm lead). `running` + `queued` is an independent floor derived
    from what is actually happening on the broker/heartbeat side, so a gap in
    the schedule query (DB replication lag, a contestant whose finished_by_time
    was extended) can never cause a shrink that evicts a live contestant -
    the result only ever reaches 0 when all three inputs are 0.
    """
    if slots <= 0:
        raise ValueError("slots must be positive")
    demand = max(scheduled, running + queued)
    if demand <= 0:
        return 0
    return min(math.ceil(demand / slots), max(maximum, 1))


def _scheduled_contestant_pks(lead_minutes: int) -> list[int]:
    now = timezone.now()
    horizon = now + datetime.timedelta(minutes=lead_minutes)
    return list(
        Contestant.objects.filter(
            tracker_start_time__lte=horizon,
            finished_by_time__gte=now,
            contestanttrack__calculator_finished=False,
        ).values_list("pk", flat=True)
    )


def _queued_count(redis_connection: redis.Redis) -> int:
    try:
        return redis_connection.llen(LIVE_CALCULATOR_QUEUE_KEY)
    except redis.exceptions.RedisError:
        logger.exception("calculator_pool_scaler: failed reading queue depth, assuming 0")
        return 0


def _current_replicas(apps_api, deployment: str, namespace: str) -> int:
    scale = apps_api.read_namespaced_deployment_scale(name=deployment, namespace=namespace)
    return scale.spec.replicas or 0


def _patch_replicas(apps_api, deployment: str, namespace: str, replicas: int):
    apps_api.patch_namespaced_deployment_scale(
        name=deployment,
        namespace=namespace,
        body={"spec": {"replicas": replicas}},
    )


# Process-local cache: wake_pool_if_cold() is called from a Celery-dispatch
# hot path (add_positions_to_calculator, in a sibling process to run_forever's
# own loop), potentially once per newly-starting contestant over the life of
# that process, so building a fresh Kubernetes client (incluster auth) on
# every call would be wasted work. run_forever() also uses this, so there is
# exactly one place that knows how to build the client.
_apps_api = None


def _build_apps_api():
    global _apps_api
    if _apps_api is None:
        # Imported lazily: this pulls in the kubernetes client and talks to
        # the in-cluster API server, neither of which should happen just by
        # importing this module (e.g. under dev or in tests).
        from kubernetes import client
        from kubernetes import config as kube_config

        kube_config.load_incluster_config()
        _apps_api = client.AppsV1Api()
    return _apps_api


def wake_pool_if_cold():
    """
    Called synchronously from add_positions_to_calculator
    (position_processor_process.py) the instant a brand-new calculator task
    is dispatched - not on every position, only on first dispatch for that
    contestant, thanks to the same is_calculator_running/is_dispatch_pending
    guard that decides whether to dispatch at all.

    run_forever()'s periodic reconcile is forward-looking (it scales up to
    CALCULATOR_POOL_PREWARM_MINUTES ahead of Contestant.tracker_start_time),
    but a contestant created with an immediate start time - no lead time at
    all - can be dispatched while the pool is still scaled to zero. Without
    this, that contestant would sit queued for up to CALCULATOR_POOL_POLL_SECONDS
    (default 60s) before the next poll even notices, on top of pod boot time.

    Deliberately minimal: only acts when the pool is at literally zero, and
    only ever bumps it to 1 - never computes or sets an exact target replica
    count. Sizing beyond "unstuck from zero" stays run_forever()'s job, on its
    next poll (seconds away, not up to a minute), using the fuller
    scheduled/running/queued picture this hot path has no business computing
    on every dispatch. A burst of many simultaneous first-dispatches all
    seeing 0 and patching to 1 redundantly is harmless - patching to the same
    value twice is a no-op.
    """
    if not scaling_enabled():
        return
    try:
        apps_api = _build_apps_api()
        deployment = os.environ.get("CALCULATOR_POOL_DEPLOYMENT", "live-calculator")
        namespace = os.environ.get("CALCULATOR_POOL_NAMESPACE", "default")
        if _current_replicas(apps_api, deployment, namespace) == 0:
            logger.info(f"calculator_pool_scaler: waking {deployment} 0 -> 1 (new calculator dispatched, pool was cold)")
            _patch_replicas(apps_api, deployment, namespace, 1)
    except Exception:
        # Never let a Kubernetes API hiccup break position ingestion - the
        # periodic scaler will still catch this contestant on its next poll.
        logger.exception("calculator_pool_scaler: failed to wake pool")


def _reconcile_once(apps_api, redis_connection: redis.Redis, cache_redis_connection: redis.Redis, config: dict):
    scheduled_pks = _scheduled_contestant_pks(config["prewarm_minutes"])
    # count_all_running, not count_running(scheduled_pks): the latter can only ever report a
    # subset of whatever pks the schedule query just produced, collapsing the "independent floor"
    # to the schedule query's own opinion - see count_all_running's docstring.
    running = count_all_running(cache_redis_connection)
    queued = _queued_count(redis_connection)
    target = desired_replicas(
        scheduled=len(scheduled_pks),
        running=running,
        queued=queued,
        slots=config["slots_per_pod"],
        maximum=config["max_replicas"],
    )
    current = _current_replicas(apps_api, config["deployment"], config["namespace"])
    if target != current:
        logger.info(
            f"calculator_pool_scaler: scaling {config['deployment']} {current} -> {target} "
            f"(scheduled={len(scheduled_pks)}, running={running}, queued={queued}, "
            f"slots={config['slots_per_pod']})"
        )
        _patch_replicas(apps_api, config["deployment"], config["namespace"], target)


def run_forever():
    """
    Entry point for the child process spawned by position_processor.py. Loops
    forever; a single reconciliation failure is logged and swallowed so a
    transient Kubernetes API or Redis error never takes down position
    ingestion, which runs in a sibling process.
    """
    if not scaling_enabled():
        logger.info("calculator_pool_scaler: disabled (CALCULATOR_POOL_SCALING_ENABLED unset), exiting")
        return

    scaler_config = {
        "deployment": os.environ.get("CALCULATOR_POOL_DEPLOYMENT", "live-calculator"),
        "namespace": os.environ.get("CALCULATOR_POOL_NAMESPACE", "default"),
        "slots_per_pod": _int_env("CALCULATOR_POOL_SLOTS_PER_POD", 12),
        "max_replicas": _int_env("CALCULATOR_POOL_MAX_REPLICAS", 4),
        "prewarm_minutes": _int_env("CALCULATOR_POOL_PREWARM_MINUTES", 15),
    }
    poll_seconds = _int_env("CALCULATOR_POOL_POLL_SECONDS", 60)

    # This is a daemon process with no restart supervision (see the Process(...)
    # call in position_processor.py): an unhandled exception here would kill
    # schedule-aware scaling for the rest of this pod's life - which can be
    # days - with nothing else noticing, so retry instead of propagating.
    apps_api = None
    redis_connection = None
    cache_redis_connection = None
    while apps_api is None or redis_connection is None or cache_redis_connection is None:
        try:
            apps_api = _build_apps_api()
            # Broker DB (queue depth) - separate from the cache DB below on purpose, same
            # DB split as the FLUSHDB fix (settings.REDIS_CACHE_URL).
            redis_connection = redis.Redis(
                host=settings.REDIS_HOST, port=settings.REDIS_PORT, password=settings.REDIS_PASSWORD
            )
            # Cache DB (CALCULATOR_RUNNING_* heartbeats) - see count_all_running.
            cache_redis_connection = redis.Redis.from_url(settings.REDIS_CACHE_URL)
        except Exception:
            logger.exception(f"calculator_pool_scaler: failed to initialise, retrying in {poll_seconds}s")
            time.sleep(poll_seconds)

    logger.info(f"calculator_pool_scaler: starting with {scaler_config}, polling every {poll_seconds}s")
    while True:
        try:
            _reconcile_once(apps_api, redis_connection, cache_redis_connection, scaler_config)
        except Exception:
            logger.exception("calculator_pool_scaler: failed to reconcile replica count")
        time.sleep(poll_seconds)
