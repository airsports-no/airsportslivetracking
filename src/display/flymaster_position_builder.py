import datetime
import logging
from display.utilities.tracking_definitions import TrackingService

logger = logging.getLogger(__name__)


def build_positions_from_flymaster(file_data: str) -> tuple["Contestant| None", str, list[dict]]:
    from display.models.contestant import Contestant

    lines = file_data.split("\n")
    initial_line = lines[0].split(",")
    identifier = initial_line[0]
    logger.info(f"Received data for identifier {identifier}")
    contestant: Contestant | None = None
    positions = []
    for line in lines[1:-2]:
        try:
            tracking_start, position_time, latitude, longitude, altitude, speed, heading = line.split(",")
            timestamp = datetime.datetime.fromtimestamp(float(position_time)).replace(tzinfo=datetime.timezone.utc)
            if contestant is None:
                contestant, is_simulator = Contestant.get_contestant_for_device_at_time(
                    TrackingService.FLY_MASTER, identifier, timestamp
                )
                if contestant is not None:
                    logger.info(
                        f"Found contestant {contestant} for fly master identifier {identifier} at timestamp {timestamp}"
                    )
            positions.append(
                {
                    "device_time": timestamp,
                    "latitude": float(latitude),
                    "longitude": float(longitude),
                    "altitude": float(altitude) * 3.281,  # metres to feet
                    "speed": float(speed) / 1.852,  # km/h to knots
                    "course": float(heading),
                    "attributes": {"battery_level": -1.0},
                    "id": 0,
                    "deviceId": identifier,
                    "server_time": datetime.datetime.now(datetime.timezone.utc),
                    "processor_received_time": datetime.datetime.now(datetime.timezone.utc),
                }
            )
        except ValueError as e:
            logger.info(f"Failed parsing flymaster data line {line}")
    return contestant, identifier, positions
