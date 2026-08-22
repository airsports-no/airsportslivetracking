import datetime
import json
import logging
import os.path
import random
import re
import urllib
import urllib.request
from io import BytesIO
from tempfile import NamedTemporaryFile
from types import SimpleNamespace
from typing import List, Literal, Optional, Tuple

import matplotlib

matplotlib.use("Agg")
import cartopy.crs as ccrs
import matplotlib.pyplot as plt
import typst
from cartopy import geodesic
from cartopy.io.img_tiles import GoogleTiles
from django.core.files.storage import default_storage
from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import Polygon

from display.flight_order_and_maps.effective_route_rendering import get_effective_route_waypoints
from display.flight_order_and_maps.map_constants import A3, LANDSCAPE
from display.flight_order_and_maps.map_plotter import plot_route
from display.flight_order_and_maps.map_plotter_shared_utilities import qr_code_image
from display.models import Contestant
from display.models.flight_order_configuration import FlightOrderConfiguration
from display.models.route import Photo
from display.utilities.calculate_gate_times import PROCEDURE_TURN_DURATION
from display.utilities.coordinate_utilities import normalise_bearing, utm_from_lat_lon
from display.utilities.gate_definitions import DUMMY, SECRETPOINT, UNKNOWN_LEG
from display.utilities.navigation_task_type_definitions import ANR_CORRIDOR
from display.utilities.wind_utilities import calculate_ground_speed, calculate_wind_correction_angle
from display.waypoint import Waypoint
from live_tracking_map.settings import MEDIA_ROOT_URL

logger = logging.getLogger(__name__)

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _typst_string(value) -> str:
    """Render a Python value as a literal Typst string expression.

    Values inserted this way are never parsed as Typst markup, so this is the
    only safe way to embed contestant/team/rules text (which may contain
    "#", "*", "[", "]", etc.) into a generated .typ document.
    """
    text = _CONTROL_CHARACTERS.sub("", str(value))
    return json.dumps(text, ensure_ascii=False)


def _flow_text(text: str) -> str:
    """Collapses single newlines into spaces (as LaTeX's normal paragraph fill
    did) while keeping blank-line paragraph breaks, so free-form rule text
    doesn't hard-wrap at each source line."""
    paragraphs = re.split(r"\n\s*\n", text.strip())
    return "\n\n".join(" ".join(p.split("\n")).strip() for p in paragraphs)


def build_flight_order_map_plot_kwargs(
    navigation_task, flight_order_configuration: FlightOrderConfiguration, contestant=None
) -> dict:
    return {
        "zoom_level": flight_order_configuration.map_zoom_level,
        "landscape": flight_order_configuration.map_orientation == LANDSCAPE,
        "contestant": contestant,
        "include_contestant_declarations": bool(flight_order_configuration.map_include_contestant_declarations),
        "annotations": flight_order_configuration.map_include_annotations,
        "waypoints_only": not flight_order_configuration.map_plot_track_between_waypoints,
        "dpi": flight_order_configuration.map_dpi,
        "scale": flight_order_configuration.map_scale,
        "map_source": flight_order_configuration.map_source,
        "include_openaip_overlay": flight_order_configuration.map_include_openaip_overlay,
        "line_width": flight_order_configuration.map_line_width,
        "minute_mark_line_width": flight_order_configuration.map_minute_mark_line_width,
        "colour": flight_order_configuration.map_line_colour,
        "include_meridians_and_parallels_lines": flight_order_configuration.map_include_meridians_and_parallels_lines,
        "margins_mm": 10,
    }


def get_flight_order_visual_waypoints(contestant: Contestant, include_contestant_declarations: bool) -> list[Waypoint]:
    effective_waypoints = get_effective_route_waypoints(
        contestant.navigation_task,
        contestant=contestant,
        include_contestant_declarations=include_contestant_declarations,
    )
    waypoints = [waypoint for waypoint in effective_waypoints if waypoint.type != "dummy"]
    payload = getattr(getattr(contestant, "contestanttaskconfiguration", None), "compiled_effective_route_payload", {}) or {}
    if contestant.navigation_task.task_subtype == "unknown_legs":
        actual_route_names = {
            item.get("name") for item in (payload.get("actual_route", {}) or {}).get("waypoints", []) if item.get("name")
        }
        if actual_route_names:
            waypoints = [waypoint for waypoint in waypoints if waypoint.name in actual_route_names]
    return waypoints


def _build_decoy_photo_waypoints(navigation_task) -> List[Waypoint]:
    """Decoy photos (2.A5) have no real trigger waypoint - build a synthetic
    one from the organizer-declared location/course so they can be rendered
    and shuffled in among the genuine unknown-leg photos via the same
    waypoint-based image pipeline.
    """
    from display.utilities.route_building_utilities import build_waypoint

    decoy_waypoints = []
    for photo in Photo.objects.filter(route=navigation_task.route, is_decoy=True):
        waypoint = build_waypoint(photo.name, photo.latitude, photo.longitude, "tp", 0.001, False, True)
        course = photo.decoy_course or 0
        # Set both: rendering picks bearing_next or bearing_from_previous
        # depending on the decoy's (randomised) position in the list.
        waypoint.bearing_next = course
        waypoint.bearing_from_previous = course
        decoy_waypoints.append(waypoint)
    return decoy_waypoints


def generate_turning_point_image(
    waypoints: List[Waypoint], index, meters_across: float, zoom_level: int, is_unknown_leg: bool = False
):
    """The parameter waypoints must be the full list of waypoints, otherwise the the plotted track will be wrong."""
    waypoint = waypoints[index]
    imagery = GoogleTiles(style="satellite")
    plt.figure(figsize=(10, 10))
    ax = plt.axes(projection=imagery.crs)
    ax.add_image(imagery, zoom_level)
    ax.set_aspect("auto")
    plt.plot(waypoint.longitude, waypoint.latitude, transform=ccrs.PlateCarree())
    if not is_unknown_leg:
        if index > 0:
            plt.plot(
                [waypoints[index - 1].longitude, waypoints[index].longitude],
                [waypoints[index - 1].latitude, waypoints[index].latitude],
                transform=ccrs.PlateCarree(),
                color="blue",
                linewidth=2,
            )
        if index < len(waypoints) - 1:
            plt.plot(
                [waypoints[index].longitude, waypoints[index + 1].longitude],
                [waypoints[index].latitude, waypoints[index + 1].latitude],
                transform=ccrs.PlateCarree(),
                color="blue",
                linewidth=2,
            )
    proj = ccrs.PlateCarree()
    utm = utm_from_lat_lon(waypoint.latitude, waypoint.longitude)
    centre_x, centre_y = utm.transform_point(waypoint.longitude, waypoint.latitude, proj)
    size = meters_across / 2
    x0, y0 = proj.transform_point(centre_x - size, centre_y - size, utm)
    x1, y1 = proj.transform_point(centre_x + size, centre_y + size, utm)
    extent = [x0, x1, y0, y1]
    ax.set_extent(extent, crs=ccrs.PlateCarree())
    circle_points = geodesic.Geodesic().circle(
        lon=waypoint.longitude,
        lat=waypoint.latitude,
        radius=200,
        n_samples=50,
        endpoint=False,
    )
    geom = Polygon(circle_points)
    ax.add_geometries((geom,), crs=ccrs.PlateCarree(), facecolor="none", edgecolor="red", linewidth=3)
    figdata = BytesIO()
    plt.savefig(figdata, format="png", dpi=200, transparent=True)
    figdata.seek(0)
    img = Image.open(figdata, formats=["PNG"])
    if index > 0:
        img2 = img.rotate(waypoint.bearing_from_previous)
    else:
        img2 = img.rotate(waypoint.bearing_next)
    width, height = img2.size
    overlap = 500
    left = overlap
    right = width - overlap
    new_width = right - left
    aspect = 16 / 13
    vertical_centre = height / 2
    vertical = new_width / (2 * aspect)
    top = int(vertical_centre - vertical)
    bottom = int(vertical_centre + vertical)
    cropped = img2.crop((left, top, right, bottom))
    draw = ImageDraw.Draw(cropped)
    if is_unknown_leg:
        fnt = ImageFont.truetype("/src/fonts/OpenSans-Bold.ttf", 100)
        draw.text(
            (10, 10),
            f"{int(round(waypoint.bearing_next))}",
            font=fnt,
            fill=(255, 0, 0, 0),
        )
    image_data = BytesIO()
    cropped.save(image_data, "PNG")
    image_data.seek(0)
    plt.close()
    return image_data


def generate_photo(photo: Photo, waypoint: Waypoint, meters_across: float, zoom_level: int):
    imagery = GoogleTiles(style="satellite")
    plt.figure(figsize=(10, 10))
    ax = plt.axes(projection=imagery.crs)
    ax.add_image(imagery, zoom_level)
    ax.set_aspect("auto")
    plt.plot(photo.longitude, photo.latitude, transform=ccrs.PlateCarree())
    proj = ccrs.PlateCarree()
    utm = utm_from_lat_lon(photo.latitude, photo.longitude)
    centre_x, centre_y = utm.transform_point(photo.longitude, photo.latitude, proj)
    range = meters_across / 2
    x0, y0 = proj.transform_point(centre_x - range, centre_y - range, utm)
    x1, y1 = proj.transform_point(centre_x + range, centre_y + range, utm)
    extent = [x0, x1, y0, y1]
    ax.set_extent(extent, crs=ccrs.PlateCarree())
    figdata = BytesIO()
    plt.savefig(figdata, format="png", dpi=200, transparent=True)
    figdata.seek(0)
    img = Image.open(figdata, formats=["PNG"])
    bearing = waypoint.bearing_next if waypoint.bearing_next is not None else 0
    img2 = img.rotate(bearing)
    width, height = img2.size
    overlap = 500
    left = overlap
    right = width - overlap
    new_width = right - left
    aspect = 16 / 13
    vertical_centre = height / 2
    vertical = new_width / (2 * aspect)
    top = int(vertical_centre - vertical)
    bottom = int(vertical_centre + vertical)
    cropped = img2.crop((left, top, right, bottom))
    draw = ImageDraw.Draw(cropped)

    fnt = ImageFont.truetype("/src/fonts/OpenSans-Bold.ttf", 100)
    draw.text(
        (10, 10),
        f"{photo.name}",
        font=fnt,
        fill=(255, 0, 0, 0),
    )
    temporary_file = NamedTemporaryFile(suffix=".png", delete=False)
    cropped.save(temporary_file, "PNG")
    plt.close()
    temporary_file.seek(0)
    return temporary_file


def get_turning_point_image(
    waypoints: List, index: int, meters_across: float, zoom_level: int, is_unknown_leg: bool = False
) -> NamedTemporaryFile:
    turning_point = generate_turning_point_image(
        waypoints, index, meters_across, zoom_level, is_unknown_leg=is_unknown_leg
    )
    temporary_file = NamedTemporaryFile(suffix=".png", delete=False)
    temporary_file.write(turning_point.read())
    temporary_file.seek(0)
    return temporary_file


def _gallery_columns(flight_order_configuration: FlightOrderConfiguration) -> Tuple[int, int]:
    if flight_order_configuration.document_size == A3:
        return 3, 4
    return 2, 3


def _typst_gallery_pages(cells: List[Tuple[str, Optional[str]]], cols: int, rows: int, header_prefix: str) -> str:
    """Renders `cells` (image path, caption-or-None) as a series of pagebroken gallery
    pages of `cols` columns each, headed "{header_prefix} N/M"."""
    if not cells:
        return ""
    images_per_page = cols * rows
    number_of_images = len(cells)
    number_of_pages = -(-number_of_images // images_per_page)
    pages = []
    for page_index, start in enumerate(range(0, number_of_images, images_per_page), start=1):
        page_cells = cells[start : start + images_per_page]
        heading = f"{header_prefix} {page_index}/{number_of_pages}"
        cell_snippets = []
        for path, caption in page_cells:
            if caption is not None:
                cell_snippets.append(
                    f"[#figure(image({_typst_string(path)}, width: 100%), caption: {_typst_string(caption)}, numbering: none)]"
                )
            else:
                cell_snippets.append(f"[#image({_typst_string(path)}, width: 100%)]")
        grid_body = ",\n    ".join(cell_snippets)
        pages.append(
            f"#pagebreak()\n"
            f"= #({_typst_string(heading)})\n"
            f"#grid(columns: {cols}, column-gutter: 4%, row-gutter: 12pt,\n    {grid_body}\n)"
        )
    return "\n".join(pages)


def _turning_point_gallery_cells(
    contestant, flight_order_configuration: FlightOrderConfiguration, waypoints: List[Waypoint]
) -> List[Tuple[str, Optional[str]]]:
    render_waypoints = [wp for wp in waypoints if wp.type not in (SECRETPOINT, DUMMY, UNKNOWN_LEG)]
    meters_across = flight_order_configuration.turning_point_photos_meters_across
    zoom_level = flight_order_configuration.turning_point_photos_zoom_level
    cells = []
    for wp in render_waypoints:
        image_file = get_turning_point_image(
            waypoints,
            waypoints.index(wp),
            meters_across,
            zoom_level,
            is_unknown_leg=False,
        )
        cells.append((image_file.name, wp.name))
    return cells


def _unknown_leg_gallery_cells(
    contestant, flight_order_configuration: FlightOrderConfiguration, waypoints: List[Waypoint]
) -> List[Tuple[str, Optional[str]]]:
    payload = getattr(getattr(contestant, "contestanttaskconfiguration", None), "compiled_effective_route_payload", {}) or {}
    compiled_unknown_leg_names = {item for item in payload.get("unknown_leg_names", []) if item}
    render_waypoints = [
        waypoint for waypoint in waypoints if waypoint.type == UNKNOWN_LEG or waypoint.name in compiled_unknown_leg_names
    ]
    if not render_waypoints:
        render_waypoints = [waypoint for waypoint in waypoints if waypoint.name in compiled_unknown_leg_names]
    render_waypoints = render_waypoints + _build_decoy_photo_waypoints(contestant.navigation_task)
    random.shuffle(render_waypoints)
    meters_across = flight_order_configuration.unknown_leg_photos_meters_across
    zoom_level = flight_order_configuration.unknown_leg_photos_zoom_level
    cells = []
    for wp in render_waypoints:
        # is_unknown_leg rendering never draws the prev/next track lines (see
        # generate_turning_point_image), so unlike the turning-point gallery this
        # doesn't need the full declared route as index context - the shuffled
        # render_waypoints list (including decoys, which aren't part of the route
        # at all) is its own base, matching the pre-Typst renderer.
        image_file = get_turning_point_image(
            render_waypoints,
            render_waypoints.index(wp),
            meters_across,
            zoom_level,
            is_unknown_leg=True,
        )
        cells.append((image_file.name, None))
    return cells


def _resolve_photo_filename(photo: Photo) -> str:
    if not photo.file:
        raise ValueError("Photo has no file attached")
    try:
        return photo.file.path
    except NotImplementedError:
        with default_storage.open(photo.file.name, "rb") as src:
            suffix = os.path.splitext(photo.file.name)[1] or ".img"
            with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(src.read())
                return tmp.name


def _compiled_observation_photos(contestant, flight_order_configuration: FlightOrderConfiguration) -> list:
    """
    Turnpoint-hunt style CIMA tasks may score observation photos that exist only
    as compiled targets (coordinates + a target waypoint name), with no real
    `Photo` row. Synthesise stand-in objects (matching the small `.name`,
    `.latitude`, `.longitude`, `.file`, `.leg` surface the gallery needs) from
    the compiled payload so those still appear in the flight order.
    """
    if not hasattr(contestant, "contestanttaskconfiguration") or not contestant.contestanttaskconfiguration.is_valid:
        return []
    payload = contestant.contestanttaskconfiguration.compiled_effective_route_payload or {}
    compiled_photos = payload.get("observation_photos", []) or []
    if not compiled_photos:
        return []

    fallback_waypoints = get_effective_route_waypoints(
        contestant.navigation_task,
        contestant=contestant,
        include_contestant_declarations=bool(flight_order_configuration.map_include_contestant_declarations),
    )
    fallback_waypoint = fallback_waypoints[0] if fallback_waypoints else None
    fallback_waypoint_by_name = {
        getattr(item, "name", None): item for item in fallback_waypoints if getattr(item, "name", None)
    }
    synthesised = []
    for item in compiled_photos:
        coordinates = item.get("coordinates") or []
        target_name = item.get("target_name") or item.get("name")
        photo_waypoint = fallback_waypoint_by_name.get(target_name) or fallback_waypoint
        if len(coordinates) != 2 or photo_waypoint is None:
            continue
        lon, lat = coordinates
        synthesised.append(
            SimpleNamespace(
                name=item.get("name") or item.get("target_name") or "Photo",
                latitude=lat,
                longitude=lon,
                file=None,
                leg=photo_waypoint,
            )
        )
    return synthesised


def _photo_gallery_cells(
    contestant, flight_order_configuration: FlightOrderConfiguration
) -> List[Tuple[str, Optional[str]]]:
    photos = list(contestant.navigation_task.route.photo_set.all().order_by("name"))
    if not photos:
        photos = _compiled_observation_photos(contestant, flight_order_configuration)
    meters_across = flight_order_configuration.photos_meters_across
    zoom_level = flight_order_configuration.photos_zoom_level
    cells = []
    for photo in photos:
        waypoint = photo.leg
        if not waypoint:
            continue
        if photo.file:
            image_filename = _resolve_photo_filename(photo)
        else:
            image_file = generate_photo(photo, waypoint, meters_across, zoom_level)
            image_filename = image_file.name
        cells.append((image_filename, photo.name))
    return cells


def round_seconds_timedelta(stamp: datetime.timedelta) -> datetime.timedelta:
    new_stamp = stamp
    if stamp.microseconds >= 500000:
        new_stamp = stamp + datetime.timedelta(seconds=1)
    return new_stamp - datetime.timedelta(microseconds=new_stamp.microseconds)


def _gate_times_table_rows(contestant: "Contestant", waypoints: List[Waypoint]) -> str:
    rows = []

    def add_row(cells):
        rows.append(", ".join(_typst_string(cell) for cell in cells))

    rows.append("[*Gate*], [*Leg (NM)*], [*Tot (NM)*], [*TT*], [*TH*], [*GS (kt)*], [*Leg time*], [*Gate Time*]")
    rows.append("table.hline()")

    local_time = "-"
    if contestant.navigation_task.route.first_takeoff_gate:
        local_time = contestant.gate_times.get(contestant.navigation_task.route.first_takeoff_gate.name, None)
        if local_time:
            local_time = local_time.astimezone(contestant.navigation_task.contest.time_zone).strftime("%H:%M:%S")
        add_row(["Takeoff gate", "-", "-", "-", "-", "-", "-", local_time])
        rows.append("table.hline()")

    accumulated_distance = 0
    last_record_distance = 0
    previous_waypoint = None
    last_recorded_time = None
    first_line = True
    waypoint: Waypoint
    for waypoint in waypoints:
        if not first_line:
            accumulated_distance += waypoint.distance_previous
        if waypoint.type not in ("secret", "dummy", "ul") or (
            contestant.navigation_task.scorecard.calculator == ANR_CORRIDOR and not waypoint.on_curved_segment
        ):
            bearing = waypoint.bearing_from_previous
            wind_correction_angle = calculate_wind_correction_angle(
                bearing,
                contestant.air_speed,
                contestant.wind_speed,
                contestant.wind_direction,
            )
            wind_bearing = normalise_bearing(bearing - wind_correction_angle)
            ground_speed = calculate_ground_speed(
                bearing,
                contestant.air_speed,
                wind_correction_angle,
                contestant.wind_speed,
                contestant.wind_direction,
            )
            gate_time = contestant.gate_times.get(waypoint.name, None)
            local_waypoint_time = gate_time.astimezone(contestant.navigation_task.contest.time_zone)
            if gate_time is not None:
                distance = accumulated_distance - last_record_distance
                add_row(
                    [
                        waypoint.name,
                        f"{distance / 1852:.2f}" if not first_line else "-",
                        f"{accumulated_distance / 1852:.2f}" if not first_line else "-",
                        f"{bearing:.0f}" if not first_line else "-",
                        f"{wind_bearing:.0f}" if not first_line else "-",
                        f"{ground_speed:.1f}" if not first_line else "-",
                        (
                            str(
                                round_seconds_timedelta(
                                    local_waypoint_time
                                    - last_recorded_time
                                    - (
                                        PROCEDURE_TURN_DURATION
                                        if previous_waypoint is not None and previous_waypoint.is_procedure_turn
                                        else datetime.timedelta(seconds=0)
                                    )
                                )
                            )
                            if last_recorded_time
                            else "-"
                        ),
                        local_waypoint_time.strftime("%H:%M:%S"),
                    ]
                )
                first_line = False
            last_record_distance = accumulated_distance
            last_recorded_time = gate_time
            previous_waypoint = waypoint

    if contestant.navigation_task.route.first_landing_gate:
        local_time = contestant.gate_times.get(contestant.navigation_task.route.first_landing_gate.name, None)
        if local_time:
            local_time = local_time.astimezone(contestant.navigation_task.contest.time_zone).strftime("%H:%M:%S")
        rows.append("table.hline()")
        add_row(["Landing gate", "-", "-", "-", "-", "-", "-", local_time])

    return ",\n    ".join(rows)


def generate_flight_orders(contestant: "Contestant") -> bytes:
    flight_order_configuration: FlightOrderConfiguration = contestant.navigation_task.flightorderconfiguration
    starting_point_time_string = f"{contestant.starting_point_time_local.strftime('%H:%M:%S')}"
    tracking_start_time_string = f"{contestant.tracker_start_time_local.strftime('%H:%M:%S')}"
    finish_tracking_time = f"{contestant.finished_by_time_local.strftime('%H:%M:%S')}"
    facebook_share_url = "https://www.facebook.com/sharer/sharer.php?u="
    url = facebook_share_url + "https://app.airsports.no" + contestant.navigation_task.tracking_link
    qr = qr_code_image(url, "static/img/facebook_logo.png")
    qr_file = NamedTemporaryFile(suffix=".png")
    qr.save(qr_file)
    qr_file.seek(0)

    starting_point_text = starting_point_time_string
    if contestant.adaptive_start:
        starting_point_text = f"After {tracking_start_time_string}"

    if contestant.navigation_task.contest.logo:
        logo_url = f"{MEDIA_ROOT_URL}{contestant.navigation_task.contest.logo}"
        logo = f"/tmp/{contestant.navigation_task.contest.logo}"
        try:
            urllib.request.urlretrieve(logo_url, logo)
            lower_logo = logo.lower()
            if not (
                lower_logo.endswith(".png")
                or lower_logo.endswith(".jpg")
                or lower_logo.endswith(".jpeg")
                or lower_logo.endswith(".pdf")
            ):
                img = Image.open(logo)
                logo = logo.rsplit(".", 1)[0] + ".png"
                img.save(logo)
        except:
            logo = "/src/static/img/airsports_no_text.png"
    else:
        logo = "/src/static/img/airsports_no_text.png"

    is_a3 = flight_order_configuration.document_size == A3
    base_font_size = "12pt" if is_a3 else "11pt"
    paper = "a3" if is_a3 else "a4"

    header_footer = (
        "context [#align(center)[#image("
        + _typst_string("/src/static/img/AirSportsLiveTracking.png")
        + ", width: 35%)]]"
    )
    map_footer = (
        "context [#align(right)[#image("
        + _typst_string("/src/static/img/AirSportsLiveTrackingWhiteBG.png")
        + ", width: 30%)]]"
    )

    waypoints = get_flight_order_visual_waypoints(
        contestant,
        include_contestant_declarations=bool(flight_order_configuration.map_include_contestant_declarations),
    )
    starting_point_image_file = get_turning_point_image(
        waypoints,
        0,
        flight_order_configuration.turning_point_photos_meters_across,
        flight_order_configuration.turning_point_photos_zoom_level,
    )
    finish_point_image_file = get_turning_point_image(
        waypoints,
        len(waypoints) - 1,
        flight_order_configuration.turning_point_photos_meters_across,
        flight_order_configuration.turning_point_photos_zoom_level,
    )

    map_image = plot_route(
        contestant.navigation_task,
        flight_order_configuration.document_size,
        **build_flight_order_map_plot_kwargs(
            contestant.navigation_task,
            flight_order_configuration,
            contestant=contestant,
        ),
    )
    mapimage_file = NamedTemporaryFile(suffix=".png")
    mapimage_file.write(map_image.read())
    mapimage_file.seek(0)
    map_width = flight_order_configuration.page_width_mm - 20
    map_height = flight_order_configuration.page_height_mm - 20

    adaptive_start_note = ""
    if contestant.adaptive_start:
        adaptive_start_note = (
            "#v(10pt)\n#emph[Adaptive Start: Your start time is set to the nearest whole minute you cross the "
            "starting gate line (within +/- 1 hour).]"
        )

    generated_at = (
        f"Flight order generated at "
        f"{datetime.datetime.now().astimezone(contestant.navigation_task.contest.time_zone).strftime('%Y-%m-%d %H:%M:%S %Z')}"
    )

    gate_time_rows = _gate_times_table_rows(contestant, waypoints)

    cols, rows = _gallery_columns(flight_order_configuration)
    turning_point_pages = ""
    if flight_order_configuration.include_turning_point_images:
        turning_point_pages = _typst_gallery_pages(
            _turning_point_gallery_cells(contestant, flight_order_configuration, waypoints),
            cols,
            rows,
            "Turning point and time gate images",
        )

    unknown_leg_pages = ""
    if any(waypoint.type == UNKNOWN_LEG for waypoint in waypoints):
        unknown_leg_pages = _typst_gallery_pages(
            _unknown_leg_gallery_cells(contestant, flight_order_configuration, waypoints),
            cols,
            rows,
            "Unknown legs images",
        )

    photo_pages = ""
    if (
        contestant.navigation_task.route.photo_set.all().count() > 0
        or _compiled_observation_photos(contestant, flight_order_configuration)
    ):
        photo_pages = _typst_gallery_pages(
            _photo_gallery_cells(contestant, flight_order_configuration),
            cols,
            rows,
            "Photos",
        )

    source = f"""
#set page(paper: {_typst_string(paper)}, margin: (left: 10mm, right: 10mm, top: 10mm, bottom: 15mm), footer: {header_footer})
#set text(size: {base_font_size})
#set par(first-line-indent: 0pt)

#align(center)[
  #text(size: 18pt)[Welcome to] \\
  #v(7pt)
  #text(size: 28pt, weight: "bold")[#({_typst_string(contestant.navigation_task.contest.name)})] \\
  #v(5pt)
  #text(size: 18pt, fill: red, weight: "bold")[#({_typst_string(contestant.navigation_task.name)})]
]

#v(10pt)

#grid(columns: (58%, 30%), column-gutter: 4%,
  [
    #block(fill: blue.lighten(90%), stroke: blue.darken(25%), radius: 4pt, inset: 10pt, width: 100%)[
      #text(weight: "bold", size: 14pt)[Flight Briefing]
      #v(6pt)
      #table(
        columns: (auto, 1fr),
        stroke: none,
        inset: (x: 0pt, y: 4pt),
        [*Contestant:*], [#({_typst_string(str(contestant))})],
        [*Task Type:*], [#({_typst_string(contestant.navigation_task.scorecard.get_calculator_display())})],
        [*Date:*], [#({_typst_string(contestant.starting_point_time_local.strftime("%Y-%m-%d"))})],
        [*Airspeed:*], [#({_typst_string("{:.0f}".format(contestant.air_speed) + " knots")})],
        [*Wind:*], [#({_typst_string("{:03.0f}".format(contestant.wind_direction) + "@" + "{:.0f}".format(contestant.wind_speed))})],
        [*Departure:*], [#({_typst_string(contestant.takeoff_time.astimezone(contestant.navigation_task.contest.time_zone).strftime("%H:%M:%S") if not contestant.adaptive_start else "Adaptive")})],
        [*Start Point:*], [#({_typst_string(starting_point_text)})],
        [*Finish By:*], [#({_typst_string(finish_tracking_time)})],
      )
    ]
  ],
  [
    #align(center)[
      #image({_typst_string(qr_file.name)}, width: 90%)
      #v(5pt)
      #link({_typst_string(url)})[#text(size: 9pt)[Share on Facebook]]
    ]
  ]
)
{adaptive_start_note}

#v(15pt)

#block(fill: red.lighten(90%), stroke: red.darken(25%), radius: 4pt, inset: 10pt, width: 100%, breakable: true)[
  #text(weight: "bold")[Rules \\& Regulations]
  #v(6pt)
  #({_typst_string(_flow_text(contestant.get_formatted_rules_description()))})
]

#v(20pt)
#align(center)[#text(size: 22pt, weight: "bold")[Good Luck!]]
#v(10pt)

#grid(columns: (45%, 45%), column-gutter: 10%,
  [#figure(image({_typst_string(starting_point_image_file.name)}, width: 100%), caption: [Starting point], numbering: none)],
  [#figure(image({_typst_string(finish_point_image_file.name)}, width: 100%), caption: [Finish point], numbering: none)],
)

#v(10pt)
#text(size: 9pt)[#({_typst_string(generated_at)})]

#pagebreak()
= Turning points and time gates
#text(size: {("14pt" if is_a3 else "12pt")})[
#table(
  columns: 8,
  stroke: none,
  inset: (x: 4pt, y: 4pt),
  {gate_time_rows}
)
]

#pagebreak()
#set page(footer: {map_footer})
#align(center + horizon)[
  #image({_typst_string(mapimage_file.name)}, {("height: " + str(map_height) + "mm") if flight_order_configuration.map_orientation == LANDSCAPE else ("width: " + str(map_width) + "mm")})
]

#set page(footer: {header_footer})
{turning_point_pages}
{unknown_leg_pages}
{photo_pages}
"""

    typ_file = NamedTemporaryFile(suffix=".typ", mode="w", delete=False)
    typ_file.write(source)
    typ_file.close()
    try:
        return typst.compile(typ_file.name, root="/")
    except typst.TypstError:
        logger.exception("Something failed when generating flight order PDF")
        raise


def embed_map_in_pdf(
    paper: Literal["a4paper", "a3paper"],
    map_image: bytes,
    width_mm: float,
    height_mm: float,
    landscape: bool,
) -> bytes:
    paper_size_mm = (297.0, 420.0) if paper == "a3paper" else (210.0, 297.0)

    class _MapFPDF(FPDF):
        def footer(self):
            logo_width = 0.3 * self.epw
            self.set_y(-25)
            self.set_x(self.w - self.r_margin - logo_width)
            self.image("/src/static/img/AirSportsLiveTracking.png", w=logo_width)

    pdf = _MapFPDF(format=paper_size_mm)
    pdf.set_margins(left=10, top=10, right=10)
    pdf.set_auto_page_break(False)
    pdf.add_page()
    map_image_file = BytesIO(map_image)
    if landscape:
        pdf.image(map_image_file, x=10, y=10, h=height_mm)
    else:
        pdf.image(map_image_file, x=10, y=10, w=width_mm)
    return bytes(pdf.output())
