#
# Script to check if we are alive. Exit value 0 on success, 1 on failure
#
# Will check if LIVENESS_FILE has been modified less than seconds ago
#
# Usage: python3 is_alive.py 30
#
# Default is 30 seconds if no argument is given.
#
import os
import sys
from datetime import datetime, timezone

from probes import LIVENESS_FILE

sec = 30

if __name__ == '__main__':
    if len(sys.argv) == 2:
        sec = int(sys.argv[1])

    mod_time = os.path.getmtime(LIVENESS_FILE)
    if mod_time > datetime.now(tz=timezone.utc).timestamp() - sec:
        sys.exit(0)

    sys.exit(1)
