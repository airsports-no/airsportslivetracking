# from lxml import etree
import logging
from typing import List, Tuple, Dict
from zipfile import ZipFile

import gpxpy
import pygeoif
from django.core.exceptions import ValidationError
from fastkml import kml, Placemark

from display.utilities.coordinate_utilities import (
    Projector,
    extend_line,
    calculate_distance_lat_lon,
    calculate_bearing,
    create_bisecting_line_between_segments_corridor_width_lonlat,
    create_perpendicular_line_at_end_lonlat,
    create_rounded_corridor_corner,
    bearing_difference,
    calculate_fractional_distance_point_lat_lon,
    point_to_line_segment_distance,
)
from display.models import Route, Scorecard, Prohibited

from display.waypoint import Waypoint

logger = logging.getLogger(__name__)


def is_procedure_turn(bearing1, bearing2) -> bool:
    """
    Return True if the turn is more than 90 degrees

    :param bearing1: degrees
    :param bearing2: degrees
    :return:
    """
    return abs(bearing_difference(bearing1, bearing2)) > 90


def add_line(place_mark):
    return [tuple(reversed(item[:2])) for item in place_mark.geometry.coords]


def add_polygon(place_mark):
    return [tuple(reversed(item[:2])) for item in place_mark.geometry.exterior.coords]


def open_kmz(file):
    zip = ZipFile(file)
    for z in zip.filelist:
        if z.filename[-4:] == ".kml":
            fstring = zip.read(z)
            break
    else:
        raise Exception("Could not find kml file in %s" % file)
    return fstring


def open_kml(file):
    try:
        fstring = open_kmz(file)
    except Exception:
        # In case zipfile screwed with the buffer
        file.seek(0)
        fstring = file.read()
    return fstring


def parse_geometries(placemark):
    if hasattr(placemark, "geometry"):  # check if the placemark has a geometry or not
        if isinstance(placemark.geometry, pygeoif.Point):
            # add_point(placemark)
            pass
        elif isinstance(placemark.geometry, pygeoif.LineString):
            return add_line(placemark)
        elif isinstance(placemark.geometry, pygeoif.LinearRing):
            return add_line(placemark)  # LinearRing can be plotted through LineString
        elif isinstance(placemark.geometry, pygeoif.Polygon):
            return add_polygon(placemark)
        # elif isinstance(placemark.geometry, geometry.MultiPoint):
        #     for geom in placemark.geometry.geoms:
        #         add_multipoint(geom)
        # elif isinstance(placemark.geometry, geometry.MultiLineString):
        #     for geom in placemark.geometry.geoms:
        #         add_multiline(geom)
        # elif isinstance(placemark.geometry, geometry.MultiPolygon):
        #     for geom in placemark.geometry.geoms:
        #         add_multipolygon(geom)
        # elif isinstance(placemark.geometry, geometry.GeometryCollection):
        #     for geom in placemark.geometry.geoms:
        #         if geom.geom_type == "Point":
        #             add_multipoint(geom)
        #         elif geom.geom_type == "LineString":
        #             add_multiline(geom)
        #         elif geom.geom_type == "LinearRing":
        #             add_multiline(geom)
        #         elif geom.geom_type == "Polygon":
        #             add_multipolygon(geom)


def parse_placemarks(document) -> List[Placemark]:
    place_marks = []
    for feature in document:
        if isinstance(feature, kml.Placemark):
            place_marks.append((feature.name, parse_geometries(feature)))
    for feature in document:
        if isinstance(feature, kml.Folder):
            place_marks.extend(parse_placemarks(list(feature.features())))
        if isinstance(feature, kml.Document):
            place_marks.extend(parse_placemarks(list(feature.features())))
    return place_marks


def validate_no_overlapping_gate_lines(gates: list[Waypoint]):
    projector = Projector(gates[0].latitude, gates[0].longitude)
    for index in range(0, len(gates) - 1):
        for second_index in range(index + 1, len(gates)):
            intersection = projector.intersect(
                gates[index].gate_line[0],
                gates[index].gate_line[1],
                gates[second_index].gate_line[0],
                gates[second_index].gate_line[1],
            )
            if intersection:
                raise ValidationError(
                    f"The gate line of gates {gates[index].name} and {gates[second_index].name} intersect, which is not "
                    f"allowed. The gates are probably placed too close."
                )


def validate_that_gate_does_not_intersect_corridor(gates: list[Waypoint]):
    projector = Projector(gates[0].latitude, gates[0].longitude)
    for index in range(0, len(gates)):
        previous_left_point = None
        previous_right_point = None
        for second_index in range(0, len(gates)):
            if second_index == index:
                previous_left_point = None
                previous_right_point = None
                continue
            if previous_left_point is None:
                previous_left_point = gates[second_index].left_corridor_line[0]
                previous_right_point = gates[second_index].right_corridor_line[0]
            for corridor_segment_index in range(0, len(gates[second_index].left_corridor_line)):
                left_intersection = projector.intersect(
                    gates[index].gate_line[0],
                    gates[index].gate_line[1],
                    previous_left_point,
                    gates[second_index].left_corridor_line[corridor_segment_index],
                )
                if left_intersection:
                    raise ValidationError(
                        f"The gate line for gate {gates[index].name} intercepts the corridor from the left near gate {gates[second_index].name}"
                    )
                previous_left_point = gates[second_index].left_corridor_line[corridor_segment_index]
            for corridor_segment_index in range(0, len(gates[second_index].right_corridor_line)):
                right_intersection = projector.intersect(
                    gates[index].gate_line[0],
                    gates[index].gate_line[1],
                    previous_right_point,
                    gates[second_index].right_corridor_line[corridor_segment_index],
                )
                if right_intersection:
                    raise ValidationError(
                        f"The gate line for gate {gates[index].name} intercepts the corridor from the right near gate {gates[second_index].name}"
                    )
                previous_right_point = gates[second_index].right_corridor_line[corridor_segment_index]


def load_features_from_kml(input_kml) -> Dict:
    document = open_kml(input_kml)
    if type(document) == str:
        document = document.encode("utf-8")
    print(document)
    kml_document = kml.KML()
    kml_document.from_string(document)
    features = list(kml_document.features())
    place_marks = parse_placemarks(features)
    lines = {}
    for name, mark in place_marks:
        lines[name] = mark
    print(lines)
    return lines


def create_precision_route_from_gpx(file, use_procedure_turns: bool) -> Route:
    gpx = gpxpy.parse(file)
    waypoints = []
    waypoint_map = {}
    landing_gates = []
    takeoff_gates = []
    route_name = ""
    for route in gpx.routes:
        for flightcontest in route.extensions:
            route_extension = flightcontest.find("route")
            if route_extension is not None:
                # print('Route {}:'.format(route.name))
                # for point in route.points:
                # print('Point {3} at ({0},{1}) -> {2}'.format(point.latitude, point.longitude, point.elevation,
                #                                              point.name))
                route_name = route.name
                logger.debug("Loading GPX route {}".format(route_name))
                for point in route.points:
                    waypoint_map[point.name] = Waypoint(point.name)
                    waypoints.append(waypoint_map[point.name])
                    # print("This is route number {}".format(route_extension.attrib["number"]))

    for route in gpx.routes:
        for flightcontest in route.extensions:
            gate_extension = flightcontest.find("gate")
            if gate_extension is not None:
                # print('Route {}:'.format(route.name))
                # for point in route.points:
                #     print('Point {3} at ({0},{1}) -> {2}'.format(point.latitude, point.longitude, point.elevation,
                #                                                  point.name))
                gate_name = route.name
                try:
                    waypoint = waypoint_map[gate_name]
                except KeyError:
                    waypoint = Waypoint(gate_name)
                    waypoint_map[gate_name] = waypoint
                waypoint.gate_line = [
                    (route.points[0].latitude, route.points[0].longitude),
                    (route.points[1].latitude, route.points[1].longitude),
                ]
                waypoint.latitude = float(gate_extension.attrib["lat"])
                waypoint.longitude = float(gate_extension.attrib["lon"])
                waypoint.elevation = float(gate_extension.attrib["alt"])
                waypoint.width = float(gate_extension.attrib["width"])
                waypoint.time_check = gate_extension.attrib["notimecheck"] == "no"
                waypoint.gate_check = gate_extension.attrib["nogatecheck"] == "no"
                waypoint.planning_test = gate_extension.attrib["noplanningtest"] == "no"
                waypoint.end_curved = gate_extension.attrib["endcurved"] == "yes"
                waypoint.type = gate_extension.attrib["type"].lower()
                if waypoint.type == "to":
                    assert not takeoff_gates
                    takeoff_gates = [waypoint]

                if waypoint.type == "ldg":
                    assert not landing_gates
                    landing_gates = [waypoint]
    if len(waypoints) < 2:
        raise ValidationError("A route must at least have a starting point and finish point")
    if waypoints[0].type != "sp":
        raise ValidationError("The first waypoint must be of type starting point")
    if waypoints[-1].type != "fp":
        raise ValidationError("The last waypoint must be of type finish point")

    calculate_and_update_legs(waypoints, use_procedure_turns)
    insert_gate_ranges(waypoints)

    object = Route(
        name=route_name,
        waypoints=waypoints,
        takeoff_gates=takeoff_gates,
        landing_gates=landing_gates,
        use_procedure_turns=use_procedure_turns,
    )
    object.save()
    return object


def calculate_extended_gate(
    waypoint: Waypoint, scorecard: "Scorecard"
) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    return extend_line(
        waypoint.gate_line[0],
        waypoint.gate_line[1],
        max(scorecard.get_extended_gate_width_for_gate_type(waypoint.type), waypoint.width),
    )


def build_waypoint(name, latitude, longitude, type, width, time_check, gate_check):
    waypoint = Waypoint(name)
    waypoint.latitude = latitude
    waypoint.longitude = longitude
    waypoint.type = type
    waypoint.width = max(
        float(width), 0.01
    )  # todo: Enforce at least a minimum gate width in case this has been set to 0
    waypoint.time_check = time_check
    waypoint.gate_check = gate_check
    return waypoint


def extract_additional_features_from_kml_features(features: Dict, route: Route):
    takeoff_gate_line = features.get("to")
    if takeoff_gate_line is not None:
        if len(takeoff_gate_line) != 2:
            raise ValidationError("Take-off gate should have exactly 2 points")
        gate = create_gate_from_line(takeoff_gate_line, "Takeoff", "to")
        gate.gate_line = takeoff_gate_line
        route.takeoff_gates.append(gate)
    landing_gate_line = features.get("ldg")
    if landing_gate_line is not None:
        if len(landing_gate_line) != 2:
            raise ValidationError("Landing gate should have exactly 2 points")
        gate = create_gate_from_line(landing_gate_line, "Landing", "ldg")
        gate.gate_line = landing_gate_line
        route.landing_gates.append(gate)
    route.save()
    # Create prohibited zones
    for name in features.keys():
        try:
            zone_type, zone_name = name.split("_")
            if zone_type in ("prohibited", "info", "penalty", "gate"):
                Prohibited.objects.create(name=zone_name, route=route, path=features[name], type=zone_type)
        except ValueError:
            pass


def create_gate_from_line(gate_line, name: str, type: str) -> Waypoint:
    gate_length = calculate_distance_lat_lon(*gate_line)
    gate_position = calculate_fractional_distance_point_lat_lon(gate_line[0], gate_line[1], 0.5)
    waypoint = build_waypoint(name, gate_position[0], gate_position[1], type, gate_length, True, True)
    waypoint.gate_line = gate_line
    return waypoint


def create_precision_route_from_waypoint_list(
    route_name, waypoint_list, use_procedure_turns: bool, scorecard: Scorecard
) -> Route:
    if len(waypoint_list) < 2:
        raise ValidationError("A route must at least have a starting point and finish point")
    if waypoint_list[0].type != "sp":
        raise ValidationError("The first waypoint must be of type starting point")
    if waypoint_list[-1].type != "fp":
        raise ValidationError("The last waypoint must be of type finish point")
    # First give everything a line according to the  drawn track
    gates = waypoint_list
    for index in range(len(gates) - 1):
        if index < len(gates) - 2 and (gates[index + 1].type == "isp"):
            # or (gates[index].type in ("dummy", "ul") and gates[index + 1].type != "dummy")):
            gates[index + 1].gate_line = create_perpendicular_line_at_end_lonlat(
                gates[index + 2].longitude,
                gates[index + 2].latitude,
                gates[index + 1].longitude,
                gates[index + 1].latitude,
                gates[index + 1].width * 1852,
            )
            gates[index + 1].gate_line.reverse()  # Reverse since created backwards
        else:
            gates[index + 1].gate_line = create_perpendicular_line_at_end_lonlat(
                gates[index].longitude,
                gates[index].latitude,
                gates[index + 1].longitude,
                gates[index + 1].latitude,
                gates[index + 1].width * 1852,
            )
        # Switch from longitude, Latitude tool attitude, longitude
        gates[index + 1].gate_line[0].reverse()
        gates[index + 1].gate_line[1].reverse()
    # Then correct the lines for the actual track
    gates = list(filter(lambda waypoint: waypoint.type != "dummy", waypoint_list))
    for index in range(len(gates) - 1):
        if index < len(gates) - 2 and (gates[index + 1].type == "isp"):
            # or (gates[index].type in ("dummy", "ul") and gates[index + 1].type != "dummy")):
            gates[index + 1].gate_line = create_perpendicular_line_at_end_lonlat(
                gates[index + 2].longitude,
                gates[index + 2].latitude,
                gates[index + 1].longitude,
                gates[index + 1].latitude,
                gates[index + 1].width * 1852,
            )
            gates[index + 1].gate_line.reverse()  # Reverse since created backwards
        else:
            gates[index + 1].gate_line = create_perpendicular_line_at_end_lonlat(
                gates[index].longitude,
                gates[index].latitude,
                gates[index + 1].longitude,
                gates[index + 1].latitude,
                gates[index + 1].width * 1852,
            )
        # Switch from longitude, Latitude tool attitude, longitude
        gates[index + 1].gate_line[0].reverse()
        gates[index + 1].gate_line[1].reverse()

    gates[0].gate_line = create_perpendicular_line_at_end_lonlat(
        gates[1].longitude, gates[1].latitude, gates[0].longitude, gates[0].latitude, gates[0].width * 1852
    )
    gates[0].gate_line[0].reverse()
    gates[0].gate_line[1].reverse()
    # Reverse the line since we have created it in the wrong direction
    gates[0].gate_line.reverse()
    for waypoint in waypoint_list:
        waypoint.gate_line_extended = calculate_extended_gate(waypoint, scorecard)

    # Validate that waypoints are not too close so that the gates cross each other
    validate_no_overlapping_gate_lines(gates)

    calculate_and_update_legs(waypoint_list, use_procedure_turns)
    insert_gate_ranges(waypoint_list)

    instance = Route(name=route_name, waypoints=waypoint_list, use_procedure_turns=use_procedure_turns)
    instance.save()
    return instance


def correct_gate_directions_to_the_right(waypoints: List[Waypoint]):
    """
    Normalise the waypoint order for the gate lines so that they always point right of track

    :param waypoints: List of the waypoints that make up the route
    """
    for waypoint in waypoints:
        if not waypoint.is_gate_line_pointing_right():
            waypoint.gate_line.reverse()
            # Change order of corridor lines
            temp = waypoint.left_corridor_line
            waypoint.left_corridor_line = waypoint.right_corridor_line
            waypoint.right_corridor_line = temp


def create_bisecting_line_between_gates(
    previous_gate: Waypoint, current_gate: Waypoint, next_gate: Waypoint, width_nm: float
) -> List[Tuple[float, float]]:
    line = create_bisecting_line_between_segments_corridor_width_lonlat(
        previous_gate.longitude,
        previous_gate.latitude,
        current_gate.longitude,
        current_gate.latitude,
        next_gate.longitude,
        next_gate.latitude,
        width_nm * 1852,
    )
    # Switch from longitude, latitude to latitude, longitude
    line[0].reverse()
    line[1].reverse()
    return line


def create_perpendicular_line_at_end_gates(
    previous_gate: Waypoint, current_gate: Waypoint, width_nm: float
) -> List[Tuple[float, float]]:
    line = create_perpendicular_line_at_end_lonlat(
        previous_gate.longitude, previous_gate.latitude, current_gate.longitude, current_gate.latitude, width_nm * 1852
    )
    line[0].reverse()
    line[1].reverse()
    return line


def create_anr_corridor_route_from_waypoint_list(
    route_name, waypoint_list: list[Waypoint], rounded_corners: bool, scorecard: Scorecard, corridor_width: float = None
) -> Route:
    """

    :param route_name:
    :param waypoint_list:
    :param rounded_corners:
    :param corridor_width: If this is set, use this for corridor width and leave the gates as they should be
    :return:
    """
    if len(waypoint_list) < 2:
        raise ValidationError("A route must at least have a starting point and finish point")
    if waypoint_list[0].type != "sp":
        raise ValidationError("The first waypoint must be of type starting point")
    if waypoint_list[-1].type != "fp":
        raise ValidationError("The last waypoint must be of type finish point")

    gates = waypoint_list
    for index in range(1, len(gates) - 1):
        gates[index].gate_line = create_bisecting_line_between_gates(
            gates[index - 1], gates[index], gates[index + 1], gates[index].width
        )
        # Fix corridor line
        corridor_line = create_bisecting_line_between_gates(
            gates[index - 1],
            gates[index],
            gates[index + 1],
            corridor_width if corridor_width is not None else gates[index].width,
        )
        # If these are in the wrong order, it will be corrected in "correct_gate_directions_to_the_right"
        gates[index].left_corridor_line = [corridor_line[0]]
        gates[index].right_corridor_line = [corridor_line[1]]

    # Start and finish gates
    gates[0].gate_line = create_perpendicular_line_at_end_gates(gates[1], gates[0], gates[0].width)
    # Reverse the line since we have created it in the wrong direction
    gates[0].gate_line.reverse()
    gates[-1].gate_line = create_perpendicular_line_at_end_gates(gates[-2], gates[-1], gates[-1].width)

    # Fix the corridor line
    # start
    start_corridor_line = create_perpendicular_line_at_end_gates(
        gates[1], gates[0], corridor_width if corridor_width is not None else gates[0].width
    )
    start_corridor_line.reverse()
    gates[0].left_corridor_line = [start_corridor_line[0]]
    gates[0].right_corridor_line = [start_corridor_line[1]]
    # finish
    finish_corridor_line = create_perpendicular_line_at_end_gates(
        gates[-2], gates[-1], corridor_width if corridor_width is not None else gates[-1].width
    )
    gates[-1].left_corridor_line = [finish_corridor_line[0]]
    gates[-1].right_corridor_line = [finish_corridor_line[1]]

    for waypoint in waypoint_list:
        waypoint.gate_line_extended = calculate_extended_gate(waypoint, scorecard)

    # Calculate bearings and distances
    calculate_and_update_legs(waypoint_list, False)
    insert_gate_ranges(waypoint_list)
    correct_gate_directions_to_the_right(waypoint_list)

    # All the gate lines are now in the correct direction, round corners if required
    if rounded_corners:
        for index in range(1, len(gates) - 1):
            waypoint = gates[index]  # type: Waypoint
            # Backup original gate
            waypoint.original_gate_line = waypoint.gate_line
            turn_degrees = bearing_difference(waypoint.bearing_from_previous, waypoint.bearing_next)
            (
                waypoint.left_corridor_line,
                waypoint.right_corridor_line,
                waypoint.gate_line,
            ) = create_rounded_corridor_corner(
                waypoint.gate_line, corridor_width if corridor_width is not None else waypoint.width, turn_degrees
            )

        # correct_distance_and_bearing_for_rounded_corridor(waypoint_list)
    # Validate that waypoints are not too close so that the gates cross each other
    validate_no_overlapping_gate_lines(gates)
    validate_that_gate_does_not_intersect_corridor(gates)
    instance = Route(name=route_name, waypoints=waypoint_list, use_procedure_turns=False)
    instance.rounded_corners = rounded_corners
    if corridor_width is not None:
        instance.corridor_width = corridor_width
    instance.save()
    return instance


def calculate_and_update_legs(waypoints: List[Waypoint], use_procedure_turns: bool):
    # gates = [item for item in waypoints if item.type in ("fp", "sp", "tp", "secret")]  # type: List[Waypoint]
    gates = list(filter(lambda waypoint: waypoint.type not in ("dummy",), waypoints))
    for index in range(0, len(gates) - 1):
        current_gate = gates[index]
        next_gate = gates[index + 1]
        current_gate.distance_next = calculate_distance_lat_lon(
            (current_gate.latitude, current_gate.longitude), (next_gate.latitude, next_gate.longitude)
        )
        current_gate.bearing_next = calculate_bearing(
            (current_gate.latitude, current_gate.longitude), (next_gate.latitude, next_gate.longitude)
        )
    for index in range(1, len(gates)):
        current_gate = gates[index]
        previous_gate = gates[index - 1]
        current_gate.distance_previous = calculate_distance_lat_lon(
            (current_gate.latitude, current_gate.longitude), (previous_gate.latitude, previous_gate.longitude)
        )
        current_gate.bearing_from_previous = calculate_bearing(
            (previous_gate.latitude, previous_gate.longitude), (current_gate.latitude, current_gate.longitude)
        )
        for index in range(0, len(gates) - 1):
            current_gate = gates[index]
            next_gate = gates[index + 1]
            if next_gate.type in ("fp", "ifp", "sp", "isp", "ldg", "ildg"):
                continue
            if use_procedure_turns:
                next_gate.is_procedure_turn = is_procedure_turn(current_gate.bearing_next, next_gate.bearing_next)
            next_gate.is_steep_turn = is_procedure_turn(current_gate.bearing_next, next_gate.bearing_next)


def find_closest_leg_to_point(
    latitude: float, longitude: float, waypoints: List[Waypoint]
) -> tuple[Waypoint, float] | None:
    minimum_distance = None
    leg = None
    for index in range(len(waypoints) - 1):
        distance = point_to_line_segment_distance(
            waypoints[index].latitude,
            waypoints[index].longitude,
            waypoints[index + 1].latitude,
            waypoints[index + 1].longitude,
            latitude,
            longitude,
        )
        logger.debug(f"Minimum distance to {waypoints[index].name} is {distance}")
        if distance is not None:
            if minimum_distance is None:
                minimum_distance = distance
                leg = waypoints[index]
            elif distance < minimum_distance:
                minimum_distance = distance
                leg = waypoints[index]
    if minimum_distance is not None and leg is not None:
        return leg, minimum_distance
    return None


def get_distance_to_other_gates(gate: Waypoint, waypoints: List[Waypoint]) -> Dict:
    distances = {}
    for current_gate in waypoints:
        if gate.name != current_gate.name:
            distances[current_gate.name] = calculate_distance_lat_lon(
                (gate.latitude, gate.longitude), (current_gate.latitude, current_gate.longitude)
            )
    return distances


def insert_gate_ranges(waypoints: List[Waypoint]):
    turning_points = [item for item in waypoints if item.type in ("sp", "fp", "tp")]
    for main_gate in turning_points:
        distances = list(get_distance_to_other_gates(main_gate, turning_points).values())
        minimum_distance = min(min(distances) / 3, 4000)
        main_gate.inside_distance = minimum_distance
        main_gate.outside_distance = 500 + minimum_distance
