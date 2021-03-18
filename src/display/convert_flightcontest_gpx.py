# from lxml import etree
import logging
from plistlib import Dict
from typing import List, Tuple, Optional
from zipfile import ZipFile

import gpxpy
from django.core.exceptions import ValidationError
from fastkml import kml, Placemark
from shapely import geometry

from display.coordinate_utilities import extend_line, calculate_distance_lat_lon, calculate_bearing, \
    create_bisecting_line_between_segments_corridor_width_lonlat, create_perpendicular_line_at_end_lonlat, \
    create_rounded_corridor_corner, bearing_difference, calculate_fractional_distance_point_lat_lon
from display.models import Route, is_procedure_turn, Scorecard, Prohibited
from gpxpy.gpx import GPX

from display.waypoint import Waypoint

logger = logging.getLogger(__name__)


def add_line(place_mark):
    return list(zip(*reversed(place_mark.geometry.xy)))


def add_polygon(place_mark):
    return list(zip(*reversed(place_mark.geometry.exterior.xy)))


def open_kmz(file):
    zip = ZipFile(file)
    for z in zip.filelist:
        print(z)
        if z.filename[-4:] == '.kml':
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
        if isinstance(placemark.geometry, geometry.Point):
            # add_point(placemark)
            pass
        elif isinstance(placemark.geometry, geometry.LineString):
            return add_line(placemark)
        elif isinstance(placemark.geometry, geometry.LinearRing):
            return add_line(placemark)  # LinearRing can be plotted through LineString
        elif isinstance(placemark.geometry, geometry.Polygon):
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


def load_features_from_kml(input_kml) -> Dict:
    document = open_kml(input_kml)
    if type(document) == str:
        document = document.encode('utf-8')
    print(document)
    kml_document = kml.KML()
    kml_document.from_string(document)
    features = list(kml_document.features())
    place_marks = parse_placemarks(features)
    lines = {}
    for name, mark in place_marks:
        lines[name.lower()] = mark
    print(lines)
    return lines


#####  Should not be used anymore
def load_route_points_from_kml(input_kml) -> List[Tuple[float, float, float]]:
    """
    Requires a single place marked with a line string inside the KML file

    :param file:
    :return: List of latitude, longitude, altitude tuples
    """
    document = input_kml.read()
    if type(document) == str:
        document = document.encode('utf-8')
    # print(document)
    kml_document = kml.KML()
    kml_document.from_string(document)
    features = list(kml_document.features())[0]
    # print(features)
    placemark = list(features.features())[0]
    geometry = placemark.geometry
    return list(zip(*reversed(geometry.xy)))


def create_precision_route_from_gpx(file, use_procedure_turns: bool) -> Route:
    gpx = gpxpy.parse(file)
    waypoints = []
    waypoint_map = {}
    landing_gate = None
    takeoff_gate = None
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
                logger.info("Loading GPX route {}".format(route_name))
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
                waypoint.gate_line = [(route.points[0].latitude, route.points[0].longitude),
                                      (route.points[1].latitude, route.points[1].longitude)]
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
                    assert not takeoff_gate
                    takeoff_gate = waypoint

                if waypoint.type == "ldg":
                    assert not landing_gate
                    landing_gate = waypoint
    if len(waypoints) < 2:
        raise ValidationError("A route must at least have a starting point and finish point")
    if waypoints[0].type != "sp":
        raise ValidationError("The first waypoint must be of type starting point")
    if waypoints[-1].type != "fp":
        raise ValidationError("The last waypoint must be of type finish point")

    calculate_and_update_legs(waypoints, use_procedure_turns)
    insert_gate_ranges(waypoints)

    object = Route(name=route_name, waypoints=waypoints, takeoff_gate=takeoff_gate,
                   landing_gate=landing_gate, use_procedure_turns=use_procedure_turns)
    object.save()
    return object


def calculate_extended_gate(waypoint: Waypoint, scorecard: "Scorecard", contestant: "Contestant") -> Tuple[
    Tuple[float, float], Tuple[float, float]]:
    return extend_line(waypoint.gate_line[0], waypoint.gate_line[1],
                       scorecard.get_extended_gate_width_for_gate_type(waypoint.type, contestant))


def build_waypoint(name, latitude, longitude, type, width, time_check, gate_check):
    waypoint = Waypoint(name)
    waypoint.latitude = latitude
    waypoint.longitude = longitude
    waypoint.type = type
    waypoint.width = width
    waypoint.time_check = time_check
    waypoint.gate_check = gate_check
    return waypoint


def extract_additional_features_from_kml_features(features: Dict, route: Route):
    takeoff_gate_line = features.get("to")
    if takeoff_gate_line is not None:
        if len(takeoff_gate_line) != 2:
            raise ValidationError("Take-off gate should have exactly 2 points")
        route.takeoff_gate = create_gate_from_line(takeoff_gate_line, "Takeoff", "to")
        route.takeoff_gate.gate_line = takeoff_gate_line
    landing_gate_line = features.get("ldg")
    if landing_gate_line is not None:
        if len(landing_gate_line) != 2:
            raise ValidationError("Landing gate should have exactly 2 points")
        route.landing_gate = create_gate_from_line(landing_gate_line, "Landing", "ldg")
        route.landing_gate.gate_line = landing_gate_line
    route.save()
    # Create prohibited zones
    for name in features.keys():
        if name.startswith("prohibited_"):
            zone_type, zone_name = name.split("_")
            Prohibited.objects.create(name=zone_name, route=route, path=features[name], type=zone_type)


def create_precision_route_from_formset(route_name, data: Dict, use_procedure_turns: bool,
                                        input_kml: Optional = None) -> Route:
    waypoint_list = []
    for item in data:
        waypoint_list.append(
            build_waypoint(item["name"], item["latitude"], item["longitude"], item["type"], item["width"],
                           item["time_check"], item["gate_check"]))

    route = create_precision_route_from_waypoint_list(route_name, waypoint_list, use_procedure_turns)
    if input_kml is not None:
        features = load_features_from_kml(input_kml)
        extract_additional_features_from_kml_features(features, route)
    return route


def create_gate_from_line(gate_line, name: str, type: str) -> Waypoint:
    gate_length = calculate_distance_lat_lon(*gate_line)
    gate_position = calculate_fractional_distance_point_lat_lon(gate_line[0], gate_line[1], 0.5)
    waypoint = build_waypoint(name, gate_position[0], gate_position[1], type, gate_length, True, True)
    waypoint.gate_line = gate_line
    return waypoint


def create_anr_corridor_route_from_kml(route_name: str, input_kml, corridor_width: float,
                                       rounded_corners: bool) -> Route:
    """
    Generate a route where only the first point and last points have gate and time checks. All other gates are secret
    without gate or tone checks.  Each gate has a width equal
    to the corridor with. Create gate lines that cut the angle of the turn in half.
    """
    waypoint_list = []
    features = load_features_from_kml(input_kml)
    points = features.get("route", [])
    if len(points) < 2:
        raise ValidationError(f"There are not enough waypoints in the file ({len(points)} must be greater than 1)")
    for index, item in enumerate(points):
        waypoint_list.append(
            build_waypoint(f"Waypoint {index}", item[0], item[1], "secret", corridor_width,
                           False, False))
    waypoint_list[0].name = "SP"
    waypoint_list[0].type = "sp"
    waypoint_list[0].gate_check = True
    waypoint_list[0].time_check = True

    waypoint_list[-1].name = "FP"
    waypoint_list[-1].type = "fp"
    waypoint_list[-1].gate_check = True
    waypoint_list[-1].time_check = True
    logger.debug(f"Created waypoints {waypoint_list}")
    route = create_anr_corridor_route_from_waypoint_list(route_name, waypoint_list, rounded_corners)
    extract_additional_features_from_kml_features(features, route)
    return route


def create_landing_line_from_kml(route_name: str, input_kml) -> Route:
    """
    Generate a route where only the first point and last points have gate and time checks. All other gates are secret
    without gate or tone checks.  Each gate has a width equal
    to the corridor with. Create gate lines that cut the angle of the turn in half.
    """
    features = load_features_from_kml(input_kml)
    if "ldg" not in features:
        raise ValidationError("File is missing a 'to' line")
    route = Route.objects.create(name=route_name, waypoints=[], use_procedure_turns=False)
    extract_additional_features_from_kml_features(features, route)
    route.waypoints = [route.landing_gate]
    route.save()
    return route


def create_precision_route_from_csv(route_name: str, lines: List[str], use_procedure_turns: bool) -> Route:
    print("lines: {}".format(lines))
    waypoint_list = []
    for line in lines:
        line = [item.strip() for item in line.split(",")]
        waypoint = Waypoint(line[0])
        waypoint.latitude = float(line[2])
        waypoint.longitude = float(line[1])
        waypoint.type = line[3].strip()
        waypoint.width = float(line[4])
        waypoint.time_check = True
        waypoint.gate_check = True
        waypoint.elevation = False
        waypoint_list.append(waypoint)
    return create_precision_route_from_waypoint_list(route_name, waypoint_list, use_procedure_turns)


def create_precision_route_from_waypoint_list(route_name, waypoint_list, use_procedure_turns: bool) -> Route:
    if len(waypoint_list) < 2:
        raise ValidationError("A route must at least have a starting point and finish point")
    if waypoint_list[0].type != "sp":
        raise ValidationError("The first waypoint must be of type starting point")
    if waypoint_list[-1].type != "fp":
        raise ValidationError("The last waypoint must be of type finish point")
    gates = waypoint_list
    for index in range(len(gates) - 1):
        gates[index + 1].gate_line = create_perpendicular_line_at_end_lonlat(gates[index].longitude,
                                                                             gates[index].latitude,
                                                                             gates[index + 1].longitude,
                                                                             gates[index + 1].latitude,
                                                                             gates[index + 1].width * 1852)
        # Switch from longitude, Latitude tool attitude, longitude
        gates[index + 1].gate_line[0].reverse()
        gates[index + 1].gate_line[1].reverse()

    gates[0].gate_line = create_perpendicular_line_at_end_lonlat(gates[1].longitude,
                                                                 gates[1].latitude,
                                                                 gates[0].longitude,
                                                                 gates[0].latitude,
                                                                 gates[0].width * 1852)
    gates[0].gate_line[0].reverse()
    gates[0].gate_line[1].reverse()
    # Reverse the line since we have created it in the wrong direction
    gates[0].gate_line.reverse()

    calculate_and_update_legs(waypoint_list, use_procedure_turns)
    insert_gate_ranges(waypoint_list)

    instance = Route(name=route_name, waypoints=waypoint_list, use_procedure_turns=use_procedure_turns)
    instance.save()
    return instance


def create_anr_corridor_route_from_waypoint_list(route_name, waypoint_list, rounded_corners: bool) -> Route:
    if len(waypoint_list) < 2:
        raise ValidationError("A route must at least have a starting point and finish point")
    if waypoint_list[0].type != "sp":
        raise ValidationError("The first waypoint must be of type starting point")
    if waypoint_list[-1].type != "fp":
        raise ValidationError("The last waypoint must be of type finish point")

    gates = waypoint_list
    for index in range(1, len(gates) - 1):
        gates[index].gate_line = create_bisecting_line_between_segments_corridor_width_lonlat(
            gates[index - 1].longitude,
            gates[index - 1].latitude,
            gates[index].longitude,
            gates[index].latitude,
            gates[index + 1].longitude,
            gates[index + 1].latitude,
            gates[index].width * 1852)
        # Switch from longitude, Latitude to lattitude, longitude
        gates[index].gate_line[0].reverse()
        gates[index].gate_line[1].reverse()

    gates[0].gate_line = create_perpendicular_line_at_end_lonlat(gates[1].longitude,
                                                                 gates[1].latitude,
                                                                 gates[0].longitude,
                                                                 gates[0].latitude,
                                                                 gates[0].width * 1852)
    gates[0].gate_line[0].reverse()
    gates[0].gate_line[1].reverse()
    # Reverse the line since we have created it in the wrong direction
    gates[0].gate_line.reverse()
    gates[-1].gate_line = create_perpendicular_line_at_end_lonlat(gates[-2].longitude,
                                                                  gates[-2].latitude,
                                                                  gates[-1].longitude,
                                                                  gates[-1].latitude,
                                                                  gates[-1].width * 1852)
    gates[-1].gate_line[0].reverse()
    gates[-1].gate_line[1].reverse()

    # Calculate bearings and distances
    calculate_and_update_legs(waypoint_list, False)
    insert_gate_ranges(waypoint_list)

    # All the gate lines are now in the correct direction, round corners if required
    if rounded_corners:
        for index in range(1, len(gates) - 1):
            waypoint = gates[index]  # type: Waypoint
            turn_degrees = bearing_difference(waypoint.bearing_from_previous, waypoint.bearing_next)
            waypoint.left_corridor_line, waypoint.right_corridor_line = create_rounded_corridor_corner(
                waypoint.gate_line, waypoint.width, turn_degrees)
    correct_distance_and_bearing_for_rounded_corridor(waypoint_list)
    instance = Route(name=route_name, waypoints=waypoint_list, use_procedure_turns=False)
    instance.rounded_corners = rounded_corners
    instance.save()
    return instance


def calculate_and_update_legs(waypoints: List[Waypoint], use_procedure_turns: bool):
    # gates = [item for item in waypoints if item.type in ("fp", "sp", "tp", "secret")]  # type: List[Waypoint]
    gates = waypoints
    for index in range(0, len(gates) - 1):
        current_gate = gates[index]
        next_gate = gates[index + 1]
        current_gate.distance_next = calculate_distance_lat_lon((current_gate.latitude, current_gate.longitude),
                                                                (next_gate.latitude, next_gate.longitude))
        current_gate.bearing_next = calculate_bearing((current_gate.latitude, current_gate.longitude),
                                                      (next_gate.latitude, next_gate.longitude))
    for index in range(1, len(gates)):
        current_gate = gates[index]
        previous_gate = gates[index - 1]
        current_gate.distance_previous = calculate_distance_lat_lon((current_gate.latitude, current_gate.longitude),
                                                                    (previous_gate.latitude, previous_gate.longitude))
        current_gate.bearing_from_previous = calculate_bearing((previous_gate.latitude, previous_gate.longitude),
                                                               (current_gate.latitude, current_gate.longitude))
        for index in range(0, len(waypoints) - 1):
            current_gate = gates[index]
            next_gate = gates[index + 1]
            if next_gate.type in ("fp", "ifp", "sp", "isp", "ldg", "ildg"):
                continue
            if use_procedure_turns:
                next_gate.is_procedure_turn = is_procedure_turn(current_gate.bearing_next,
                                                                next_gate.bearing_next)
            next_gate.is_steep_turn = is_procedure_turn(current_gate.bearing_next,
                                                        next_gate.bearing_next)


def correct_distance_and_bearing_for_rounded_corridor(waypoints: List[Waypoint]):
    """
    Correct distance to next and the bearing to next to take into account the additional distance caused by rounded
    corners
    """
    centre_tracks = []
    for waypoint in waypoints:
        centre_tracks.append(waypoint.get_centre_track_segments())
    for index in range(0, len(waypoints) - 1):
        current_gate = centre_tracks[index]
        next_gate = centre_tracks[index + 1]
        start_index = len(current_gate) // 2
        finish_index = len(next_gate) // 2
        distance = 0
        for track_index in range(start_index, len(current_gate) - 1):
            distance += calculate_distance_lat_lon(current_gate[track_index], current_gate[track_index + 1])
        distance += calculate_distance_lat_lon(current_gate[-1], next_gate[0])
        for track_index in range(0, finish_index):
            distance += calculate_distance_lat_lon(next_gate[track_index], next_gate[track_index + 1])

        waypoints[index].distance_next = distance
        waypoints[index].bearing_next = calculate_bearing(current_gate[-1],
                                                      next_gate[0])
    for index in range(1, len(waypoints)):
        current_gate = waypoints[index]
        previous_gate = waypoints[index - 1]
        current_gate.distance_previous = previous_gate.distance_next
        current_gate.bearing_from_previous = previous_gate.bearing_next


def get_distance_to_other_gates(gate: Waypoint, waypoints: List[Waypoint]) -> Dict:
    distances = {}
    for current_gate in waypoints:
        if gate.name != current_gate.name:
            distances[current_gate.name] = calculate_distance_lat_lon(
                (gate.latitude, gate.longitude),
                (current_gate.latitude, current_gate.longitude))
    return distances


def insert_gate_ranges(waypoints: List[Waypoint]):
    turning_points = [item for item in waypoints if item.type == "tp"]
    for main_gate in turning_points:
        distances = list(get_distance_to_other_gates(main_gate, turning_points).values())
        minimum_distance = min(min(distances) / 3, 4000)
        main_gate.inside_distance = minimum_distance
        main_gate.outside_distance = 500 + minimum_distance
