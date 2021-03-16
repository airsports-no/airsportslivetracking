from io import BytesIO

import pytz
import datetime
import os
import sys
from typing import Optional, Tuple, List

from cartopy.io.img_tiles import OSM, GoogleWTS
import matplotlib.pyplot as plt
import numpy as np
import cartopy.crs as ccrs
from matplotlib import patheffects
from matplotlib.transforms import Bbox
from shapely.geometry import Polygon

from display.coordinate_utilities import calculate_distance_lat_lon, calculate_bearing, \
    calculate_fractional_distance_point_lat_lon, get_heading_difference, project_position_lat_lon, \
    create_perpendicular_line_at_end_lonlat
from display.wind_utilities import calculate_ground_speed_combined

if __name__ == "__main__":
    sys.path.append("../")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()

from display.models import Route, Contestant, NavigationTask
from display.waypoint import Waypoint

LINEWIDTH = 0.5


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
        lines.append((create_perpendicular_line_at_end_lonlat(*reversed(start), *reversed(line_position),
                                                              line_width_nm * 1852), line_position,
                      gate_start_time + datetime.timedelta(seconds=time_to_next_line)))
        time_to_next_line += resolution_seconds
    return lines


A4 = "A4"
A3 = "A3"

OSM_MAP = 0
N250_MAP = 1


class LocalImages(GoogleWTS):
    def _image_url(self, tile):
        x, y, z = tile
        return "file:///maptiles/Norway_N250/{}/{}/{}.png".format(z, x, y)

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


def utm_from_lon(lon):
    """
    utm_from_lon - UTM zone for a longitude
    Not right for some polar regions (Norway, Svalbard, Antartica)
    :param float lon: longitude
    :return: UTM zone number
    :rtype: int
    """
    return np.floor((lon + 180) / 6) + 1


def scale_bar(ax, proj, length, location=(0.5, 0.05), linewidth=3,
              units='km', m_per_unit=1000, scale=0):
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
    utm = ccrs.UTM(utm_from_lon((x0 + x1) / 2))
    # Get the extent of the plotted area in coordinates in metres
    x0, x1, y0, y1 = ax.get_extent(utm)
    # Turn the specified scalebar location into coordinates in metres
    sbcx, sbcy = x0 + (x1 - x0) * location[0], y0 + (y1 - y0) * location[1]
    # Generate the x coordinate for the ends of the scalebar
    bar_xs = [sbcx - length * m_per_unit / 2, sbcx + length * m_per_unit / 2]
    # buffer for scalebar
    buffer = [patheffects.withStroke(linewidth=5, foreground="w")]
    # Plot the scalebar with buffer
    x0, y = proj.transform_point(bar_xs[0], sbcy, utm)
    x1, _ = proj.transform_point(bar_xs[1], sbcy, utm)
    xc, yc = proj.transform_point(sbcx, sbcy + 200, utm)
    ax.plot([x0, x1], [y, y], transform=proj, color='k',
            linewidth=linewidth, path_effects=buffer)
    # buffer for text
    buffer = [patheffects.withStroke(linewidth=3, foreground="w")]
    # Plot the scalebar label
    ruler_scale = 100 * 1852 * length / (scale * 1000)
    t0 = ax.text(xc, yc, "1:{:,d} {} {} = {:.2f} cm".format(int(scale * 1000), str(length), units, ruler_scale),
                 transform=proj,
                 horizontalalignment='center', verticalalignment='bottom',
                 path_effects=buffer, zorder=2)
    # left = x0 + (x1 - x0) * 0.05
    # Plot the N arrow
    # t1 = ax.text(left, sbcy, u'\u25B2\nN', transform=utm,
    #              horizontalalignment='center', verticalalignment='bottom',
    #              path_effects=buffer, zorder=2)

    # Plot the scalebar without buffer, in case covered by text buffer
    ax.plot([x0, x1], [y, y], transform=proj, color='k',
            linewidth=linewidth, zorder=3)


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


def plot_leg_bearing(current_waypoint, next_waypoint, character_offset: int = 4, fontsize: int = 14):
    bearing = current_waypoint.bearing_next
    bearing_difference_next = get_heading_difference(next_waypoint.bearing_from_previous,
                                                     next_waypoint.bearing_next)
    bearing_difference_previous = get_heading_difference(current_waypoint.bearing_from_previous,
                                                         current_waypoint.bearing_next)
    course_position = get_course_position((current_waypoint.latitude, current_waypoint.longitude),
                                          (next_waypoint.latitude,
                                           next_waypoint.longitude),
                                          True, 3)
    course_text = "{:03.0f}".format(current_waypoint.bearing_next)
    # Try to keep it out of the way of the next leg
    if bearing_difference_next > 60 or bearing_difference_previous > 60:  # leftSide
        label = "" + course_text + " " * len(course_text) + " " * character_offset
    else:  # Right-sided is preferred
        label = "" + " " * len(course_text) + " " * character_offset + course_text
    plt.text(course_position[1], course_position[0], label,
             verticalalignment="center", color="red",
             horizontalalignment="center", transform=ccrs.PlateCarree(), fontsize=fontsize,
             rotation=-bearing,
             linespacing=2, family="monospace")


def waypoint_bearing(waypoint, index) -> float:
    bearing = waypoint.bearing_from_previous
    if index == 0:
        bearing = waypoint.bearing_next
    return bearing


def plot_prohibited_zones(route: Route, target_projection, ax):
    for prohibited in route.prohibited_set.all():
        line = []
        for element in prohibited.path:
            line.append(target_projection.transform_point(*list(reversed(element)), ccrs.PlateCarree()))
        polygon = Polygon(line)
        centre = polygon.centroid
        ax.add_geometries([polygon], crs=target_projection, facecolor="red", alpha=0.4)
        plt.text(centre.x, centre.y, prohibited.name, horizontalalignment="center")


def plot_waypoint_name(route: Route, waypoint: Waypoint, bearing: float, annotations: bool, waypoints_only: bool,
                       contestant: Optional[Contestant], character_padding: int = 4):
    text = "{}".format(waypoint.name)
    if contestant is not None and annotations:
        waypoint_time = contestant.gate_times.get(waypoint.name)  # type: datetime.datetime
        if waypoint_time is not None:
            local_waypoint_time = waypoint_time.astimezone(route.navigationtask.contest.time_zone)
            text += " {}".format(local_waypoint_time.strftime("%H:%M:%S"))
    bearing_difference = get_heading_difference(waypoint.bearing_from_previous, waypoint.bearing_next)
    if bearing_difference > 0:
        text = "\n" + text + " " * len(text) + " " * character_padding  # Padding to get things aligned correctly
    else:
        text = "\n" + " " * (len(text) + character_padding) + text  # Padding to get things aligned correctly
    if waypoints_only:
        bearing = 0
    plt.text(waypoint.longitude, waypoint.latitude, text, verticalalignment="center", color="blue",
             horizontalalignment="center", transform=ccrs.PlateCarree(), fontsize=8, rotation=-bearing,
             linespacing=2, family="monospace", clip_on=True)


def plot_anr_corridor_track(route: Route, contestant: Optional[Contestant], annotations):
    inner_track = []
    outer_track = []
    for index, waypoint in enumerate(route.waypoints):
        ys, xs = np.array(waypoint.gate_line).T
        bearing = waypoint_bearing(waypoint, index)

        if waypoint.type in ("sp", "fp"):
            plot_waypoint_name(route, waypoint, bearing, annotations, False, contestant, character_padding=5)
        if route.rounded_corners and waypoint.left_corridor_line is not None:
            inner_track.extend(waypoint.left_corridor_line)
            outer_track.extend(waypoint.right_corridor_line)
        else:
            plt.plot(xs, ys, transform=ccrs.PlateCarree(), color="blue", linewidth=LINEWIDTH)
            inner_track.append(waypoint.gate_line[0])
            outer_track.append(waypoint.gate_line[1])
        if index < len(route.waypoints) - 1 and annotations and contestant is not None:
            plot_minute_marks(waypoint, contestant, route.waypoints, index, mark_offset=4,
                              line_width_nm=contestant.navigation_task.scorecard.get_corridor_width(contestant) * 2)
            plot_leg_bearing(waypoint, route.waypoints[index + 1], 2, 10)
        print(inner_track)
    path = np.array(inner_track)
    ys, xs = path.T
    plt.plot(xs, ys, transform=ccrs.PlateCarree(), color="blue", linewidth=LINEWIDTH)
    path = np.array(outer_track)
    ys, xs = path.T
    plt.plot(xs, ys, transform=ccrs.PlateCarree(), color="blue", linewidth=LINEWIDTH)
    return path


def plot_minute_marks(waypoint: Waypoint, contestant: Contestant, track, index, mark_offset=1,
                      line_width_nm: float = 0.5):
    gate_start_time = contestant.gate_times.get(waypoint.name)
    if waypoint.is_procedure_turn:
        gate_start_time += datetime.timedelta(minutes=1)
    minute_lines = create_minute_lines((waypoint.latitude, waypoint.longitude),
                                       (track[index + 1].latitude, track[index + 1].longitude),
                                       contestant.air_speed, contestant.wind_speed,
                                       contestant.wind_direction,
                                       gate_start_time,
                                       contestant.gate_times.get(track[0].name), line_width_nm=line_width_nm)
    for mark_line, line_position, timestamp in minute_lines:
        xs, ys = np.array(mark_line).T  # Already comes in the format lon, lat
        plt.plot(xs, ys, transform=ccrs.PlateCarree(), color="blue", linewidth=LINEWIDTH)
        time_format = "%M"
        if timestamp.second != 0:
            time_format = "%M:%S"
        time_string = timestamp.strftime(time_format)
        text = "\n" + " " * mark_offset + " " * len(time_string) + time_string
        plt.text(line_position[1], line_position[0], text, verticalalignment="center",
                 color="blue",
                 horizontalalignment="center", transform=ccrs.PlateCarree(), fontsize=8,
                 rotation=-waypoint.bearing_next,
                 linespacing=2, family="monospace")


def plot_precision_track(route: Route, contestant: Optional[Contestant], waypoints_only: bool, annotations: bool):
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
                    plt.plot(xs, ys, transform=ccrs.PlateCarree(), color="blue", linewidth=LINEWIDTH)
                else:
                    plt.plot(waypoint.longitude, waypoint.latitude, transform=ccrs.PlateCarree(), color="blue",
                             marker="o", markersize=8, fillstyle="none")
                plot_waypoint_name(route, waypoint, bearing, annotations, waypoints_only, contestant)
                if contestant is not None:
                    if index < len(track) - 1:
                        if annotations:
                            plot_leg_bearing(waypoint, track[index + 1])
                            plot_minute_marks(waypoint, contestant, track, index)

            if waypoint.is_procedure_turn:
                line.extend(waypoint.procedure_turn_points)
            else:
                line.append((waypoint.latitude, waypoint.longitude))
        path = np.array(line)
        if not waypoints_only:
            ys, xs = path.T
            plt.plot(xs, ys, transform=ccrs.PlateCarree(), color="blue", linewidth=LINEWIDTH)
        return path


def plot_route(task: NavigationTask, map_size: str, zoom_level: Optional[int] = None, landscape: bool = True,
               contestant: Optional[Contestant] = None,
               waypoints_only: bool = False, annotations: bool = True, scale: int = 200, dpi: int = 300,
               map_source: int = OSM):
    route = task.route
    if map_source == OSM_MAP:
        imagery = OSM()
    elif map_source == N250_MAP:
        imagery = LocalImages()
    else:
        return
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
    if "precision" in task.scorecard.task_type:
        path = plot_precision_track(route, contestant, waypoints_only, annotations)
    elif "anr_corridor" in task.scorecard.task_type:
        path = plot_anr_corridor_track(route, contestant, annotations)
    else:
        path = []
    plot_prohibited_zones(route, imagery.crs, ax)
    ax.gridlines(draw_labels=False, dms=True)
    buffer = [patheffects.withStroke(linewidth=3, foreground="w")]
    if contestant is not None:
        plt.title("Track: '{}' - Contestant: {} - Wind: {:03.0f}/{:02.0f}".format(route.name, contestant,
                                                                                  contestant.wind_direction,
                                                                                  contestant.wind_speed), y=1, pad=-20,
                  color="black", fontsize=10, path_effects=buffer)
    else:
        plt.title("Track: {}".format(route.navigationtask.name), y=1, pad=-20, path_effects=buffer)

    # plt.tight_layout()
    fig = plt.gcf()
    figure_size = fig.get_size_inches()
    figure_width = inch2cm(figure_size[0])
    figure_height = inch2cm(figure_size[1])

    minimum_latitude = np.min(path[:, 0])
    minimum_longitude = np.min(path[:, 1])
    maximum_latitude = np.max(path[:, 0])
    maximum_longitude = np.max(path[:, 1])
    if scale == 0:
        # Zoom to fit
        map_margin = 6000  # metres
        longitude_scale = calculate_distance_lat_lon((minimum_latitude, minimum_longitude),
                                                     (minimum_latitude, minimum_longitude + 1))
        latitude_scale = calculate_distance_lat_lon((minimum_latitude, minimum_longitude),
                                                    (minimum_latitude + 1, minimum_longitude))

        x0 = minimum_longitude - map_margin / longitude_scale
        x1 = maximum_longitude + map_margin / longitude_scale
        x_centre = x0 + (x1 - x0) / 2
        y0 = minimum_latitude - map_margin / latitude_scale
        y1 = maximum_latitude + map_margin / latitude_scale
        y_centre = y0 + (y1 - y0) / 2
        horizontal_metres = (x1 - x0) * longitude_scale
        vertical_metres = (y1 - y0) * latitude_scale
        print(f'horizontal_metres: {horizontal_metres}')
        print(f'vertical_metres: {vertical_metres}')
        vertical_scale = vertical_metres / figure_height  # m per cm
        horizontal_scale = horizontal_metres / figure_width  # m per cm
        print(f'horizontal_scale: {horizontal_scale}')
        print(f'vertical_scale: {vertical_scale}')

        if vertical_scale < horizontal_scale:
            # Increase vertical scale to match
            vertical_metres = horizontal_scale * figure_height
            print(f'new_vertical_metres: {vertical_metres}')

            vertical_offset = vertical_metres / (2 * latitude_scale)
            print(f'vertical_offset: {vertical_offset}')

            y0 = y_centre - vertical_offset
            y1 = y_centre + vertical_offset
            scale = horizontal_metres / (10 * figure_width)
        else:
            horizontal_metres = vertical_scale * figure_width
            print(f'new_horizontal_metres: {horizontal_metres}')
            horizontal_offset = horizontal_metres / (2 * longitude_scale)
            print(f'horizontal_offset: {horizontal_offset}')

            x0 = x_centre - horizontal_offset
            x1 = x_centre + horizontal_offset
            scale = vertical_metres / (10 * figure_height)
        extent = [x0, x1, y0, y1]



    else:
        centre_longitude = minimum_longitude + (maximum_longitude - minimum_longitude) / 2
        centre_latitude = minimum_latitude + (maximum_latitude - minimum_latitude) / 2
        print("Figure width: {}".format(figure_width))
        print("Figure height: {}".format(figure_height))
        # bbox = ax.get_tightbbox(fig.canvas.get_renderer()).transformed(fig.dpi_scale_trans.inverted())
        # bbox = ax.get_window_extent().transformed(fig.dpi_scale_trans.inverted())
        # width = inch2cm(bbox.width)
        # height = inch2cm(bbox.height)
        # print("Axis width: {}".format(width))
        # print("Axis height: {}".format(height))
        width_metres = (scale * 10) * figure_width
        height_metres = (scale * 10) * figure_height
        print("Width: {} km".format(width_metres / 1000))
        print("Height {} km".format(height_metres / 1000))
        # To scale
        extent = calculate_extent(width_metres, height_metres, (centre_latitude, centre_longitude))
    print(extent)
    ax.set_extent(extent)
    # plt.tight_layout()
    scale_bar(ax, ccrs.Mercator(), 5, units="NM", m_per_unit=1852, scale=scale)
    # plt.tight_layout()
    ax.autoscale(False)
    fig.patch.set_visible(False)
    # lat lon lines
    longitude = np.ceil(extent[0])
    while longitude < extent[1]:
        plt.plot((longitude, longitude), (extent[2], extent[3]), transform=ccrs.PlateCarree(), color="black",
                 linewidth=0.5)
        longitude += 1
    latitude = np.ceil(extent[2])
    while latitude < extent[3]:
        plt.plot((extent[0], extent[1]), (latitude, latitude), transform=ccrs.PlateCarree(), color="black",
                 linewidth=0.5)
        latitude += 1
    # plt.savefig("map.png", dpi=600)
    figdata = BytesIO()
    plt.savefig(figdata, format='png', dpi=dpi, bbox_inches="tight", pad_inches=0)
    plt.close()
    figdata.seek(0)
    return figdata


def get_basic_track(positions: List[Tuple[float, float]]):
    """

    :param positions: List of (latitude, longitude) pairs
    :return:
    """
    imagery = OSM()
    ax = plt.axes(projection=imagery.crs)
    ax.add_image(imagery, 13)
    ax.set_aspect("auto")
    ys, xs = np.array(positions).T
    plt.plot(xs, ys, transform=ccrs.PlateCarree(), color="blue", linewidth=LINEWIDTH * 2)
    index = 1
    for latitude, longitude in positions[1:-1]:
        plt.text(longitude, latitude, f"TP {index}", verticalalignment="center", color="blue",
                 horizontalalignment="center", transform=ccrs.PlateCarree(), fontsize=6)
        index += 1
    plt.text(positions[0][1], positions[0][0], f"SP", verticalalignment="center", color="blue",
             horizontalalignment="center", transform=ccrs.PlateCarree(), fontsize=6)
    plt.text(positions[-1][1], positions[-1][0], f"FP", verticalalignment="center", color="blue",
             horizontalalignment="center", transform=ccrs.PlateCarree(), fontsize=6)
    figdata = BytesIO()
    plt.savefig(figdata, format='png', dpi=100, bbox_inches="tight", pad_inches=0)
    plt.close()
    figdata.seek(0)
    return figdata

# if __name__ == "__main__":
#     task = NavigationTask.objects.get(pk=76)
#     contestant = Contestant.objects.get(pk=1803)
#     plot_route(task, contestant=contestant)
