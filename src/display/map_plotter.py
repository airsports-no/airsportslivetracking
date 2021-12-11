import logging
from io import BytesIO

import six
import datetime
import os
import sys
from typing import Optional, Tuple, List

from PIL import Image
from cartopy.io.img_tiles import OSM, GoogleWTS
import matplotlib.pyplot as plt
import numpy as np
import cartopy.crs as ccrs
from matplotlib import patheffects
from shapely.geometry import Polygon

from display.coordinate_utilities import (
    calculate_distance_lat_lon,
    calculate_bearing,
    calculate_fractional_distance_point_lat_lon,
    get_heading_difference,
    project_position_lat_lon,
    create_perpendicular_line_at_end_lonlat, utm_from_lat_lon, bearing_difference,
)
from display.wind_utilities import (
    calculate_ground_speed_combined,
    calculate_wind_correction_angle,
)

if __name__ == "__main__":
    sys.path.append("../")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()

from display.models import Route, Contestant, NavigationTask
from display.waypoint import Waypoint

LINEWIDTH = 0.5

logger = logging.getLogger(__name__)


def create_minute_lines(
        start: Tuple[float, float],
        finish: Tuple[float, float],
        air_speed: float,
        wind_speed: float,
        wind_direction: float,
        gate_start_time: datetime.datetime,
        route_start_time: datetime.datetime,
        resolution_seconds: int = 60,
        line_width_nm=0.5,
) -> List[
    Tuple[
        Tuple[Tuple[float, float], Tuple[float, float]],
        Tuple[float, float],
        datetime.datetime,
    ]
]:
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
    ground_speed = calculate_ground_speed_combined(
        bearing, air_speed, wind_speed, wind_direction
    )
    length = calculate_distance_lat_lon(start, finish) / 1852  # NM
    leg_time = length / ground_speed * 3600  # seconds

    def time_to_position(seconds):
        return calculate_fractional_distance_point_lat_lon(
            start, finish, seconds / leg_time
        )

    lines = []
    gate_start_elapsed = (gate_start_time - route_start_time).total_seconds()
    time_to_next_line = resolution_seconds - gate_start_elapsed % resolution_seconds
    if time_to_next_line == 0:
        time_to_next_line += resolution_seconds
    while time_to_next_line < leg_time:
        line_position = time_to_position(time_to_next_line)
        lines.append(
            (
                create_perpendicular_line_at_end_lonlat(
                    *reversed(start), *reversed(line_position), line_width_nm * 1852
                ),
                line_position,
                gate_start_time + datetime.timedelta(seconds=time_to_next_line),
            )
        )
        time_to_next_line += resolution_seconds
    return lines


def create_minute_lines_track(
        track: List[Tuple[float, float]],
        air_speed: float,
        wind_speed: float,
        wind_direction: float,
        gate_start_time: datetime.datetime,
        route_start_time: datetime.datetime,
        start_offset: Optional[float] = None,
        end_offset: Optional[float] = None,
        resolution_seconds: int = 60,
        line_width_nm=0.5,
) -> List[
    Tuple[
        Tuple[Tuple[float, float], Tuple[float, float]],
        Tuple[float, float],
        datetime.datetime,
    ]
]:
    """
    Generates a track that goes through the centre of the route (or corridor if it exists)

    :param end_offset: The distance from the centre of the track to place the minute number near the end of the track. If this is omitted, the start of that is used all the way.
    :param start_offset: The distance from the centre of track to place the minute number (nm). If this is none, line width is used
    :param track: List of positions that represents the path between two gates
    :param air_speed:
    :param wind_speed:
    :param wind_direction:
    :param gate_start_time: The time of the contestant crosses out from the gate (so remember to factor in procedure turns in that time)
    :param route_start_time:
    :param resolution_seconds:
    :param line_width_nm:
    :return:
    """
    gate_start_elapsed = (gate_start_time - route_start_time).total_seconds()
    time_to_next_line = resolution_seconds - gate_start_elapsed % resolution_seconds
    if time_to_next_line == 0:
        time_to_next_line += resolution_seconds
    accumulated_time = 0
    lines = []
    for index in range(0, len(track) - 1):
        start = track[index]
        finish = track[index + 1]
        bearing = calculate_bearing(start, finish)
        ground_speed = calculate_ground_speed_combined(
            bearing, air_speed, wind_speed, wind_direction
        )
        length = calculate_distance_lat_lon(start, finish) / 1852
        leg_time = 3600 * length / ground_speed  # seconds
        while time_to_next_line < leg_time + accumulated_time:
            internal_leg_time = time_to_next_line - accumulated_time
            fraction = internal_leg_time / leg_time
            line_position = calculate_fractional_distance_point_lat_lon(
                start, finish, fraction
            )
            minute_mark = create_perpendicular_line_at_end_lonlat(
                *reversed(start), *reversed(line_position), line_width_nm * 1852
            )
            if start_offset is None:
                number_distance = line_width_nm
            elif end_offset is None:
                number_distance = start_offset
            else:
                number_distance = start_offset + (fraction * (end_offset - start_offset))
                if number_distance > 2:
                    number_distance = line_width_nm

            text_position = extend_point_to_the_right(bearing, (
                tuple(reversed(minute_mark[0])), tuple(reversed(minute_mark[1]))), 1852 * number_distance / 2)
            lines.append(
                (
                    minute_mark,
                    text_position,
                    gate_start_time + datetime.timedelta(seconds=time_to_next_line),
                )
            )
            time_to_next_line += resolution_seconds
        accumulated_time += leg_time
    for line in lines:
        print(line)
    return lines


A4 = "A4"
A3 = "A3"


def country_code_to_map_source(country_code: str) -> str:
    map = {"no": "/maptiles/Norway_N250"}
    return map.get(country_code, "cyclosm")


class FlightContest(GoogleWTS):
    def _image_url(self, tile):
        x, y, z = tile
        y = (2 ** z) - y - 1
        return f"https://tiles.flightcontest.de/{z}/{x}/{y}.png"

    def get_image(self, tile):
        if six.PY3:
            from urllib.request import urlopen, Request, HTTPError, URLError
        else:
            from urllib2 import urlopen, Request, HTTPError, URLError

        url = self._image_url(tile)
        try:
            request = Request(url, headers={"User-Agent": self.user_agent})
            fh = urlopen(request)
            im_data = six.BytesIO(fh.read())
            fh.close()
            img = Image.open(im_data)

        except (HTTPError, URLError) as err:
            print(err)
            img = Image.fromarray(
                np.full((256, 256, 3), (255, 255, 255), dtype=np.uint8)
            )

        img = img.convert(self.desired_tile_form)
        return img, self.tileextent(tile), "lower"


class OpenAIP(GoogleWTS):
    def _image_url(self, tile):
        x, y, z = tile
        s = "1"
        ext = "png"
        return f"http://{s}.tile.maps.openaip.net/geowebcache/service/tms/1.0.0/openaip_basemap@EPSG%3A900913@png/{z}/{x}/{y}.{ext}"


class MapTilerOutdoor(GoogleWTS):
    def _image_url(self, tile):
        x, y, z = tile
        return f"https://api.maptiler.com/maps/outdoor/{z}/{x}/{y}.png?key=YxHsFU6aEqsEULL34uJT"


class CyclOSM(GoogleWTS):
    def _image_url(self, tile):
        x, y, z = tile
        return f"https://a.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png"


class LocalImages(GoogleWTS):
    def __init__(self, folder: str, **kwargs):
        super().__init__(**kwargs)
        self.folder = folder

    def _image_url(self, tile):
        x, y, z = tile
        return "file://{}/{}/{}/{}.png".format(self.folder, z, x, y)

    def tileextent(self, x_y_z):
        """Return extent tuple ``(x0,x1,y0,y1)`` in Mercator coordinates."""
        x, y, z = x_y_z
        x_lim, y_lim = self.tile_bbox(x, y, z, y0_at_north_pole=False)
        return tuple(x_lim) + tuple(y_lim)

    _tileextent = tileextent

    # def subtiles(self, x_y_z):
    #     x, y, z = x_y_z
    #     # Google tile specific (i.e. up->down).
    #     for xi in range(0, 2):
    #         for yi in range(0, 2):
    #             ry=y * 2 + yi
    #             result = x * 2 + xi, (ry*2) + yi, z + 1
    #             print(result)
    #             yield result
    #
    # _subtiles = subtiles
    # def tileextent(self, x_y_z):
    #     """Return extent tuple ``(x0,x1,y0,y1)`` in Mercator coordinates."""
    #     x, y, z = x_y_z
    #     x_lim, y_lim = self.tile_bbox(x, y, z, y0_at_north_pole=True)
    #     # return [-1.70230674884, 32.2907623616, 57.5458684362, 71.7652057932]
    #     return [577671.47,475230.47,6378894.33, 7962889.13]
    #     # return [57.5458684362, 32.2907623616], [71.7652057932, -1.70230674884]
    #     # return tuple(x_lim) + tuple(y_lim)


def scale_bar(
        ax,
        proj,
        length,
        location=(0.5, 0.05),
        linewidth=3,
        units="km",
        m_per_unit=1000,
        scale=0,
):
    """
    http://stackoverflow.com/a/35705477/1072212
    ax is the axes to draw the scalebar on.
    proj is the projection the axes are in
    location is center of the scalebar in axis coordinates ie. 0.5 is the middle of the plot
    length is the length of the scalebar in km.
    linewidth is the thickness of the scalebar.
    units is the name of the unit
    m_per_unit is the number of meters in a unit
    """
    # find lat/lon center to find best UTM zone
    x0, x1, y0, y1 = ax.get_extent(proj.as_geodetic())
    # Projection in metres
    utm = utm_from_lat_lon((y0 + y1) / 2, (x0 + x1) / 2)
    # Get the extent of the plotted area in coordinates in metres
    x0, x1, y0, y1 = ax.get_extent(utm)
    # Turn the specified scalebar location into coordinates in metres
    sbcx, sbcy = x0 + (x1 - x0) * location[0], y0 + (y1 - y0) * location[1]
    # Generate the x coordinate for the ends of the scalebar
    ruler_scale = 100 * 1852 * length / (scale * 1000)  # cm
    bar_length = 10 * scale * 1000 / (100 * 1852)  # NM (10 is cm)
    x_offset = bar_length * m_per_unit
    bar_xs = [sbcx - x_offset / 2, sbcx + x_offset / 2]
    # buffer for scalebar
    buffer = [patheffects.withStroke(linewidth=5, foreground="w")]
    # Plot the scalebar with buffer
    x0, y = proj.transform_point(bar_xs[0], sbcy, utm)
    x1, _ = proj.transform_point(bar_xs[1], sbcy, utm)
    xc, yc = proj.transform_point(sbcx, sbcy + 200, utm)
    ax.plot(
        [x0, x1],
        [y, y],
        transform=proj,
        color="k",
        linewidth=linewidth,
        path_effects=buffer,
        solid_capstyle="butt",
    )
    # buffer for text
    buffer = [patheffects.withStroke(linewidth=3, foreground="w")]
    # Plot the scalebar label
    t0 = ax.text(
        xc,
        yc,
        "1:{:,d} {:.2f} {} = {:.0f} cm".format(
            int(scale * 1000), bar_length, units, 10
        ),
        transform=proj,
        horizontalalignment="center",
        verticalalignment="bottom",
        path_effects=buffer,
        zorder=2,
    )
    # left = x0 + (x1 - x0) * 0.05
    # Plot the N arrow
    # t1 = ax.text(left, sbcy, u'\u25B2\nN', transform=utm,
    #              horizontalalignment='center', verticalalignment='bottom',
    #              path_effects=buffer, zorder=2)

    # Plot the scalebar without buffer, in case covered by text buffer
    ax.plot(
        [x0, x1],
        [y, y],
        transform=proj,
        color="k",
        linewidth=linewidth,
        zorder=3,
        solid_capstyle="butt",
    )


def scale_bar_y(
        ax,
        proj,
        length,
        location=(0.05, 0.5),
        linewidth=3,
        units="km",
        m_per_unit=1000,
        scale=0,
):
    """
    http://stackoverflow.com/a/35705477/1072212
    ax is the axes to draw the scalebar on.
    proj is the projection the axes are in
    location is center of the scalebar in axis coordinates ie. 0.5 is the middle of the plot
    length is the length of the scalebar in km.
    linewidth is the thickness of the scalebar.
    units is the name of the unit
    m_per_unit is the number of meters in a unit

    """
    print("Scale y")
    # find lat/lon center to find best UTM zone
    x0, x1, y0, y1 = ax.get_extent(proj.as_geodetic())
    # Projection in metres
    utm = utm_from_lat_lon((y0 + y1) / 2, (x0 + x1) / 2)
    # Get the extent of the plotted area in coordinates in metres
    x0, x1, y0, y1 = ax.get_extent(utm)
    # Turn the specified scalebar location into coordinates in metres
    sbcx, sbcy = x0 + (x1 - x0) * location[0], y0 + (y1 - y0) * location[1]
    # Generate the x coordinate for the ends of the scalebar
    ruler_scale = 100 * 1852 * length / (scale * 1000)  # cm
    bar_length = 10 * scale * 1000 / (100 * 1852)  # NM (10 is cm)
    y_offset = bar_length * m_per_unit
    bar_ys = [sbcy - y_offset / 2, sbcy + y_offset / 2]
    # buffer for scalebar
    buffer = [patheffects.withStroke(linewidth=5, foreground="w")]
    # Plot the scalebar with buffer
    x, y0 = proj.transform_point(sbcx, bar_ys[0], utm)
    _, y1 = proj.transform_point(sbcx, bar_ys[1], utm)
    xc, yc = proj.transform_point(sbcx + 400, sbcy, utm)
    ax.plot(
        [x, x],
        [y0, y1],
        transform=proj,
        color="k",
        linewidth=linewidth,
        path_effects=buffer,
        solid_capstyle="butt",
    )
    # buffer for text
    buffer = [patheffects.withStroke(linewidth=3, foreground="w")]
    # Plot the scalebar label
    t0 = ax.text(
        xc,
        yc,
        "1:{:,d} {:.2f} {} = {:.0f} cm".format(
            int(scale * 1000), bar_length, units, 10
        ),
        transform=proj,
        horizontalalignment="center",
        verticalalignment="bottom",
        path_effects=buffer,
        zorder=2,
        rotation=-90,
        ha="center",
        va="center",
    )
    # left = x0 + (x1 - x0) * 0.05
    # Plot the N arrow
    # t1 = ax.text(left, sbcy, u'\u25B2\nN', transform=utm,
    #              horizontalalignment='center', verticalalignment='bottom',
    #              path_effects=buffer, zorder=2)

    # Plot the scalebar without buffer, in case covered by text buffer
    ax.plot(
        [x, x],
        [y0, y1],
        transform=proj,
        color="k",
        linewidth=linewidth,
        zorder=3,
        solid_capstyle="butt",
    )


# if __name__ == '__main__':
#     ax = plt.axes(projection=ccrs.Mercator())
#     plt.title('Cyprus')
#     ax.set_extent([31, 35.5, 34, 36], ccrs.Geodetic())
#     ax.stock_img()
#     ax.coastlines(resolution='10m')
#     scale_bar(ax, ccrs.Mercator(), 100)  # 100 km scale bar
#     # or to use m instead of km
#     # scale_bar(ax, ccrs.Mercator(), 100000, m_per_unit=1, units='m')
#     # or to use miles instead of km
#     # scale_bar(ax, ccrs.Mercator(), 60, m_per_unit=1609.34, units='miles')
#     plt.show()
def inch2cm(inch: float) -> float:
    return inch * 2.54


def cm2inch(cm: float) -> float:
    return cm / 2.54


def calculate_extent(width: float, height: float, centre: Tuple[float, float]):
    left_edge = project_position_lat_lon(centre, 270, width / 2)[1]
    right_edge = project_position_lat_lon(centre, 90, width / 2)[1]
    top_edge = project_position_lat_lon(centre, 0, height / 2)[0]
    bottom_edge = project_position_lat_lon(centre, 180, height / 2)[0]
    return [left_edge, right_edge, bottom_edge, top_edge]


def plot_leg_bearing(
        current_waypoint,
        next_waypoint,
        air_speed,
        wind_speed,
        wind_direction,
        character_offset: int = 4,
        fontsize: int = 14,
):
    left_of_leg_start = current_waypoint.get_gate_position_left_of_track(True)
    left_of_leg_finish = next_waypoint.get_gate_position_left_of_track(True)

    bearing = current_waypoint.bearing_next
    wind_correction_angle = calculate_wind_correction_angle(
        bearing, air_speed, wind_speed, wind_direction
    )
    bearing_difference_next = get_heading_difference(
        next_waypoint.bearing_from_previous, next_waypoint.bearing_next
    )
    bearing_difference_previous = get_heading_difference(
        current_waypoint.bearing_from_previous, current_waypoint.bearing_next
    )
    course_position = calculate_fractional_distance_point_lat_lon(left_of_leg_start, left_of_leg_finish, 0.5)
    course_text = "{:03.0f}".format(
        current_waypoint.bearing_next - wind_correction_angle
    )
    label = course_text + " " * (len(course_text) + 1)
    # Try to keep it out of the way of the next leg
    # if bearing_difference_next > 60 or bearing_difference_previous > 60:  # leftSide
    #     label = "" + course_text + " " * len(course_text) + " " * character_offset
    # else:  # Right-sided is preferred
    #     label = "" + " " * len(course_text) + " " * character_offset + course_text
    plt.text(
        course_position[1],
        course_position[0],
        label,
        verticalalignment="center",
        color="red",
        horizontalalignment="center",
        transform=ccrs.PlateCarree(),
        fontsize=fontsize,
        rotation=-bearing,
        linespacing=1,
        family="monospace",
    )


def waypoint_bearing(waypoint, index) -> float:
    bearing = waypoint.bearing_from_previous
    if index == 0:
        bearing = waypoint.bearing_next
    return bearing


def plot_prohibited_zones(route: Route, target_projection, ax):
    PROHIBITED_COLOURS = {
        "prohibited": ("red", "darkred"),
        "penalty": ("orange", "darkorange"),
        "info": ("lightblue", "Lightskyblue"),
        "gate": ("blue", "darkblue"),
    }
    for prohibited in route.prohibited_set.all():
        line = []
        for element in prohibited.path:
            line.append(
                target_projection.transform_point(
                    *list(reversed(element)), ccrs.PlateCarree()
                )
            )
        polygon = Polygon(line)
        centre = polygon.centroid
        fill_colour, line_colour = PROHIBITED_COLOURS.get(prohibited.type, ("blue", "darkblue"))
        ax.add_geometries(
            [polygon],
            crs=target_projection,
            facecolor=fill_colour,
            alpha=0.4,
            linewidth=2,
            edgecolor=line_colour
        )
        plt.text(centre.x, centre.y, prohibited.name, horizontalalignment="center")


def extend_point_to_the_right(track_bearing: float, line: Tuple[Tuple[float, float], Tuple[float, float]],
                              distance: float) -> Tuple[float, float]:
    gate_line_bearing = calculate_bearing(*line)
    right = (gate_line_bearing - track_bearing) % 360.0 > 0
    if not right:
        line = reversed(line)
        gate_line_bearing = (gate_line_bearing + 180) % 360
    if distance == 0:
        return line[1]
    return project_position_lat_lon(line[1], gate_line_bearing, distance)


def plot_waypoint_name(
        route: Route,
        waypoint: Waypoint,
        bearing: float,
        annotations: bool,
        waypoints_only: bool,
        contestant: Optional[Contestant],
        line_width: float,
        colour: str,
        character_padding: int = 2,
):
    if not waypoint.time_check and not waypoint.gate_check:
        return
    waypoint_name = "{}".format(waypoint.name)
    timing = ""
    if contestant is not None and annotations:
        waypoint_time = contestant.gate_times.get(
            waypoint.name
        )  # type: datetime.datetime
        if waypoint_time is not None and waypoint.time_check:
            local_waypoint_time = waypoint_time.astimezone(
                route.navigationtask.contest.time_zone
            )
            timing = " {}".format(local_waypoint_time.strftime("%M:%S"))

    name_position = []
    timing_position = []
    rotation = -bearing
    logger.debug(f"Waypoint {waypoint.name}")
    if len(waypoint.gate_line):
        timing_position = waypoint.get_gate_position_right_of_track()
        name_position = waypoint.get_gate_position_left_of_track()
        bearing_to_the_right = calculate_bearing(name_position, timing_position)
        rotation = -bearing_to_the_right + 90

    if waypoints_only:
        rotation = 0
    if len(timing):
        timing = " " * (0 + len(timing)) + timing
        plt.text(
            timing_position[1] if len(timing_position) else waypoint.longitude,
            timing_position[0] if len(timing_position) else waypoint.latitude,
            timing,
            verticalalignment="center",
            color=colour,
            horizontalalignment="center",
            transform=ccrs.PlateCarree(),
            fontsize=8,
            rotation=rotation,
            # linespacing=2,
            family="monospace",
            clip_on=True,
        )
    waypoint_name = waypoint_name + " " * (2 + len(waypoint_name))
    plt.text(
        name_position[1] if len(name_position) else waypoint.longitude,
        name_position[0] if len(name_position) else waypoint.latitude,
        waypoint_name,
        verticalalignment="center",
        color=colour,
        horizontalalignment="center",
        transform=ccrs.PlateCarree(),
        fontsize=8,
        rotation=rotation,
        # linespacing=2,
        family="monospace",
        clip_on=True,
    )


def plot_anr_corridor_track(
        route: Route,
        contestant: Optional[Contestant],
        annotations,
        line_width: float,
        colour: str,
        plot_center_line: bool
):
    inner_track = []
    outer_track = []
    center_track = []
    for index, waypoint in enumerate(route.waypoints):
        ys, xs = np.array(waypoint.gate_line).T
        bearing = waypoint_bearing(waypoint, index)

        if waypoint.type not in ("secret",) and waypoint.time_check:
            plot_waypoint_name(
                route,
                waypoint,
                bearing,
                annotations,
                False,
                contestant,
                line_width,
                "red",
                character_padding=1,
            )
        if route.rounded_corners and waypoint.left_corridor_line is not None:
            inner_track.extend(waypoint.left_corridor_line)
            outer_track.extend(waypoint.right_corridor_line)
        else:
            inner_track.append(waypoint.gate_line[0])
            outer_track.append(waypoint.gate_line[1])
        center_track.append((waypoint.latitude, waypoint.longitude))
        if waypoint.type not in ('secret',) and waypoint.time_check:
            plt.plot(
                xs, ys, transform=ccrs.PlateCarree(), color=colour, linewidth=line_width
            )
        if index < len(route.waypoints) - 1 and annotations and contestant is not None:
            plot_minute_marks(
                waypoint,
                contestant,
                route.waypoints,
                index,
                line_width,
                colour,
                mark_offset=2,
                line_width_nm=0.5,
                adaptive=True
            )
            plot_leg_bearing(
                waypoint,
                route.waypoints[index + 1],
                contestant.air_speed,
                contestant.wind_speed,
                contestant.wind_direction,
                2,
                12,
            )
    if plot_center_line:
        path = np.array(center_track)
        ys, xs = path.T
        plt.plot(
            xs, ys, transform=ccrs.PlateCarree(), color=colour, linewidth=line_width / 2
        )
    path = np.array(inner_track)
    ys, xs = path.T
    plt.plot(xs, ys, transform=ccrs.PlateCarree(), color=colour, linewidth=line_width)
    path = np.array(outer_track)
    ys, xs = path.T
    plt.plot(xs, ys, transform=ccrs.PlateCarree(), color=colour, linewidth=line_width)
    return path


def plot_minute_marks(
        waypoint: Waypoint,
        contestant: Contestant,
        track: List[Waypoint],
        index,
        line_width: float,
        colour: str,
        mark_offset=1,
        line_width_nm: float = 0.5,
        adaptive: bool = False
):
    """

    :param waypoint:
    :param contestant:
    :param track:
    :param index:
    :param line_width:
    :param colour:
    :param mark_offset:
    :param line_width_nm:
    :param adaptive: If true, place the minute mark according to the gate width, otherwise use the static line width
    :return:
    """
    next_waypoint = track[index + 1]
    gate_start_time = contestant.gate_times.get(waypoint.name)
    if waypoint.is_procedure_turn:
        gate_start_time += datetime.timedelta(minutes=1)
    first_segments = waypoint.get_centre_track_segments()
    last_segments = track[index + 1].get_centre_track_segments()
    track_points = (
            first_segments[len(first_segments) // 2:]
            + last_segments[: (len(last_segments) // 2) + 1]
    )
    # print(f"track_points: {track_points}")
    ys, xs = np.array(track_points).T
    # plt.plot(xs, ys, transform=ccrs.PlateCarree(), color="green", linewidth=LINEWIDTH)
    minute_lines = create_minute_lines_track(
        track_points,
        contestant.air_speed,
        contestant.wind_speed,
        contestant.wind_direction,
        gate_start_time,
        contestant.gate_times.get(track[0].name),
        line_width_nm=line_width_nm,
        start_offset=waypoint.width if adaptive else line_width_nm,
        end_offset=next_waypoint.width if adaptive else None
    )
    for mark_line, text_position, timestamp in minute_lines:
        xs, ys = np.array(mark_line).T  # Already comes in the format lon, lat
        plt.plot(
            xs, ys, transform=ccrs.PlateCarree(), color=colour, linewidth=line_width
        )
        time_format = "%M"
        if timestamp.second != 0:
            time_format = "%M:%S"
        time_string = timestamp.strftime(time_format)
        text = " " * mark_offset + time_string
        plt.text(
            text_position[1],
            text_position[0],
            text,
            verticalalignment="center",
            color=colour,
            horizontalalignment="center",
            transform=ccrs.PlateCarree(),
            fontsize=8,
            rotation=-waypoint.bearing_next,
            linespacing=2,
            family="monospace",
        )


def plot_precision_track(
        route: Route,
        contestant: Optional[Contestant],
        waypoints_only: bool,
        annotations: bool,
        line_width: float,
        colour: str,
):
    tracks = [[]]
    for waypoint in route.waypoints:  # type: Waypoint
        if waypoint.type == "isp":
            tracks.append([])
        if waypoint.type in ("tp", "sp", "fp", "isp", "ifp"):
            tracks[-1].append(waypoint)
    for track in tracks:
        line = []
        for index, waypoint in enumerate(track):  # type: int, Waypoint
            if waypoint.type != "secret":
                bearing = waypoint_bearing(waypoint, index)
                ys, xs = np.array(waypoint.gate_line).T
                if not waypoints_only:
                    plt.plot(
                        xs,
                        ys,
                        transform=ccrs.PlateCarree(),
                        color=colour,
                        linewidth=line_width,
                    )
                else:
                    plt.plot(
                        waypoint.longitude,
                        waypoint.latitude,
                        transform=ccrs.PlateCarree(),
                        color=colour,
                        marker="o",
                        markersize=8,
                        fillstyle="none",
                    )
                plot_waypoint_name(
                    route,
                    waypoint,
                    bearing,
                    annotations,
                    waypoints_only,
                    contestant,
                    line_width,
                    "red",
                )
                if contestant is not None:
                    if index < len(track) - 1:
                        if annotations:
                            plot_leg_bearing(
                                waypoint,
                                track[index + 1],
                                contestant.air_speed,
                                contestant.wind_speed,
                                contestant.wind_direction,
                            )
                            plot_minute_marks(
                                waypoint, contestant, track, index, line_width, colour
                            )

            if waypoint.is_procedure_turn:
                line.extend(waypoint.procedure_turn_points)
            else:
                line.append((waypoint.latitude, waypoint.longitude))
        path = np.array(line)
        if not waypoints_only:
            ys, xs = path.T
            plt.plot(
                xs, ys, transform=ccrs.PlateCarree(), color=colour, linewidth=line_width
            )
        return path


def plot_route(
        task: NavigationTask,
        map_size: str,
        zoom_level: Optional[int] = None,
        landscape: bool = True,
        contestant: Optional[Contestant] = None,
        waypoints_only: bool = False,
        annotations: bool = True,
        scale: int = 200,
        dpi: int = 300,
        map_source: str = "osm",
        line_width: float = 0.5,
        colour: str = "#0000ff",
):
    route = task.route
    A4_width = 21.0
    A4_height = 29.7
    A3_height = 42
    A3_width = 29.7
    if map_source == "osm":
        imagery = OSM()
    elif map_source == "fc":
        imagery = FlightContest(desired_tile_form="RGBA")
    elif map_source == "mto":
        imagery = MapTilerOutdoor(desired_tile_form="RGBA")
    elif map_source == "cyclosm":
        imagery = CyclOSM(desired_tile_form="RGBA")
    else:
        imagery = LocalImages(map_source, desired_tile_form="RGBA")
    if map_size == A3:
        if zoom_level is None:
            zoom_level = 12
        if landscape:
            figure_width = A3_height
            figure_height = A3_width
        else:
            figure_width = A3_width
            figure_height = A3_height
    else:
        if zoom_level is None:
            zoom_level = 11
        if landscape:
            figure_width = A4_height
            figure_height = A4_width
        else:
            figure_width = A4_width
            figure_height = A4_height

    plt.figure(figsize=(cm2inch(figure_width), cm2inch(figure_height)))
    ax = plt.axes(projection=imagery.crs)
    # ax.background_patch.set_fill(False)
    # ax.background_patch.set_facecolor((250 / 255, 250 / 255, 250 / 255))
    print(f"Figure projection: {imagery.crs}")
    ax.add_image(imagery, zoom_level)  # , interpolation='spline36', zorder=10)
    # ax.add_image(OpenAIP(), zoom_level, interpolation='spline36', alpha=0.6, zorder=20)
    ax.set_aspect("auto")
    if NavigationTask.PRECISION in task.scorecard.task_type or NavigationTask.POKER in task.scorecard.task_type:
        path = plot_precision_track(
            route, contestant, waypoints_only, annotations, line_width, colour
        )
    elif NavigationTask.ANR_CORRIDOR in task.scorecard.task_type:
        path = plot_anr_corridor_track(
            route, contestant, annotations, line_width, colour, False
        )
    elif NavigationTask.AIRSPORTS in task.scorecard.task_type:
        path = plot_anr_corridor_track(
            route, contestant, annotations, line_width, colour, True
        )
    else:
        path = []
    plot_prohibited_zones(route, imagery.crs, ax)
    ax.gridlines(draw_labels=False, dms=True)
    buffer = [patheffects.withStroke(linewidth=3, foreground="w")]
    if contestant is not None:
        plt.title(
            "Track: '{}' - Contestant: {} - Wind: {:03.0f}/{:02.0f}".format(
                route.name, contestant, contestant.wind_direction, contestant.wind_speed
            ),
            y=1,
            pad=-20,
            color="black",
            fontsize=10,
            path_effects=buffer,
        )
    else:
        plt.title(
            "Track: {}".format(route.navigationtask.name),
            y=1,
            pad=-20,
            path_effects=buffer,
        )

    # plt.tight_layout()
    fig = plt.gcf()
    print(f"Figure size (cm): ({figure_width}, {figure_height})")
    minimum_latitude = np.min(path[:, 0])
    minimum_longitude = np.min(path[:, 1])
    maximum_latitude = np.max(path[:, 0])
    maximum_longitude = np.max(path[:, 1])
    print(f"minimum: {minimum_latitude}, {minimum_longitude}")
    print(f"maximum: {maximum_latitude}, {maximum_longitude}")
    if scale == 0:
        # Zoom to fit
        map_margin = 6000  # metres

        proj = ccrs.PlateCarree()
        x0, x1, y0, y1 = ax.get_extent(proj.as_geodetic())
        print(f"x0: {x0}, y0: {y0}")
        print(f"x1: {x1}, y1: {y1}")

        # Projection in metres
        utm = utm_from_lat_lon((y0 + y1) / 2, (x0 + x1) / 2)
        bottom_left = utm.transform_point(minimum_longitude, minimum_latitude, proj)
        top_left = utm.transform_point(minimum_longitude, maximum_latitude, proj)
        bottom_right = utm.transform_point(maximum_longitude, minimum_latitude, proj)
        top_right = utm.transform_point(maximum_longitude, maximum_latitude, proj)

        print(f"bottom_left: {bottom_left}")
        print(f"top_right: {top_right}")
        x0 = bottom_left[0] - map_margin
        y0 = bottom_left[1] - map_margin
        x1 = top_right[0] + map_margin
        y1 = top_right[1] + map_margin
        print(f"Width at top: {top_right[0] - top_left[0]}")
        print(f"Width at bottom: {bottom_right[0] - bottom_left[0]}")
        horizontal_metres = x1 - x0
        vertical_metres = y1 - y0
        x_centre = (x0 + x1) / 2
        y_centre = (y0 + y1) / 2
        vertical_scale = vertical_metres / figure_height  # m per cm
        horizontal_scale = horizontal_metres / figure_width  # m per cm

        if vertical_scale < horizontal_scale:
            # Increase vertical scale to match
            vertical_metres = horizontal_scale * figure_height
            y0 = y_centre - vertical_metres / 2
            y1 = y_centre + vertical_metres / 2
            x0 += 2000
            x1 -= 2000
            scale = horizontal_metres / (10 * figure_width)
        else:
            # Do not scale in the horizontal direction, just make sure that we do not step over the bounds
            horizontal_metres = vertical_scale * figure_width
            # x0 = x_centre - horizontal_metres / 2
            # x1 = x_centre + horizontal_metres / 2
            scale = vertical_metres / (10 * figure_height)
        print(f"x0: {x0}, y0: {y0}")
        print(f"x1: {x1}, y1: {y1}")
        x0, y0 = proj.transform_point(x0, y0, utm)
        x1, y1 = proj.transform_point(x1, y1, utm)
        print(f"x0: {x0}, y0: {y0}")
        print(f"x1: {x1}, y1: {y1}")
        extent = [x0, x1, y0, y1]
    else:
        proj = ccrs.PlateCarree()
        x0, x1, y0, y1 = ax.get_extent(proj.as_geodetic())
        # Projection in metres
        utm = utm_from_lat_lon((y0 + y1) / 2, (x0 + x1) / 2)
        centre_longitude = (
                minimum_longitude + (maximum_longitude - minimum_longitude) / 2
        )
        centre_latitude = minimum_latitude + (maximum_latitude - minimum_latitude) / 2
        centre_x, centre_y = utm.transform_point(
            centre_longitude, centre_latitude, proj
        )
        width_metres = (scale * 10) * figure_width
        height_metres = (scale * 10) * figure_height
        height_offset = 0
        width_offset = 2000
        lower_left = proj.transform_point(
            centre_x - width_metres / 2 + width_offset,
            centre_y - height_metres / 2 + height_offset,
            utm,
        )
        upper_right = proj.transform_point(
            centre_x + width_metres / 2 - width_offset,
            centre_y + height_metres / 2 - height_offset,
            utm,
        )
        extent = [lower_left[0], upper_right[0], lower_left[1], upper_right[1]]
    print(extent)
    ax.set_extent(extent, crs=ccrs.PlateCarree())
    # scale_bar(ax, ccrs.PlateCarree(), 5, units="NM", m_per_unit=1852, scale=scale)
    scale_bar_y(ax, ccrs.PlateCarree(), 5, units="NM", m_per_unit=1852, scale=scale)
    ax.autoscale(False)
    fig.patch.set_visible(False)
    # lat lon lines
    longitude = np.ceil(extent[0])
    while longitude < extent[1]:
        plt.plot(
            (longitude, longitude),
            (extent[2], extent[3]),
            transform=ccrs.PlateCarree(),
            color="black",
            linewidth=0.5,
        )
        longitude += 1
    latitude = np.ceil(extent[2])
    while latitude < extent[3]:
        plt.plot(
            (extent[0], extent[1]),
            (latitude, latitude),
            transform=ccrs.PlateCarree(),
            color="black",
            linewidth=0.5,
        )
        latitude += 1
    # plt.savefig("map.png", dpi=600)
    fig.subplots_adjust(bottom=0)
    fig.subplots_adjust(top=1)
    fig.subplots_adjust(right=1)
    fig.subplots_adjust(left=0)

    # plot_margin = 1
    # plot_margin = plot_margin / 2.54
    #
    # x0, x1, y0, y1 = plt.axis()
    # plt.axis((x0 - plot_margin,
    #           x1 + plot_margin,
    #           y0 - plot_margin,
    #           y1 + plot_margin))

    figdata = BytesIO()
    plt.savefig(
        figdata, format="png", dpi=dpi, transparent=True
    )  # , bbox_inches="tight", pad_inches=margin_inches/2)
    figdata.seek(0)
    pdfdata = BytesIO()
    plt.savefig(
        pdfdata, format="pdf", dpi=dpi, transparent=True
    )  # , bbox_inches="tight", pad_inches=margin_inches/2)
    plt.close()
    pdfdata.seek(0)

    return figdata, pdfdata


def get_basic_track(positions: List[Tuple[float, float]]):
    """

    :param positions: List of (latitude, longitude) pairs
    :return:
    """
    imagery = OSM()
    ax = plt.axes(projection=imagery.crs)
    ax.add_image(imagery, 7)
    ax.set_aspect("auto")
    ys, xs = np.array(positions).T
    plt.plot(
        xs, ys, transform=ccrs.PlateCarree(), color="blue", linewidth=LINEWIDTH * 2
    )
    index = 1
    for latitude, longitude in positions[1:-1]:
        plt.text(
            longitude,
            latitude,
            f"TP {index}",
            verticalalignment="center",
            color="blue",
            horizontalalignment="center",
            transform=ccrs.PlateCarree(),
            fontsize=6,
        )
        index += 1
    plt.text(
        positions[0][1],
        positions[0][0],
        f"SP",
        verticalalignment="center",
        color="blue",
        horizontalalignment="center",
        transform=ccrs.PlateCarree(),
        fontsize=6,
    )
    plt.text(
        positions[-1][1],
        positions[-1][0],
        f"FP",
        verticalalignment="center",
        color="blue",
        horizontalalignment="center",
        transform=ccrs.PlateCarree(),
        fontsize=6,
    )
    figdata = BytesIO()
    plt.savefig(figdata, format="png", dpi=100, bbox_inches="tight", pad_inches=0)
    plt.close()
    figdata.seek(0)
    return figdata
