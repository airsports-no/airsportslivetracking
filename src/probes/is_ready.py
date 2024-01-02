#
# Script to check if we are ready. Exit value 0 on success, 1 on failure
#
# Will check if READINESS_FILE exists
#
# Usage: python3 is_ready.py
#
import os
import sys

from probes import READINESS_FILE

if __name__ == '__main__':
    if os.path.exists(READINESS_FILE):
        sys.exit(0)

    sys.exit(1)
