from io import BytesIO

import pytz
import datetime
import os
import sys
from typing import Optional

from cartopy.io.img_tiles import OSM
import matplotlib.pyplot as plt
import numpy as np
import cartopy.crs as ccrs

from display.coordinate_utilities import calculate_distance_lat_lon

if __name__ == "__main__":
    sys.path.append("../")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()

from display.models import Route, Contestant, NavigationTask
from display.waypoint import Waypoint

LINEWIDTH = 0.5
LOCAL_TIME_ZONE = pytz.timezone("Europe/Oslo")


def plot_route(task: NavigationTask, contestant: Optional[Contestant] = None):
    route = task.route
    imagery = OSM()
    plt.figure(figsize=(16.53, 11.69))
    ax = plt.axes(projection=imagery.crs)
    ax.add_image(imagery, 12)
    ax.set_aspect("auto")
    line = []
    for index, waypoint in enumerate(route.waypoints):  # type: Waypoint
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
                    local_waypoint_time = waypoint_time.astimezone(task.time_zone or LOCAL_TIME_ZONE)
                    text += " {}".format(local_waypoint_time.strftime("%H:%M:%S"))
            text = "\n" + " "*len(text) + text  # Padding to get things aligned correctly
            plt.text(waypoint.longitude, waypoint.latitude, text, verticalalignment="center", color="blue",
                     horizontalalignment="center", transform=ccrs.PlateCarree(), fontsize=8, rotation=-bearing,
                     linespacing=2)

        if waypoint.is_procedure_turn:
            line.extend(waypoint.procedure_turn_points)
        else:
            line.append((waypoint.latitude, waypoint.longitude))
    path = np.array(line)
    minimum_latitude = np.min(path[:, 0])
    minimum_longitude = np.min(path[:, 1])
    maximum_latitude = np.max(path[:, 0])
    maximum_longitude = np.max(path[:, 1])
    map_margin = 3000  # metres
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
    plt.savefig("map.png", dpi=600)
    figdata = BytesIO()
    plt.savefig(figdata, format='png')
    plt.close()
    figdata.seek(0)
    return figdata


if __name__ == "__main__":
    task = NavigationTask.objects.get(pk=76)
    contestant = Contestant.objects.get(pk=1803)
    plot_route(task, contestant=contestant)
