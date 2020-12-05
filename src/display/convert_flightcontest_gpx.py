# from lxml import etree
import logging
from plistlib import Dict
from typing import List

import gpxpy

from display.coordinate_utilities import extend_line, calculate_distance_lat_lon, calculate_bearing
from display.models import Track, is_procedure_turn, create_perpendicular_line_at_end
from gpxpy.gpx import GPX

from display.waypoint import Waypoint

logger = logging.getLogger(__name__)



def create_track_from_gpx(track_name: str, file) -> Track:
    logger.debug("Loading GPX track {}".format(track_name))
    gpx = gpxpy.parse(file)
    track = []
    waypoint_map = {}
    for route in gpx.routes:
        for flightcontest in route.extensions:
            route_extension = flightcontest.find("route")
            if route_extension is not None:
                # print('Route {}:'.format(route.name))
                # for point in route.points:
                # print('Point {3} at ({0},{1}) -> {2}'.format(point.latitude, point.longitude, point.elevation,
                #                                              point.name))
                for point in route.points:
                    waypoint_map[point.name] = Waypoint(point.name)
                    track.append(waypoint_map[point.name])
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
                waypoint.gate_line_infinite = extend_line(waypoint.gate_line[0], waypoint.gate_line[1], 40)

    calculate_and_update_legs(track)
    insert_gate_ranges(track)

    starting_line = track[0]
    object = Track(name=track_name, waypoints=track, starting_line=starting_line)
    object.save()
    return object


def create_track_from_csv(track_name: str, lines: List[str]) -> Track:
    track = []
    for line in lines:
        line = [item.strip() for item in line.split(",")]
        waypoint = Waypoint(line[0])
        waypoint.latitude = float(line[2])
        waypoint.longitude = float(line[1])
        waypoint.type = line[3]
        waypoint.width = float(line[4])

        waypoint.time_check = True
        waypoint.gate_check = True
        waypoint.planning_test = True
        waypoint.elevation = False
        track.append(waypoint)

    gates = [item for item in track if item.type in ("tp", "secret")]
    for index in range(len(gates) - 1):
        gates[index + 1].gate_line = create_perpendicular_line_at_end(gates[index].longitude,
                                                                      gates[index].latitude,
                                                                      gates[index + 1].longitude,
                                                                      gates[index + 1].latitude,
                                                                      gates[index + 1].width * 1852)
        # Switch from longitude, Latitude tool attitude, longitude
        gates[index + 1].gate_line[0].reverse()
        gates[index + 1].gate_line[1].reverse()
        gates[index + 1].gate_line_infinite = extend_line(gates[index + 1].gate_line[0], gates[index + 1].gate_line[1], 40)

    gates[0].gate_line = create_perpendicular_line_at_end(gates[1].longitude,
                                                          gates[1].latitude,
                                                          gates[0].longitude,
                                                          gates[0].latitude,
                                                          gates[0].width * 1852)
    gates[0].gate_line[0].reverse()
    gates[0].gate_line[1].reverse()
    gates[0].gate_line_infinite = extend_line(gates[0].gate_line[0], gates[0].gate_line[1], 40)

    calculate_and_update_legs(track)
    insert_gate_ranges(track)

    starting_line = track[0]
    object = Track(name=track_name, waypoints=track, starting_line=starting_line)
    object.save()
    return object


def calculate_and_update_legs(waypoints: List[Waypoint]):
    # gates = [item for item in waypoints if item.type in ("fp", "sp", "tp", "secret")]  # type: List[Waypoint]
    gates = waypoints
    for index in range(0, len(gates) - 1):
        current_gate = gates[index]
        next_gate = gates[index + 1]
        current_gate.distance_next = calculate_distance_lat_lon((current_gate.latitude, current_gate.longitude),
                                                                (next_gate.latitude, next_gate.longitude))
        current_gate.bearing_next = calculate_bearing((current_gate.latitude, current_gate.longitude),
                                                      (next_gate.latitude, next_gate.longitude))
    for index in range(0, len(waypoints) - 1):
        current_gate = gates[index]
        next_gate = gates[index + 1]
        next_gate.is_procedure_turn = is_procedure_turn(current_gate.bearing_next,
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
    for main_gate in waypoints:
        distances = list(get_distance_to_other_gates(main_gate, waypoints).values())
        minimum_distance = min(distances)
        main_gate.inside_distance = minimum_distance * 2 / 3
        main_gate.outside_distance = 2000 + minimum_distance * 2 / 3
