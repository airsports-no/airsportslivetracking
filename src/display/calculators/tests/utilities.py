import datetime
from typing import List, Tuple

import dateutil


def load_traccar_track(track_file) -> List[Tuple[datetime.datetime, float, float]]:
    positions = []
    with open(track_file, "r") as i:
        for line in i.readlines():
            elements = line.split(",")
            positions.append((dateutil.parser.parse(elements[1]).replace(tzinfo=datetime.timezone.utc),
                              float(elements[2]), float(elements[3])))
    return positions
