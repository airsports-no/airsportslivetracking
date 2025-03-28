import io
import logging
from io import BytesIO

import PIL
import requests
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
import matplotlib

matplotlib.use("Agg")
from matplotlib import patheffects
import matplotlib.ticker as mticker
from pymbtiles import MBtiles
from shapely.geometry import Polygon

from display.flight_order_and_maps.map_plotter_shared_utilities import MAP_ATTRIBUTIONS
from display.flight_order_and_maps.mbtiles_facade import get_map_details
from display.utilities.coordinate_utilities import (
    calculate_distance_lat_lon,
    calculate_bearing,
    calculate_fractional_distance_point_lat_lon,
    get_heading_difference,
    project_position_lat_lon,
    create_perpendicular_line_at_end_lonlat,
    utm_from_lat_lon,
    bearing_difference,
    normalise_bearing,
)
from display.flight_order_and_maps.map_constants import A3
from display.utilities.gate_definitions import (
    SECRETPOINT,
    UNKNOWN_LEG,
    DUMMY,
    TURNPOINT,
    STARTINGPOINT,
    FINISHPOINT,
    INTERMEDIARY_STARTINGPOINT,
    INTERMEDIARY_FINISHPOINT,
)
from display.utilities.navigation_task_type_definitions import (
    PRECISION,
    POKER,
    ANR_CORRIDOR,
    AIRSPORTS,
    AIRSPORT_CHALLENGE,
)
from display.utilities.wind_utilities import (
    calculate_ground_speed_combined,
    calculate_wind_correction_angle,
)
from live_tracking_map.settings import MBTILES_SERVER_URL

A4_WIDTH = 21.0
A4_HEIGHT = 29.7
A3_HEIGHT = 42
A3_WIDTH = 29.7

if __name__ == "__main__":
    sys.path.append("../../")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()

from display.models import (
    Route,
    Contestant,
    NavigationTask,
    EditableRoute,
    UserUploadedMap,
)
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
    ground_speed = calculate_ground_speed_combined(bearing, air_speed, wind_speed, wind_direction)
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
        ground_speed = calculate_ground_speed_combined(bearing, air_speed, wind_speed, wind_direction)
        length = calculate_distance_lat_lon(start, finish) / 1852
        leg_time = 3600 * length / ground_speed  # seconds
        while time_to_next_line < leg_time + accumulated_time:
            internal_leg_time = time_to_next_line - accumulated_time
            fraction = internal_leg_time / leg_time
            line_position = calculate_fractional_distance_point_lat_lon(start, finish, fraction)
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

            text_position = extend_point_to_the_right(
                bearing,
                (tuple(reversed(minute_mark[0])), tuple(reversed(minute_mark[1]))),
                1852 * number_distance / 2,
            )
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
        logger.debug(line)
    return lines


first = True


class MyGoogleWTS(GoogleWTS):
    def get_image(self, tile):

        if self.cache_path is not None:
            filename = "_".join([str(i) for i in tile]) + ".npy"
            cached_file = self._cache_dir / filename
        else:
            cached_file = None

        if cached_file in self.cache:
            img = np.load(cached_file, allow_pickle=False)
        else:
            url = self._image_url(tile)
            try:
                response = requests.get(url, headers={"User-Agent": self.user_agent}, timeout=1)
                im_data = io.StringIO(response.content.decode("utf-8"))
                img = Image.open(im_data)

            except requests.RequestException:
                logger.exception("Failed fetching tile for url %s", url)
                img = Image.fromarray(np.full((256, 256, 3), (250, 250, 250), dtype=np.uint8))

            img = img.convert(self.desired_tile_form)
            if self.cache_path is not None:
                np.save(cached_file, img, allow_pickle=False)
                self.cache.add(cached_file)

        return img, self.tileextent(tile), "lower"


class UserUploadedMBTiles(GoogleWTS):
    def __init__(self, user_uploaded_map: UserUploadedMap, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mbtiles_file = user_uploaded_map.get_local_file_path()

    def _image_url(self, tile):
        return "something"

    def get_image(self, tile):
        global first
        x, y, z = tile
        y = (2**z) - y - 1
        try:
            with MBtiles(self.mbtiles_file) as src:
                # tiles = src.list_tiles()
                # for tile in tiles:
                #     if tile.z == z and first:
                #         print(tile)
                # print(f"Has tile: {src.has_tile(z, x, y)}")
                data = src.read_tile(z=z, x=x, y=y)
                try:
                    img = Image.open(BytesIO(data))
                except PIL.UnidentifiedImageError:
                    img = Image.fromarray(np.full((256, 256, 3), (250, 250, 250), dtype=np.uint8))
        except ValueError:
            img = Image.fromarray(np.full((256, 256, 3), (255, 255, 255), dtype=np.uint8))
        except Exception:
            logger.exception("bad ")
            raise

        img = img.convert(self.desired_tile_form)
        first = False
        return img, self.tileextent(tile), "lower"


class FlightContest(MyGoogleWTS):
    def _image_url(self, tile):
        x, y, z = tile
        y = (2**z) - y - 1
        return f"https://tiles.flightcontest.de/{z}/{x}/{y}.png"

    def get_image(self, tile):
        from urllib.request import urlopen, Request

        url = self._image_url(tile)
        try:
            request = Request(url, headers={"User-Agent": self.user_agent})
            fh = urlopen(request)
            im_data = six.BytesIO(fh.read())
            fh.close()
            img = Image.open(im_data)

        except Exception as err:
            print(err)
            img = Image.fromarray(np.full((256, 256, 3), (255, 255, 255), dtype=np.uint8))

        img = img.convert(self.desired_tile_form)
        return img, self.tileextent(tile), "lower"


class OpenAIP(MyGoogleWTS):
    def _image_url(self, tile):
        x, y, z = tile
        s = "1"
        ext = "png"
        return f"http://{s}.tile.maps.openaip.net/geowebcache/service/tms/1.0.0/openaip_basemap@EPSG%3A900913@png/{z}/{x}/{y}.{ext}"


class MapTilerOutdoor(MyGoogleWTS):
    def _image_url(self, tile):
        x, y, z = tile
        return f"https://api.maptiler.com/maps/outdoor/{z}/{x}/{y}.png?key=YxHsFU6aEqsEULL34uJT"


class CyclOSM(MyGoogleWTS):
    def _image_url(self, tile):
        x, y, z = tile
        return f"https://a.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png"


class LocalMapServer(MyGoogleWTS):
    def __init__(self, map_key: str, **kwargs):
        super().__init__(**kwargs)
        self.map_key = map_key
        self.format = get_map_details(self.map_key).get("format", "png")

    def _image_url(self, tile):
        x, y, z = tile
        return f"{MBTILES_SERVER_URL}/services/{self.map_key}/tiles/{z}/{x}/{y}.{self.format}"


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
        "1:{:,d} {:.2f} {} = {:.0f} cm".format(int(scale * 1000), bar_length, units, 10),
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
        "1:{:,d} {:.2f} {} = {:.0f} cm".format(int(scale * 1000), bar_length, units, 10),
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
    course_position = calculate_fractional_distance_point_lat_lon(left_of_leg_start, left_of_leg_finish, 0.5)
    course_text = "{:03.0f}".format(normalise_bearing(bearing))
    label = course_text + " " * (len(course_text) + 1)
    # Try to keep it out of the way of the next leg
    # bearing_difference_next = get_heading_difference(next_waypoint.bearing_from_previous, next_waypoint.bearing_next)
    # bearing_difference_previous = get_heading_difference(
    #     current_waypoint.bearing_from_previous, current_waypoint.bearing_next
    # )
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


PROHIBITED_COLOURS = {
    "prohibited": ("red", "darkred", 4),
    "penalty": ("orange", "darkorange", 4),
    "info": ("lightblue", "Lightskyblue", 10),
    "gate": ("blue", "darkblue", 4),
}


def plot_prohibited_polygon(
    target_projection, ax, polygon_path, fill_colour: str, line_colour: str, font_size: int, name
):
    line = []
    for element in polygon_path:
        line.append(target_projection.transform_point(*list(reversed(element)), ccrs.PlateCarree()))
    polygon = Polygon(line)
    centre = polygon.centroid
    ax.add_geometries(
        [polygon],
        crs=target_projection,
        facecolor=fill_colour,
        alpha=0.4,
        # linewidth=2,
        edgecolor=line_colour,
    )
    plt.text(centre.x, centre.y, name, {"fontsize": font_size}, horizontalalignment="center")


def plot_prohibited_zones(route: Route, target_projection, ax):
    for prohibited in route.prohibited_set.all():
        fill_colour, line_colour, font_size = PROHIBITED_COLOURS.get(prohibited.type, ("blue", "darkblue", 4))
        plot_prohibited_polygon(
            target_projection,
            ax,
            prohibited.path,
            fill_colour,
            line_colour,
            font_size,
            prohibited.name,
        )


def extend_point_to_the_right(
    track_bearing: float,
    line: Tuple[Tuple[float, float], Tuple[float, float]],
    distance: float,
) -> Tuple[float, float]:
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
    waypoint_name = "{}".format(waypoint.name)
    timing = ""
    if contestant is not None and annotations:
        waypoint_time = contestant.gate_times.get(waypoint.name)  # type: datetime.datetime
        if waypoint_time is not None:
            local_waypoint_time = waypoint_time.astimezone(route.navigationtask.contest.time_zone)
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
        name_position = []
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
            fontsize=12,
            rotation=rotation,
            # linespacing=2,
            family="monospace",
            clip_on=True,
        )
    waypoint_name = waypoint_name + " " * ((2 if not waypoints_only else 6) + len(waypoint_name))
    plt.text(
        name_position[1] if len(name_position) else waypoint.longitude,
        name_position[0] if len(name_position) else waypoint.latitude,
        waypoint_name,
        verticalalignment="center",
        color=colour,
        horizontalalignment="center",
        transform=ccrs.PlateCarree(),
        fontsize=10,
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
    minute_mark_line_width: float,
    colour: str,
    plot_center_line: bool,
):
    inner_track = []
    outer_track = []
    center_track = []
    for index, waypoint in enumerate(route.waypoints):
        ys, xs = np.array(waypoint.gate_line).T
        bearing = waypoint_bearing(waypoint, index)

        if waypoint.type not in (SECRETPOINT,):
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
        if waypoint.left_corridor_line is not None:
            inner_track.extend(waypoint.left_corridor_line)
            outer_track.extend(waypoint.right_corridor_line)
        else:
            inner_track.append(waypoint.gate_line[0])
            outer_track.append(waypoint.gate_line[1])
        center_track.append((waypoint.latitude, waypoint.longitude))
        if waypoint.type not in (SECRETPOINT,):
            plt.plot(xs, ys, transform=ccrs.PlateCarree(), color=colour, linewidth=line_width)
        if index < len(route.waypoints) - 1 and annotations and contestant is not None:
            plot_minute_marks(
                waypoint,
                contestant,
                route.waypoints,
                index,
                minute_mark_line_width,
                colour,
                mark_offset=2,
                line_width_nm=0.5,
                adaptive=True,
            )
            maybe_plot_leg_bearing_anr(waypoint, index, route.waypoints, contestant, 2, 12)
    if plot_center_line:
        path = np.array(center_track)
        ys, xs = path.T
        plt.plot(xs, ys, transform=ccrs.PlateCarree(), color=colour, linewidth=line_width / 2)
    path = np.array(inner_track)
    ys, xs = path.T
    plt.plot(xs, ys, transform=ccrs.PlateCarree(), color=colour, linewidth=line_width)
    path = np.array(outer_track)
    ys, xs = path.T
    plt.plot(xs, ys, transform=ccrs.PlateCarree(), color=colour, linewidth=line_width)
    return [path]


def maybe_plot_leg_bearing_anr(
    waypoint: Waypoint, index: int, track: List[Waypoint], contestant: Contestant, character_offset: int, font_size: int
):
    next_index = index + 1
    if next_index >= len(track):
        return
    if (
        track[next_index].type not in (UNKNOWN_LEG, DUMMY) and track[next_index].distance_previous / 1852 > 1
    ):  # Distance between waypoints must be more than 1 nautical miles
        plot_leg_bearing(
            waypoint,
            track[next_index],
            contestant.air_speed,
            contestant.wind_speed,
            contestant.wind_direction,
            character_offset,
            font_size,
        )


def maybe_plot_leg_bearing(
    waypoint: Waypoint, index: int, track: List[Waypoint], contestant: Contestant, character_offset: int, font_size: int
):
    if waypoint.type != SECRETPOINT:
        # Only plot bearing if there is a straight line between one not secret gate and the next
        next_index = index + 1
        accumulated_distance = 0
        while next_index < len(track):
            if (
                abs(
                    bearing_difference(
                        waypoint.bearing_next,
                        track[next_index].bearing_from_previous,
                    )
                )
                > 3
            ):
                break
            accumulated_distance += track[next_index].distance_previous
            if (
                track[next_index].type not in (SECRETPOINT, UNKNOWN_LEG, DUMMY) and accumulated_distance / 1852 > 1
            ):  # Distance between waypoints must be more than 1 nautical miles
                plot_leg_bearing(
                    waypoint,
                    track[next_index],
                    contestant.air_speed,
                    contestant.wind_speed,
                    contestant.wind_direction,
                    character_offset,
                    font_size,
                )
                break
            next_index += 1


def plot_minute_marks(
    waypoint: Waypoint,
    contestant: Contestant,
    track: List[Waypoint],
    index,
    line_width: float,
    colour: str,
    mark_offset=1,
    line_width_nm: float = 0.5,
    adaptive: bool = False,
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
    track_points = first_segments[len(first_segments) // 2 :] + last_segments[: (len(last_segments) // 2) + 1]
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
        end_offset=next_waypoint.width if adaptive else None,
    )
    for mark_line, text_position, timestamp in minute_lines:
        xs, ys = np.array(mark_line).T  # Already comes in the format lon, lat
        plt.plot(xs, ys, transform=ccrs.PlateCarree(), color=colour, linewidth=line_width)
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
    minute_mark_line_width: float,
    colour: str,
):
    tracks = [[]]
    previous_waypoint = None  # type: Optional[Waypoint]
    includes_unknown_legs = any(waypoint.type == "ul" for waypoint in route.waypoints)
    on_unknown_leg = False
    for index, waypoint in enumerate(route.waypoints):
        if index < len(route.waypoints) - 1:
            next_waypoint = route.waypoints[index + 1]
        else:
            next_waypoint = None
        if waypoint.type == "ul":
            on_unknown_leg = True
        if waypoint.type in (
            TURNPOINT,
            STARTINGPOINT,
            FINISHPOINT,
            INTERMEDIARY_STARTINGPOINT,
            INTERMEDIARY_FINISHPOINT,
        ):
            on_unknown_leg = False
        if previous_waypoint and previous_waypoint.type in (DUMMY, UNKNOWN_LEG) and waypoint.type != DUMMY:
            tracks.append([])
        if waypoint.type == INTERMEDIARY_STARTINGPOINT:
            tracks.append([])
        if waypoint.type in (
            TURNPOINT,
            STARTINGPOINT,
            FINISHPOINT,
            INTERMEDIARY_STARTINGPOINT,
            INTERMEDIARY_FINISHPOINT,
            SECRETPOINT,
            DUMMY,
            UNKNOWN_LEG,
        ):
            # Do not show unknown leg gates, these are to be considered secret unless followed by a dummy
            if waypoint.type == UNKNOWN_LEG and next_waypoint and next_waypoint.type != DUMMY:
                continue
            # Secret checkpoints on unknown legs should not be displayed
            if on_unknown_leg and waypoint.type == SECRETPOINT:
                continue
            tracks[-1].append(waypoint)
        previous_waypoint = waypoint
    paths = []
    for track in tracks:  # type: List[Waypoint]
        line = []
        for index, waypoint in enumerate(track):  # type: int, Waypoint
            if waypoint.type not in (SECRETPOINT, UNKNOWN_LEG, DUMMY):
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
                    plt.scatter(
                        waypoint.longitude,
                        waypoint.latitude,
                        transform=ccrs.PlateCarree(),
                        color=colour,
                        s=0.5,
                        edgecolor="none",
                    )
                    plt.plot(
                        waypoint.longitude,
                        waypoint.latitude,
                        transform=ccrs.PlateCarree(),
                        color=colour,
                        marker="o",
                        markersize=20,
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
                        maybe_plot_leg_bearing(waypoint, index, track, contestant, 4, 14)
                        if not includes_unknown_legs:
                            plot_minute_marks(
                                waypoint,
                                contestant,
                                track,
                                index,
                                minute_mark_line_width,
                                colour,
                            )

            if waypoint.is_procedure_turn and waypoint.type != UNKNOWN_LEG:
                line.extend(waypoint.procedure_turn_points)
            else:
                line.append((waypoint.latitude, waypoint.longitude))
        if len(line):
            path = np.array(line)
            paths.append(path)
            if not waypoints_only:
                ys, xs = path.T
                plt.plot(
                    xs,
                    ys,
                    transform=ccrs.PlateCarree(),
                    color=colour,
                    linewidth=line_width,
                )
    return paths


# def add_geotiff_background(path: str, ax):
#     import xarray as xr
#     from affine import Affine
#     da = xr.open_rasterio(path)
#     transform = Affine.from_gdal(
#         *da.attrs['transform'])  # this is important to retain the geographic attributes from the file
#     # Create meshgrid from geotiff
#     nx, ny = da.sizes['x'], da.sizes['y']
#     x, y = np.meshgrid(np.arange(nx), np.arange(ny)) * transform
def plot_editable_route(editable_route: EditableRoute) -> Optional[BytesIO]:
    plt.figure(figsize=(3, 3))
    imagery = OSM()
    ax = plt.axes(projection=imagery.crs)
    editable_track = editable_route.get_feature_type("track")
    if editable_track is not None:
        tracks = [[]]
        coordinates = editable_route.get_feature_coordinates(editable_track)
        track_points = editable_track["track_points"]
        for index, (latitude, longitude) in enumerate(coordinates):
            item = track_points[index]
            tracks[-1].append((latitude, longitude))
            plt.text(
                longitude,
                latitude,
                " " + item["name"],
                verticalalignment="center",
                color="red",
                horizontalalignment="left",
                transform=ccrs.PlateCarree(),
                fontsize=8,
                family="monospace",
                clip_on=True,
            )
        for track in tracks:
            path = np.array(track)
            ys, xs = path.T
            plt.plot(xs, ys, transform=ccrs.PlateCarree(), color="blue", linewidth=1)
    takeoff_gates = editable_route.get_features_type("to")
    for takeoff_gate in takeoff_gates:
        takeoff_gate_line = editable_route.get_feature_coordinates(takeoff_gate)
        path = np.array(takeoff_gate_line)
        ys, xs = path.T
        plt.plot(xs, ys, transform=ccrs.PlateCarree(), color="green", linewidth=1)
    landing_gates = editable_route.get_features_type("ldg")
    for landing_gate in landing_gates:
        landing_gate_line = editable_route.get_feature_coordinates(landing_gate)
        path = np.array(landing_gate_line)
        ys, xs = path.T
        plt.plot(xs, ys, transform=ccrs.PlateCarree(), color="red", linewidth=1)
    for zone_type in ("info", "penalty", "prohibited", "gate"):
        for feature in editable_route.get_features_type(zone_type):
            fill_colour, line_colour, font_size = PROHIBITED_COLOURS.get(zone_type, ("blue", "darkblue", 4))
            plot_prohibited_polygon(
                imagery.crs,
                ax,
                editable_route.get_feature_coordinates(feature, flip=True),
                fill_colour,
                line_colour,
                font_size,
                feature["name"],
            )
    ax.add_image(imagery, 11)
    figdata = BytesIO()
    plt.savefig(figdata, format="png", dpi=100, transparent=True)  # , bbox_inches="tight", pad_inches=margin_inches/2)
    figdata.seek(0)
    return figdata


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
    user_map_source: UserUploadedMap = None,
    line_width: float = 0.5,
    minute_mark_line_width: float = 0.5,
    colour: str = "#0000ff",
    include_meridians_and_parallels_lines: bool = True,
    margins_mm: float = 0,
):
    route = task.route
    attribution = ""
    if user_map_source:
        imagery = UserUploadedMBTiles(user_map_source)
        attribution = user_map_source.attribution
    else:
        if map_source == "osm":
            imagery = OSM(user_agent="airsports.no, support@airsports.no")  # Does not like zoom level greater than 12
            attribution = "openstreetmap.org"
        elif map_source == "fc":
            imagery = FlightContest(desired_tile_form="RGBA")
            attribution = "FlightContest"
        elif map_source == "mto":
            imagery = MapTilerOutdoor(desired_tile_form="RGBA")
            attribution = "maptiler.com"
        elif map_source == "cyclosm":
            imagery = OSM(user_agent="airsports.no, support@airsports.no")  # Does not like zoom level greater than 12
            attribution = "openstreetmap.org"
            # imagery = CyclOSM(desired_tile_form="RGBA", user_agent="airsports.no, support@airsports.no")
            # attribution = "openstreetmap.org CycleOSM"
        else:
            imagery = LocalMapServer(map_source, desired_tile_form="RGBA")
            attribution = MAP_ATTRIBUTIONS.get(map_source, "Missing")
    if map_size == A3:
        if zoom_level is None:
            zoom_level = 12
        if landscape:
            figure_width = A3_HEIGHT
            figure_height = A3_WIDTH
        else:
            figure_width = A3_WIDTH
            figure_height = A3_HEIGHT
    else:
        if zoom_level is None:
            zoom_level = 11
        if landscape:
            figure_width = A4_HEIGHT
            figure_height = A4_WIDTH
        else:
            figure_width = A4_WIDTH
            figure_height = A4_HEIGHT
    figure_width -= 0.2 * margins_mm
    figure_height -= 0.2 * margins_mm
    fig = plt.figure(figsize=(cm2inch(figure_width), cm2inch(figure_height)))
    ax = fig.add_axes([0, 0, 1, 1], projection=imagery.crs)
    # ax.background_patch.set_fill(False)
    # ax.background_patch.set_facecolor((250 / 255, 250 / 255, 250 / 255))
    # print(f"Figure projection: {imagery.crs}")
    ax.add_image(imagery, zoom_level)  # , interpolation='spline36', zorder=10)
    # ax.add_image(OpenAIP(), zoom_level, interpolation='spline36', alpha=0.6, zorder=20)
    ax.set_aspect("auto")
    if PRECISION in task.scorecard.task_type or POKER in task.scorecard.task_type:
        paths = plot_precision_track(
            route,
            contestant,
            waypoints_only,
            annotations,
            line_width,
            minute_mark_line_width,
            colour,
        )
    elif ANR_CORRIDOR in task.scorecard.task_type:
        paths = plot_anr_corridor_track(
            route,
            contestant,
            annotations,
            line_width,
            minute_mark_line_width,
            colour,
            False,
        )
    elif AIRSPORTS in task.scorecard.task_type or AIRSPORT_CHALLENGE in task.scorecard.task_type:
        paths = plot_anr_corridor_track(
            route,
            contestant,
            annotations,
            line_width,
            minute_mark_line_width,
            colour,
            not waypoints_only,
        )
    else:
        paths = []
    plot_prohibited_zones(route, imagery.crs, ax)
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

    # print(f"Figure size (cm): ({figure_width}, {figure_height})")
    minimum_latitude, maximum_latitude, minimum_longitude, maximum_longitude = route.get_extent()
    # print(f"minimum: {minimum_latitude}, {minimum_longitude}")
    # print(f"maximum: {maximum_latitude}, {maximum_longitude}")
    proj_pc = ccrs.PlateCarree()
    x0_lon, x1_lon, y0_lat, y1_lat = ax.get_extent(proj_pc)

    # Projection in metres
    utm = utm_from_lat_lon((y0_lat + y1_lat) / 2, (x0_lon + x1_lon) / 2)
    if scale == 0:
        # Zoom to fit
        map_margin = 6000  # metres

        bottom_left = utm.transform_point(minimum_longitude, minimum_latitude, proj_pc)
        # top_left = utm.transform_point(minimum_longitude, maximum_latitude, proj)
        # bottom_right = utm.transform_point(maximum_longitude, minimum_latitude, proj)
        top_right = utm.transform_point(maximum_longitude, maximum_latitude, proj_pc)
        # Widen the image a bit
        scaled_top = top_right[1] + map_margin
        scaled_bottom = bottom_left[1] - map_margin
        logger.info(f"scaled_the_top: {scaled_top}, scaled_bottom: {scaled_bottom}")
        scaled_left = bottom_left[0] - map_margin
        scaled_right = top_right[0] + map_margin
        desired_vertical_scale = (scaled_top - scaled_bottom) / figure_height
        desired_horizontal_scale = (scaled_right - scaled_left) / figure_width
        if desired_horizontal_scale > desired_vertical_scale:
            logger.info("Scale is controlled by horizontal")
            horizontal_metres = scaled_right - scaled_left
            horizontal_scale = horizontal_metres / figure_width  # m per cm
            y_centre = (bottom_left[1] + top_right[1]) / 2
            # Change vertical scale to match
            vertical_metres = horizontal_scale * figure_height
            y0 = y_centre - vertical_metres / 2
            y1 = y_centre + vertical_metres / 2
            scale = horizontal_metres / (10 * figure_width)
            x0, y0 = scaled_left, y0
            x1, y1 = scaled_right, y1
        else:
            logger.info("Scale is controlled by vertical")
            vertical_metres = scaled_top - scaled_bottom
            vertical_scale = vertical_metres / figure_height  # m per cm
            x_centre = (bottom_left[0] + top_right[0]) / 2
            # Change horizontal scale to match
            horizontal_metres = vertical_scale * figure_width
            x0 = x_centre - horizontal_metres / 2
            x1 = x_centre + horizontal_metres / 2
            scale = vertical_metres / (10 * figure_height)
            x0, y0 = x0, scaled_bottom
            x1, y1 = x1, scaled_top
        extent = [x0, x1, y0, y1]
    else:
        centre_longitude = minimum_longitude + (maximum_longitude - minimum_longitude) / 2
        centre_latitude = minimum_latitude + (maximum_latitude - minimum_latitude) / 2
        centre_x, centre_y = utm.transform_point(centre_longitude, centre_latitude, proj_pc)
        width_metres = (scale * 10) * figure_width
        height_metres = (scale * 10) * figure_height
        lower_left = (
            centre_x - width_metres / 2,
            centre_y - height_metres / 2,
        )
        upper_right = (
            centre_x + width_metres / 2,
            centre_y + height_metres / 2,
        )
        extent = [lower_left[0], upper_right[0], lower_left[1], upper_right[1]]
    ax.set_extent(extent, crs=utm)
    # scale_bar(ax, ccrs.PlateCarree(), 5, units="NM", m_per_unit=1852, scale=scale)
    scale_bar_y(ax, ccrs.PlateCarree(), 5, units="NM", m_per_unit=1852, scale=scale)
    # ax.autoscale(False)
    fig.patch.set_visible(False)
    # lat lon lines
    extent = ax.get_extent(proj_pc)
    if include_meridians_and_parallels_lines:
        # ax.set_xticks(np.arange(np.floor(extent[0]), np.ceil(extent[1]), 0.1), crs=ccrs.PlateCarree())
        gl = ax.gridlines(
            draw_labels=True,
            xpadding=-10,
            ypadding=-10,
            x_inline=False,
            y_inline=False,
            dms=True,
            crs=ccrs.PlateCarree(),
            color="grey",
            linewidth=1,
            clip_on=True,
        )
        gl.xlocator = mticker.FixedLocator(np.arange(np.floor(extent[0]), np.ceil(extent[1]), 1 / 6))
        # gl.right_labels=True
        # gl.left_labels=True
        # gl.xformatter = LONGITUDE_FORMATTER
        # gl.xlabel_style = {"size": 15, "color": "grey"}
        # gl.xpadding = 10
        gl.ylocator = mticker.FixedLocator(np.arange(np.floor(extent[2]), np.ceil(extent[3]), 1 / 6))
        # gl.bottom_labels=True
        # gl.top_labels=True
        # gl.yformatter = LATITUDE_FORMATTER
        # gl.ylabel_style = {"size": 15, "color": "grey"}
        # gl.ypadding = 10
        # for artist in gl.bottom_label_artists:
        #     artist.set_visible(True)
        # longitude = np.ceil(extent[0])
        # while longitude < extent[1]:
        #     plt.plot(
        #         (longitude, longitude),
        #         (extent[2], extent[3]),
        #         transform=ccrs.PlateCarree(),
        #         color="black",
        #         linewidth=0.5,
        #     )
        #     longitude += 1
        # latitude = np.ceil(extent[2])
        # while latitude < extent[3]:
        #     plt.plot(
        #         (extent[0], extent[1]),
        #         (latitude, latitude),
        #         transform=ccrs.PlateCarree(),
        #         color="black",
        #         linewidth=0.5,
        #     )
        #     latitude += 1
    plt.text(0, 0, " " + attribution, ha="left", va="bottom", transform=ax.transAxes)
    # fig.subplots_adjust(bottom=0)
    # fig.subplots_adjust(top=1)
    # fig.subplots_adjust(right=1)
    # fig.subplots_adjust(left=0)
    fig.tight_layout(pad=0)
    # plt.savefig("map.png", dpi=dpi)

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
        figdata,
        format="png",
        dpi=dpi,
        transparent=True,
    )  # , bbox_inches="tight", pad_inches=margin_inches/2)
    figdata.seek(0)
    if landscape:
        image = Image.open(figdata)
        rotated = image.rotate(90, expand=1)
        rotated_data = BytesIO()
        rotated.save(rotated_data, format="PNG")
        rotated_data.seek(0)
        figdata = rotated_data
    plt.close()
    return figdata


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
    plt.plot(xs, ys, transform=ccrs.PlateCarree(), color="blue", linewidth=LINEWIDTH * 2)
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
