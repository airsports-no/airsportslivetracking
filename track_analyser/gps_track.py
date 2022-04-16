from datetime import timedelta, timezone
from cartopy.io.img_tiles import OSM
import matplotlib.pyplot as plt
import numpy as np
import cartopy.crs as ccrs

import gpxpy

from datetime_modulo import datetime
from typing import List, Tuple, Optional

from display.coordinate_utilities import (
    calculate_distance_lat_lon,
    calculate_fractional_distance_point_lat_lon,
)


def get_normalised_track(
        track: List[Tuple[datetime, float, float, float]],
        step: timedelta = timedelta(seconds=1),
) -> Tuple[datetime, datetime, List[Tuple[float, float]]]:
    # Make a copy
    track = list(track)
    interpolated = []
    start_time = track[0][0].replace(microsecond=0) + step
    current_time = start_time
    while len(track) > 1:
        next_time = current_time + step
        if next_time > track[1][0]:
            track.pop(0)
            continue
        distance = calculate_distance_lat_lon(
            (track[0][1], track[0][2]), (track[1][1], track[1][2])
        )
        if distance < 0.001:
            new_position = (track[1][1], track[1][2])
        else:
            time_difference = (track[1][0] - track[0][0]).total_seconds()
            time_difference_after_previous = (next_time - track[0][0]).total_seconds()
            fraction = time_difference_after_previous / time_difference
            new_position = calculate_fractional_distance_point_lat_lon(
                (track[0][1], track[0][2]), (track[1][1], track[1][2]), fraction
            )
        interpolated.append(new_position)
        current_time = next_time
    return start_time, current_time - step, interpolated


class GPSTrack:
    def __init__(self, name: str, track: List[Tuple[datetime, float, float, float]]):
        """

        :param track: timestamp, Latitude, longitude, altitude (m)
        """
        self.name = name
        self.track = track
        self.step = timedelta(seconds=1)
        self.start_time, self.finish_time, self.interpolated = get_normalised_track(
            track, self.step
        )

    def __str__(self):
        return self.name

    def clip_track(self, start_time: datetime, finish_time: datetime):
        start_index = int(max((start_time - self.start_time).total_seconds(), 0))
        finish_index = int(min((finish_time - self.start_time).total_seconds(), len(self.interpolated)))
        self.interpolated = self.interpolated[start_index:finish_index]
        self.start_time = max(self.start_time, start_time)
        self.finish_time = min(self.finish_time, finish_time)

    def get_normalised_position_at_time(
            self, timestamp: datetime
    ) -> Optional[Tuple[float, float]]:
        assert (
                timestamp % self.step == timedelta()
        ), f"Timestamp must be a whole number of {self.step}"
        if timestamp < self.start_time or timestamp > self.finish_time:
            return None
        index = (timestamp - self.start_time).total_seconds()
        assert index.is_integer(), "Index is not an integer"
        return self.interpolated[int(index)]

    def plot_track(self):
        plt.figure(figsize=(3, 3))
        imagery = OSM()
        ax = plt.axes(projection=imagery.crs)
        path = np.array(self.interpolated)
        ys, xs = path.T
        plt.plot(xs, ys, transform=ccrs.PlateCarree(), color="blue", linewidth=1)
        ax.add_image(imagery, 11)
        plt.savefig(f"{self.name}_track.png", format="png", dpi=400, transparent=True)

    def plot_track_existing_figure(self, ax, color, label):
        path = np.array(self.interpolated)
        ys, xs = path.T
        ax.plot(
            xs,
            ys,
            transform=ccrs.PlateCarree(),
            color=color,
            linewidth=0.2,
            label=label,
        )

    @classmethod
    def load_gpx(cls, name: str, filename: str) -> "GPSTrack":
        with open(filename, "r") as file:
            gpx = gpxpy.parse(file)
        path = []
        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    path.append(
                        (
                            datetime(
                                year=point.time.year,
                                month=point.time.month,
                                day=point.time.day,
                                hour=point.time.hour,
                                minute=point.time.minute,
                                second=point.time.second,
                                microsecond=point.time.microsecond,
                                tzinfo=timezone.utc,
                            ),
                            point.latitude,
                            point.longitude,
                            point.elevation if point.elevation else 0,
                        )
                    )
        return cls(name, path)
