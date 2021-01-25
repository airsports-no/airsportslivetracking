# from lxml import etree
import logging
from plistlib import Dict
from typing import List, Tuple

import gpxpy
from fastkml import kml

from display.coordinate_utilities import extend_line, calculate_distance_lat_lon, calculate_bearing
from display.models import Route, is_procedure_turn, create_perpendicular_line_at_end, Scorecard
from gpxpy.gpx import GPX

from display.waypoint import Waypoint

logger = logging.getLogger(__name__)


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


def create_precision_route_from_formset(route_name, data: Dict, use_procedure_turns: bool) -> Route:
    waypoint_list = []
    for item in data:
        waypoint_list.append(
            build_waypoint(item["name"], item["latitude"], item["longitude"], item["type"], item["width"],
                           item["time_check"], item["gate_check"]))
    return create_route_from_waypoint_list(route_name, waypoint_list, use_procedure_turns)


def create_anr_corridor_route_from_kml(route_name: str, input_kml) -> Route:
    pass


def create_precision_route_from_csv(route_name: str, lines: List[str], use_procedure_turns: bool) -> Route:
    print("lines: {}".format(lines))
    waypoint_list = []
    for line in lines:
        line = [item.strip() for item in line.split(",")]
        waypoint = Waypoint(line[0])
        waypoint.latitude = float(line[2])
        waypoint.longitude = float(line[1])
        waypoint.type = line[3]
        waypoint.width = float(line[4])
        waypoint.time_check = True
        waypoint.gate_check = True
        waypoint.elevation = False
        waypoint_list.append(waypoint)
    return create_route_from_waypoint_list(route_name, waypoint_list, use_procedure_turns)


def create_route_from_waypoint_list(route_name, waypoint_list, use_procedure_turns: bool) -> Route:
    gates = waypoint_list
    for index in range(len(gates) - 1):
        gates[index + 1].gate_line = create_perpendicular_line_at_end(gates[index].longitude,
                                                                      gates[index].latitude,
                                                                      gates[index + 1].longitude,
                                                                      gates[index + 1].latitude,
                                                                      gates[index + 1].width * 1852)
        # Switch from longitude, Latitude tool attitude, longitude
        gates[index + 1].gate_line[0].reverse()
        gates[index + 1].gate_line[1].reverse()

    gates[0].gate_line = create_perpendicular_line_at_end(gates[1].longitude,
                                                          gates[1].latitude,
                                                          gates[0].longitude,
                                                          gates[0].latitude,
                                                          gates[0].width * 1852)
    gates[0].gate_line[0].reverse()
    gates[0].gate_line[1].reverse()

    calculate_and_update_legs(waypoint_list, use_procedure_turns)
    insert_gate_ranges(waypoint_list)

    object = Route(name=route_name, waypoints=waypoint_list, use_procedure_turns=use_procedure_turns)
    object.save()
    return object


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
        minimum_distance = min(min(distances) / 2, 6000)
        main_gate.inside_distance = minimum_distance
        main_gate.outside_distance = 1000 + minimum_distance
