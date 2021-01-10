from io import BytesIO

import pytz
import datetime
import os
import sys
from typing import Optional, Tuple, List

from cartopy.io.img_tiles import OSM
import matplotlib.pyplot as plt
import numpy as np
import cartopy.crs as ccrs

from display.coordinate_utilities import calculate_distance_lat_lon, calculate_bearing, \
    calculate_fractional_distance_point_lat_lon, get_heading_difference
from display.wind_utilities import calculate_ground_speed_combined

if __name__ == "__main__":
    sys.path.append("../")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()

from display.models import Route, Contestant, NavigationTask, create_perpendicular_line_at_end
from display.waypoint import Waypoint

LINEWIDTH = 0.5
LOCAL_TIME_ZONE = pytz.timezone("Europe/Oslo")


def get_course_position(start: Tuple[float, float], finish: Tuple[float, float], left_side: bool, distance_nm: float) -> \
        Tuple[float, float]:
    centre = calculate_fractional_distance_point_lat_lon(start, finish, 0.5)
    return centre
    # positions = create_perpendicular_line_at_end(*reversed(start), *reversed(centre), distance_nm * 1852)
    # if left_side:
    #     return tuple(reversed(positions[0]))
    # return tuple(reversed(positions[1]))


def create_minute_lines(start: Tuple[float, float], finish: Tuple[float, float], air_speed: float, wind_speed: float,
                        wind_direction: float, gate_start_time: datetime.datetime, route_start_time: datetime.datetime,
                        resolution_seconds: int = 60,
                        line_width_nm=0.5) -> List[
    Tuple[Tuple[Tuple[float, float], Tuple[float, float]], Tuple[float, float], datetime.datetime]]:
    """

    :param start:
    :param finish:
    :param air_speed:
    :param wind_speed:
    :param wind_direction:
    :param gate_start_time: The time of the contestant crosses out from the gate (so remember to factor in procedure turns in that time)
    :param route_start_time:
    :param resolution_seconds:
    :param line_width_nm:
    :return:
    """
    bearing = calculate_bearing(start, finish)
    ground_speed = calculate_ground_speed_combined(bearing, air_speed, wind_speed,
                                                   wind_direction)
    length = calculate_distance_lat_lon(start, finish) / 1852  # NM
    leg_time = length / ground_speed * 3600  # seconds

    def time_to_position(seconds):
        return calculate_fractional_distance_point_lat_lon(start, finish, seconds / leg_time)

    lines = []
    gate_start_elapsed = (gate_start_time - route_start_time).total_seconds()
    time_to_next_line = resolution_seconds - gate_start_elapsed % resolution_seconds
    if time_to_next_line == 0:
        time_to_next_line += resolution_seconds
    while time_to_next_line < leg_time:
        line_position = time_to_position(time_to_next_line)
        lines.append((create_perpendicular_line_at_end(*reversed(start), *reversed(line_position),
                                                       line_width_nm * 1852), line_position,
                      gate_start_time + datetime.timedelta(seconds=time_to_next_line)))
        time_to_next_line += resolution_seconds
    return lines


A4 = "A4"
A3 = "A3"


def plot_route(task: NavigationTask, map_size: str, zoom_level: Optional[int]=None, landscape: bool = True, contestant: Optional[Contestant] = None,
               minute_marks: bool = True, courses: bool = True):
    route = task.route
    imagery = OSM()
    if map_size == A3:
        if zoom_level is None:
            zoom_level = 12
        if landscape:
            plt.figure(figsize=(16.53, 11.69))
        else:
            plt.figure(figsize=(11.69, 16.53))
    else:
        if zoom_level is None:
            zoom_level = 11
        if landscape:
            plt.figure(figsize=(11.69, 8.27))
        else:
            plt.figure(figsize=(8.27, 11.69))

    ax = plt.axes(projection=imagery.crs)
    ax.add_image(imagery, zoom_level)
    ax.set_aspect("auto")
    line = []
    tracks = [[]]
    for waypoint in route.waypoints:  # type: Waypoint
        if waypoint.type == "isp":
            tracks.append([])
        if waypoint.type in ("tp", "sp", "fp", "isp", "ifp"):
            tracks[-1].append(waypoint)
    for track in tracks:
        for index, waypoint in enumerate(track):  # type: int, Waypoint
            if waypoint.type != "secret":
                ys, xs = np.array(waypoint.gate_line).T
                plt.plot(xs, ys, transform=ccrs.PlateCarree(), color="blue", linewidth=LINEWIDTH)
                text = "{}".format(waypoint.name)
                bearing = waypoint.bearing_from_previous
                if index == 0:
                    bearing = waypoint.bearing_next
                if contestant is not None:
                    waypoint_time = contestant.gate_times.get(waypoint.name)  # type: datetime.datetime
                    if waypoint_time is not None:
                        local_waypoint_time = waypoint_time.astimezone(task.contest.time_zone or LOCAL_TIME_ZONE)
                        text += " {}".format(local_waypoint_time.strftime("%H:%M:%S"))
                bearing_difference = get_heading_difference(waypoint.bearing_from_previous, waypoint.bearing_next)
                if bearing_difference > 0:
                    text = "\n" + text + " " * len(text) + "    "  # Padding to get things aligned correctly
                else:
                    text = "\n    " + " " * len(text) + text  # Padding to get things aligned correctly
                plt.text(waypoint.longitude, waypoint.latitude, text, verticalalignment="center", color="blue",
                         horizontalalignment="center", transform=ccrs.PlateCarree(), fontsize=8, rotation=-bearing,
                         linespacing=2, family="monospace")
                if contestant is not None:
                    if index < len(track) - 1:
                        if courses:
                            bearing = waypoint.bearing_next
                            bearing_difference_next = get_heading_difference(track[index + 1].bearing_from_previous,
                                                                             track[index + 1].bearing_next)
                            bearing_difference_previous = get_heading_difference(waypoint.bearing_from_previous,
                                                                                 waypoint.bearing_next)
                            course_position = get_course_position((waypoint.latitude, waypoint.longitude),
                                                                  (track[index + 1].latitude,
                                                                   track[index + 1].longitude),
                                                                  True, 3)
                            course_text = "{:03.0f}".format(waypoint.bearing_next)
                            # Try to keep it out of the way of the next leg
                            if bearing_difference_next > 90 or bearing_difference_previous > 90:  # leftSide
                                label = "\n" + course_text + " " * len(course_text) + "    "
                            else:  # Right-sided is preferred
                                label = "\n" + " " * len(course_text) + "    " + course_text
                            plt.text(course_position[1], course_position[0], label,
                                     verticalalignment="center", color="red",
                                     horizontalalignment="center", transform=ccrs.PlateCarree(), fontsize=16,
                                     rotation=-bearing,
                                     linespacing=2, family="monospace")
                        if minute_marks:
                            gate_start_time = contestant.gate_times.get(waypoint.name)
                            if waypoint.is_procedure_turn:
                                gate_start_time += datetime.timedelta(minutes=1)
                            minute_lines = create_minute_lines((waypoint.latitude, waypoint.longitude),
                                                               (track[index + 1].latitude, track[index + 1].longitude),
                                                               contestant.air_speed, contestant.wind_speed,
                                                               contestant.wind_direction,
                                                               gate_start_time,
                                                               contestant.gate_times.get(track[0].name))
                            for mark_line, line_position, timestamp in minute_lines:
                                xs, ys = np.array(mark_line).T  # Already comes in the format lon, lat
                                plt.plot(xs, ys, transform=ccrs.PlateCarree(), color="blue", linewidth=LINEWIDTH)
                                time_format = "%M"
                                if timestamp.second != 0:
                                    time_format = "%M:%S"
                                time_string = timestamp.strftime(time_format)
                                text = "\n " + " " * len(time_string) + time_string
                                plt.text(line_position[1], line_position[0], text, verticalalignment="center",
                                         color="blue",
                                         horizontalalignment="center", transform=ccrs.PlateCarree(), fontsize=8,
                                         rotation=-bearing,
                                         linespacing=2, family="monospace")

            if waypoint.is_procedure_turn:
                line.extend(waypoint.procedure_turn_points)
            else:
                line.append((waypoint.latitude, waypoint.longitude))
        path = np.array(line)
        minimum_latitude = np.min(path[:, 0])
        minimum_longitude = np.min(path[:, 1])
        maximum_latitude = np.max(path[:, 0])
        maximum_longitude = np.max(path[:, 1])
        map_margin = 6000  # metres
        longitude_scale = map_margin / calculate_distance_lat_lon((minimum_latitude, minimum_longitude),
                                                                  (minimum_latitude, minimum_longitude + 1))
        latitude_scale = map_margin / calculate_distance_lat_lon((minimum_latitude, minimum_longitude),
                                                                 (minimum_latitude + 1, minimum_longitude))
        extent = [minimum_longitude - longitude_scale, maximum_longitude + longitude_scale,
                  minimum_latitude - latitude_scale, maximum_latitude + latitude_scale]
        ax.set_extent(extent)
        ys, xs = path.T

        plt.plot(xs, ys, transform=ccrs.PlateCarree(), color="blue", linewidth=LINEWIDTH)
    if contestant is not None:
        plt.title("Track: '{}' - Contestant: {} - Wind: {:03.0f}/{:02.0f}".format(route.name, contestant,
                                                                                  contestant.wind_direction,
                                                                                  contestant.wind_speed))
    else:
        plt.title("Track: '{}'".format(route.name))
    plt.tight_layout()
    # plt.savefig("map.png", dpi=600)
    figdata = BytesIO()
    plt.savefig(figdata, format='png', dpi=600)
    plt.close()
    figdata.seek(0)
    return figdata


if __name__ == "__main__":
    task = NavigationTask.objects.get(pk=76)
    contestant = Contestant.objects.get(pk=1803)
    plot_route(task, contestant=contestant)
