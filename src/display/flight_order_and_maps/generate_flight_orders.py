import logging
import os.path
import random
import urllib
import urllib.request
from io import BytesIO
from subprocess import CalledProcessError
from tempfile import NamedTemporaryFile
from typing import List, Literal
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont
from cartopy import geodesic

from cartopy.io.img_tiles import GoogleTiles
from fpdf import FPDF, HTMLMixin
from pylatex.base_classes import Environment, Arguments
from pylatex.utils import bold
from shapely.geometry import Polygon

from display.utilities.coordinate_utilities import utm_from_lat_lon, normalise_bearing
from display.flight_order_and_maps.map_constants import LANDSCAPE, A4
from display.flight_order_and_maps.map_plotter import plot_route
from display.flight_order_and_maps.map_plotter_shared_utilities import qr_code_image
from display.models import Contestant
from display.waypoint import Waypoint
import cartopy.crs as ccrs

from display.utilities.wind_utilities import calculate_wind_correction_angle
from live_tracking_map.settings import AZURE_ACCOUNT_NAME
from pylatex import (
    Document,
    PageStyle,
    MiniPage,
    NoEscape,
    StandAloneGraphic,
    Section,
    HugeText,
    Center,
    LineBreak,
    LargeText,
    Package,
    TextColor,
    Tabu,
    VerticalSpace,
    Figure,
    Command,
    Foot,
    NewPage,
    Label,
    Marker,
    MediumText,
)

logger = logging.getLogger(__name__)


class MyFPDF(FPDF, HTMLMixin):
    pass


def generate_turning_point_image(waypoints: List[Waypoint], index, unknown_leg: bool = False):
    waypoint = waypoints[index]
    imagery = GoogleTiles(style="satellite")
    plt.figure(figsize=(10, 10))
    ax = plt.axes(projection=imagery.crs)
    ax.add_image(imagery, 15)
    ax.set_aspect("auto")
    plt.plot(waypoint.longitude, waypoint.latitude, transform=ccrs.PlateCarree())
    if not unknown_leg:
        if index > 0:
            plt.plot(
                [waypoints[index - 1].longitude, waypoints[index].longitude],
                [waypoints[index - 1].latitude, waypoints[index].latitude],
                transform=ccrs.PlateCarree(),
                color="blue",
                linewidth=2,
            )
        if index < len(waypoints) - 1:
            # print(waypoints[index])
            # print(waypoints[index + 1])
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
    range = 700
    x0, y0 = proj.transform_point(centre_x - range, centre_y - range, utm)
    x1, y1 = proj.transform_point(centre_x + range, centre_y + range, utm)
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
    # plt.savefig(
    #     "temporary", format="png", dpi=100, transparent=True
    # )
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
    if unknown_leg:
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


def insert_turning_point_images_latex(contestant, document: Document):
    navigation = contestant.navigation_task  # type: NavigationTask
    render_turning_point_images(navigation.route.waypoints, document, "Turning point", unknown_leg=False)


def insert_unknown_leg_images_latex(
    contestant,
    document: Document,
):
    navigation = contestant.navigation_task  # type: NavigationTask
    render_waypoints = [waypoint for waypoint in navigation.route.waypoints if waypoint.type == "ul"]
    random.shuffle(render_waypoints)
    render_turning_point_images(render_waypoints, document, "Unknown legs", unknown_leg=True)


def render_turning_point_images(
    waypoints: List[Waypoint],
    document,
    header_prefix: str,
    unknown_leg: bool = False,
):
    render_waypoints = [
        waypoint
        for waypoint in waypoints
        if waypoint.type not in ("secret", "ul") and (waypoint.gate_check or waypoint.time_check)
    ]

    rows_per_page = 3
    number_of_images = len(render_waypoints)
    number_of_pages = 1 + ((number_of_images - 1) // (2 * rows_per_page))
    current_page = -1
    document.append(Label(Marker("firstpagetocount")))
    for index in range(0, len(render_waypoints), 2):
        if index % (rows_per_page * 2) == 0:
            document.append(NewPage())
            page_text = f"{header_prefix} images {current_page + 2}/{number_of_pages}" if number_of_pages > 1 else ""
            document.append(Section(page_text, numbering=False))
            current_page += 1
        figure_width = 0.4
        with document.create(Figure(position="!ht")):
            with document.create(MiniPage(width=fr"{figure_width}\textwidth")):
                image_file = get_turning_point_image(
                    # Use full waypoint list to get correct track in image
                    waypoints, waypoints.index(render_waypoints[index]), unknown_leg=unknown_leg
                )
                document.append(
                    StandAloneGraphic(
                        image_options=r"width=\linewidth",
                        filename=image_file.name,
                    )
                )
                if not unknown_leg:
                    document.append(Command("caption*", render_waypoints[index].name))
            document.append(Command("hfill"))
            if index < len(render_waypoints) - 1:
                image_file = get_turning_point_image(
                    # Use full waypoint list to get correct track in image
                    waypoints, waypoints.index(render_waypoints[index + 1]), unknown_leg=unknown_leg
                )
                with document.create(MiniPage(width=fr"{figure_width}\textwidth")):
                    document.append(
                        StandAloneGraphic(
                            image_options=r"width=\linewidth",
                            filename=image_file.name,
                        )
                    )
                    if not unknown_leg:
                        document.append(Command("caption*", render_waypoints[index + 1].name))
    document.append(Label(Marker("lastpagetocount")))


def recode_text(text: str):
    return text.encode("latin-1", "replace").decode("latin-1")


class WrapFigure(Environment):
    _latex_name = "wrapfigure"
    packages = [Package("wrapfig")]

    def __init__(self, left_or_right: str, width_string, data=None):
        super().__init__(
            arguments=Arguments(left_or_right, width_string),
            data=data,
        )


def generate_flight_orders_latex(contestant: "Contestant") -> bytes:
    flight_order_configuration = contestant.navigation_task.flightorderconfiguration
    starting_point_time_string = f'{contestant.starting_point_time_local.strftime("%H:%M:%S")}'
    tracking_start_time_string = f'{contestant.tracker_start_time_local.strftime("%H:%M:%S")}'
    finish_tracking_time = f'{contestant.finished_by_time_local.strftime("%H:%M:%S")}'
    facebook_share_url = "https://www.facebook.com/sharer/sharer.php?u="
    url = facebook_share_url + "https://airsports.no" + contestant.navigation_task.tracking_link
    qr = qr_code_image(url, "static/img/facebook_logo.png")
    qr_file = NamedTemporaryFile(suffix=".png")
    qr.save(qr_file)
    qr_file.seek(0)

    starting_point_text = starting_point_time_string
    if contestant.adaptive_start:
        starting_point_text = f"After {tracking_start_time_string}"

    if contestant.navigation_task.contest.logo:
        logo_url = f"https://{AZURE_ACCOUNT_NAME}.blob.core.windows.net/media/{contestant.navigation_task.contest.logo}"
        logo = f"/tmp/{contestant.navigation_task.contest.logo}"
        urllib.request.urlretrieve(logo_url, logo)
    else:
        logo = "/src/static/img/airsports_no_text.png"

    geometry_options = {
        "a4paper": True,
        "head": "40pt",
        "left": "10mm",
        "right": "10mm",
        "top": "10mm",
        "bottom": "15mm",
        "includeheadfoot": False,
    }
    document = Document(indent=False)
    document.preamble.append(
        Command(
            "usepackage",
            "geometry",
            "a4paper,head=40pt,left=10mm,right=10mm,top=10mm,bottom=15mm",
        )
    )
    document.preamble.append(Command("usepackage", "graphicx"))
    document.preamble.append(Command("usepackage", "caption"))
    document.preamble.append(Command("usepackage", "xassoccnt"))
    document.preamble.append(Command("usepackage", "zref", "abspage,user,lastpage"))
    document.preamble.append(Command("usepackage", "hyperref"))
    # document.preamble.append(Command("newcounter", "turningpointimagepages"))
    # document.preamble.append(Command("makeatletter"))
    # count_command = UnsafeCommand(
    #     "newcommand",
    #     "totalimagepages",
    #     extra_arguments=r"\setcounter{turningpointimagepages}{\numexpr\zref@extract{lastpagetocount}{abspage} -\zref@extract{firstpagetocount}{abspage}+1\relax}\theturningpointimagepages",
    # )
    # document.preamble.append(count_command)
    # document.preamble.append(Command("makeatother"))
    # document.preamble.append(Command("newcounter", "realpage"))
    # document.preamble.append(Command("DeclareAssociatedCounters", ["page", "realpage"]))
    # document.preamble.append(
    #     Command("AtBeginDocument", NoEscape(r"\stepcounter{realpage}"))
    # )
    document.preamble.append(Command("captionsetup", "font=Large", "figure"))
    header = PageStyle("header")
    with header.create(Foot("C")):
        header.append(
            StandAloneGraphic(
                image_options=r"width=0.4\linewidth",
                filename="/src/static/img/AirSportsLiveTracking.png",
            )
        )
    document.preamble.append(header)
    # Map header
    map_header = PageStyle("mapheader")
    with map_header.create(Foot("R")):
        map_header.append(
            StandAloneGraphic(
                image_options=r"width=0.3\linewidth",
                filename="/src/static/img/AirSportsLiveTracking.png",
            )
        )
    document.preamble.append(map_header)
    # turning_point_header = PageStyle("turningpointheader")
    # with turning_point_header.create(Head("C")):
    #     turning_point_header.append(
    #         NoEscape(r"Turning point images \therealpage \totalimagepages")
    #     )
    # document.preamble.append(turning_point_header)
    document.change_document_style("header")
    with document.create(MiniPage()):
        with document.create(WrapFigure("r", "80pt")):
            document.append(StandAloneGraphic(image_options=r"width=\linewidth", filename=logo))
        with document.create(Section("", numbering=False)):
            with document.create(Center()):
                document.append(LargeText("Welcome to"))
                document.append(LineBreak())
                document.append(LineBreak())
                document.append(HugeText(f"{contestant.navigation_task.contest.name}"))
                document.append(LineBreak())
                document.append(LineBreak())
                document.append(TextColor("red", LargeText(f"{contestant.navigation_task.name}")))
    document.append(VerticalSpace("10pt"))
    with document.create(Section("", numbering=False)):
        with document.create(MiniPage()):
            with document.create(MiniPage(width=NoEscape(r"0.7\textwidth"))):
                with document.create(Section("", numbering=False)):
                    with document.create(Tabu("ll", row_height=1.2, booktabs=False)) as data_table:
                        document.append(Command("fontsize", "14pt", extra_arguments="16pt"))
                        document.append(Command("selectfont"))
                        data_table.add_row(bold("Contestant:"), MediumText(str(contestant)))
                        data_table.add_row(
                            bold("Task type:"),
                            f"{contestant.navigation_task.scorecard.get_calculator_display()}",
                        )
                        data_table.add_row(
                            bold("Competition date:"),
                            f'{contestant.starting_point_time_local.strftime("%Y-%m-%d")}',
                        )
                        data_table.add_row(bold("Airspeed:"), f'{"{:.0f}".format(contestant.air_speed)} knots')
                        data_table.add_row(
                            bold("Tasks wind:"),
                            f'{"{:03.0f}".format(contestant.wind_direction)}@{"{:.0f}".format(contestant.wind_speed)}',
                        )
                        data_table.add_row(
                            bold("Departure:"),
                            f"{contestant.takeoff_time.astimezone(contestant.navigation_task.contest.time_zone).strftime('%Y-%m-%d %H:%M:%S') if not contestant.adaptive_start else 'Take-off time is not measured'}",
                        )
                        data_table.add_row(bold("Start point:"), f"{starting_point_text}")
                        data_table.add_row(bold("Finish by:"), f"{finish_tracking_time} (tracking will stop)")
                if contestant.adaptive_start:
                    with document.create(Section("", numbering=False)):
                        document.append(
                            f"Using adaptive start, your start time will be set to the nearest whole minute you cross the infinite "
                            f"line going through the starting gate anywhere between one hour before and one hour after the selected "
                            f"starting point time."
                        )
                        document.append(LineBreak())
                        document.append("https://home.airsports.no/faq/#adaptiv-start")

            document.append(Command(r"hfill"))
            with document.create(MiniPage(width=NoEscape(r"0.25\textwidth"))):
                document.append(StandAloneGraphic(image_options=r"width=0.8\linewidth", filename=qr_file.name))
                document.append(
                    Command(
                        "captionof*",
                        "figure",
                        extra_arguments=NoEscape(fr"\protect\href{{{url}}}{{Share on Facebook}}"),
                    )
                )

    with document.create(Section("Rules", numbering=False)):
        document.append(contestant.get_formatted_rules_description().replace("\n", ""))
    document.append(VerticalSpace("25pt"))
    with document.create(Center()):
        document.append(HugeText(bold("Good luck")))
    document.append(VerticalSpace("20pt"))
    waypoints = list(
        filter(
            lambda waypoint: waypoint.type != "dummy",
            contestant.navigation_task.route.waypoints,
        )
    )
    starting_point_image_file = get_turning_point_image(waypoints, 0)
    finish_point_image_file = get_turning_point_image(waypoints, len(waypoints) - 1)
    with document.create(Figure(position="!ht")):
        with document.create(MiniPage(width=r"0.45\textwidth")):
            document.append(
                StandAloneGraphic(
                    image_options=r"width=\linewidth",
                    filename=starting_point_image_file.name,
                )
            )
            document.append(Command("caption*", "Starting point"))
        document.append(Command("hfill"))
        with document.create(MiniPage(width=r"0.45\textwidth")):
            document.append(
                StandAloneGraphic(
                    image_options=r"width=\linewidth",
                    filename=finish_point_image_file.name,
                )
            )
            document.append(Command("caption*", "Finish point"))
    document.append(NewPage())
    with document.create(Section("Turning point times", numbering=False)):
        with document.create(MiniPage(width=r"\textwidth")):
            document.append(Command("Large"))
            with document.create(Tabu("X[l] X[l] X[l] X[l] X[l]")) as data_table:
                data_table.add_row(["Turning point", "Distance", "TT", "TH", "Time"], mapper=[bold])
                data_table.add_hline()
                first_line = True
                local_time = "-"
                if contestant.navigation_task.route.first_takeoff_gate:
                    local_time = contestant.gate_times.get(
                        contestant.navigation_task.route.first_takeoff_gate.name, None
                    )
                    if local_time:
                        local_time = local_time.astimezone(contestant.navigation_task.contest.time_zone).strftime(
                            "%H:%M:%S"
                        )
                data_table.add_row(["Takeoff gate", "-", "-", "-", local_time])

                accumulated_distance = 0
                for waypoint in contestant.navigation_task.route.waypoints:  # type: Waypoint
                    if not first_line:
                        accumulated_distance += waypoint.distance_previous
                    if waypoint.type not in ("secret", "dummy", "ul") and waypoint.time_check:
                        bearing = waypoint.bearing_from_previous
                        wind_correction_angle = calculate_wind_correction_angle(
                            bearing,
                            contestant.air_speed,
                            contestant.wind_speed,
                            contestant.wind_direction,
                        )
                        wind_bearing = normalise_bearing(bearing - wind_correction_angle)
                        gate_time = contestant.gate_times.get(waypoint.name, None)
                        local_waypoint_time = gate_time.astimezone(contestant.navigation_task.contest.time_zone)
                        if gate_time is not None:
                            data_table.add_row(
                                [
                                    waypoint.name,
                                    f"{accumulated_distance / 1852:.2f} NM" if not first_line else "-",
                                    f"{bearing:.0f}" if not first_line else "-",
                                    f"{wind_bearing:.0f}" if not first_line else "-",
                                    local_waypoint_time.strftime("%H:%M:%S"),
                                ]
                            )
                            accumulated_distance = 0
                            first_line = False
                local_time = "-"
                if contestant.navigation_task.route.first_landing_gate:
                    local_time = contestant.gate_times.get(
                        contestant.navigation_task.route.first_landing_gate.name, None
                    )
                    if local_time:
                        local_time = local_time.astimezone(contestant.navigation_task.contest.time_zone).strftime(
                            "%H:%M:%S"
                        )
                data_table.add_row(["Landing gate", "-", "-", "-", local_time])

    map_image = plot_route(
        contestant.navigation_task,
        A4,  # flight_order_configuration.document_size,
        zoom_level=flight_order_configuration.map_zoom_level,
        landscape=flight_order_configuration.map_orientation == LANDSCAPE,
        contestant=contestant,
        annotations=flight_order_configuration.map_include_annotations,
        waypoints_only=not flight_order_configuration.map_plot_track_between_waypoints,
        dpi=flight_order_configuration.map_dpi,
        scale=flight_order_configuration.map_scale,
        map_source=flight_order_configuration.map_source,
        user_map_source=str(flight_order_configuration.map_user_source.map_file)
        if flight_order_configuration.map_user_source
        else "",
        line_width=flight_order_configuration.map_line_width,
        minute_mark_line_width=flight_order_configuration.map_minute_mark_line_width,
        colour=flight_order_configuration.map_line_colour,
        include_meridians_and_parallels_lines=flight_order_configuration.map_include_meridians_and_parallels_lines,
        margins_mm=10,
    )
    mapimage_file = NamedTemporaryFile(suffix=".png")
    mapimage_file.write(map_image.read())
    mapimage_file.seek(0)
    document.append(NewPage())
    # document.append(Command("newgeometry", "left=0pt,bottom=0pt,top=0pt,right=0pt"))
    document.change_document_style("mapheader")
    # with document.create(Figure(position="!ht")):
    with document.create(MiniPage()):
        document.append(Command("centering"))
        document.append(
            StandAloneGraphic(
                mapimage_file.name,
                rf"width=190mm" if flight_order_configuration.map_orientation != LANDSCAPE else rf"height=277mm",
            )
        )  # f"resolution={flight_order_configuration.map_dpi}"))
    document.append(NewPage())
    # document.append(Command("restoregeometry"))

    document.change_document_style("header")
    # document.change_document_style("turningpointheader")
    if flight_order_configuration.include_turning_point_images:
        insert_turning_point_images_latex(contestant, document)

    if any(waypoint.type == "ul" for waypoint in contestant.navigation_task.route.waypoints):
        insert_unknown_leg_images_latex(contestant, document)

    # Produce the output
    pdf_file = NamedTemporaryFile()
    document.generate_tex(pdf_file.name)
    with open(pdf_file.name + ".tex", "r") as f:
        print(f.read())
    try:
        document.generate_pdf(pdf_file.name, clean=True, compiler_args=["-f"])
    except CalledProcessError:
        file_exists = os.path.isfile(pdf_file.name + ".pdf")
        logger.exception(f"Something failed when generating flight order PDF. Output file exists: {file_exists}")
    with open(pdf_file.name + ".pdf", "rb") as f:
        return f.read()


def get_turning_point_image(waypoints: List, index: int, unknown_leg: bool = False) -> NamedTemporaryFile:
    turning_point = generate_turning_point_image(waypoints, index, unknown_leg=unknown_leg)
    temporary_file = NamedTemporaryFile(suffix=".png", delete=False)
    temporary_file.write(turning_point.read())
    temporary_file.seek(0)
    return temporary_file


def embed_map_in_pdf(
    paper: Literal["a4paper", "a3paper"],
    map_image: bytes,
    width_mm: float,
    height_mm: float,
    landscape: bool,
) -> bytes:
    document = Document(indent=False)
    document.preamble.append(
        Command(
            "usepackage",
            "geometry",
            f"{paper},head=0pt,left=10mm,right=10mm,top=10mm,bottom=15mm",
        )
    )
    map_header = PageStyle("mapheader")
    with map_header.create(Foot("R")):
        map_header.append(
            StandAloneGraphic(
                image_options=r"width=0.3\linewidth",
                filename="/src/static/img/AirSportsLiveTracking.png",
            )
        )
    document.preamble.append(map_header)
    document.change_document_style("mapheader")
    mapimage_file = NamedTemporaryFile(suffix=".png")
    mapimage_file.write(map_image)
    mapimage_file.seek(0)
    with document.create(Figure()):
        document.append(
            StandAloneGraphic(
                mapimage_file.name,
                rf"width={width_mm}mm" if not landscape else rf"height={height_mm}mm",
            )
        )
    pdf_file = NamedTemporaryFile()
    document.generate_pdf(pdf_file.name, clean=True, compiler_args=["-f"])
    with open(pdf_file.name + ".pdf", "rb") as f:
        return f.read()
