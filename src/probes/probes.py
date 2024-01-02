import logging
import os
from datetime import timedelta, datetime

LIVENESS_FILE = "/tmp/im_alive"
READINESS_FILE = "/tmp/im_ready"

_deadline = datetime.max

logger = logging.getLogger(__name__)


def set_ttl(ttl: timedelta):
    """
    Sets a deadline in the future where the liveness file be deleted, causing k8s to restart the pod.

    Assuming the pod is healthy, the liveness file will be deleted the first time liveness() is called after this time.
    If so, k8s will immediately notice, (although it will try again a few of times before actually restarting).
    If the pod for some reason stops calling liveness, k8s will not notice until the liveness file has expired.
    In any case, the pod is guaranteed to be restarted a reasonably short time after the TTL, but not exactly at.
    """
    global _deadline
    _deadline = datetime.now() + ttl
    logger.debug(f"Sets deadline {ttl} from now: {_deadline}")


def liveness(is_alive: bool):
    """
    Signals to k8s that the pod is alive, i.e. does not need to be restarted, assuming the pod is configured to use the
    probes package for liveness.

    If the process has a TTL which is expired, the liveness will be set to False at each call.

    This needs to be called regularly, e.g. every ten seconds. Maximum amount of time between each liveness is decided
    by the liveness probe's periodSeconds in the deployment, usually decided by helm-common.probeHeader.
    """
    if is_alive:
        allowed_to_live = datetime.now() < _deadline
        if not allowed_to_live:
            logger.debug("Deadline reached, setting liveness to false")
    else:
        allowed_to_live = is_alive
    _liveness(allowed_to_live)


def _liveness(up: bool):
    if up:
        with open(LIVENESS_FILE, "w") as f:
            f.write("I'm alive")
    else:
        if os.path.exists(LIVENESS_FILE):
            os.remove(LIVENESS_FILE)


def readiness(is_ready: bool):
    """
    Signals to k8s that the pod is ready, i.e. that it is successfully started and ready to replace any previous version
    of itself, assuming the pod is configured to use the probes package for readiness.

    This should be called exactly once.
    """
    if is_ready:
        with open(READINESS_FILE, "w") as f:
            f.write("I'm ready")
    else:
        if os.path.exists(READINESS_FILE):
            os.remove(READINESS_FILE)
