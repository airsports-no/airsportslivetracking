#
# Script to check if we are alive. Exit value 0 on success, 1 on failure
#
# Will check if LIVENESS_FILE has been modified less than seconds ago
#
# Usage: python3 is_alive.py 90
#
# Default is 90 seconds if no argument is given - position_processor.py's
# check_connection() refreshes the file every CONNECTION_CHECK_INTERVAL (30s), but
# reschedules its own next run *after* doing its work (including a Redis cache.get
# round trip), so the true refresh period is always 30s+epsilon. A 30s threshold gave
# zero margin - file age immediately before each refresh always exceeded it, failing a
# genuinely healthy pod. 90s (3x the refresh interval) leaves real margin while still
# detecting a truly wedged process well within the existing failureThreshold*periodSeconds
# window before Kubernetes would actually restart the pod. Compare celery_liveness.py's
# 10s-touch/60s-threshold (6x margin).
#
import os
import sys
from datetime import datetime, timezone

from probes import LIVENESS_FILE

sec = 90

if __name__ == '__main__':
    if len(sys.argv) == 2:
        sec = int(sys.argv[1])

    mod_time = os.path.getmtime(LIVENESS_FILE)
    if mod_time > datetime.now(tz=timezone.utc).timestamp() - sec:
        sys.exit(0)

    sys.exit(1)
