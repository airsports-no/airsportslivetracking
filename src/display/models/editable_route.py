import logging
import typing
from io import BytesIO
from typing import Optional, TextIO

import gpxpy
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models
from django.db.models import QuerySet
from guardian.shortcuts import get_objects_for_user, get_users_with_perms

from display.fields.my_pickled_object_field import MyPickledObjectField
from display.utilities.coordinate_utilities import calculate_distance_lat_lon
from display.utilities.editable_route_utilities import (
    create_track_block,
    create_takeoff_gate,
    create_landing_gate,
    create_prohibited_zone,
    create_information_zone,
    create_penalty_zone,
    create_gate_polygon,
)
from display.utilities.gate_definitions import DUMMY, UNKNOWN_LEG, STARTINGPOINT, FINISHPOINT
from display.utilities.navigation_task_type_definitions import (
    NAVIGATION_TASK_TYPES,
    PRECISION,
    POKER,
    ANR_CORRIDOR,
    AIRSPORTS,
    AIRSPORT_CHALLENGE,
    LANDING,
)

if typing.TYPE_CHECKING:
    from display.models import Scorecard, Route

logger = logging.getLogger(__name__)


class EditableRoute(models.Model):
    """
    Model to hold the routes created by users in the Route editor.
    """

    route_type = models.CharField(
        choices=NAVIGATION_TASK_TYPES, default=PRECISION, max_length=200, help_text="Not used"
    )
    name = models.CharField(max_length=200, help_text="User-friendly name")
    route = MyPickledObjectField(
        default=list,
        help_text="""
    List of route elements. Each route element is a dictionary with the required key "feature_type" which is used to 
    define the kind of route element that is being described. Legal values are: 
    ['track', 'to', 'ldg', 'prohibited_*', 'info_*', 'penalty_*', 'gate_*']. 
    Each element can be included multiple times except for 'track' which can appear at most once.
    """,
    )
    number_of_waypoints = models.IntegerField(default=0)
    route_length = models.FloatField(default=0, help_text="NM")
    thumbnail = models.ImageField(upload_to="route_thumbnails/", blank=True, null=True)

    class Meta:
        ordering = ("name", "pk")

    @classmethod
    def get_for_user(cls, user: User) -> QuerySet:
        return get_objects_for_user(
            user, "display.change_editableroute", klass=EditableRoute, accept_global_perms=False
        )

    @property
    def editors(self) -> list:
        users = get_users_with_perms(self, attach_perms=True)
        return [user for user, permissions in users.items() if "change_editableroute" in permissions]

    def calculate_number_of_waypoints(self):
        if track := self.get_track():
            return len(track["track_points"])
        return 0

    def calculate_route_length(self) -> float:
        """
        Returns the length of the route (m)
        """
        initial_length = 0
        if track := self.get_track():
            path = track["geojson"]["geometry"]["coordinates"]
            for index in range(0, len(path) - 1):
                initial_length += calculate_distance_lat_lon(
                    (path[index][1], path[index][0]), (path[index + 1][1], path[index + 1][0])
                )
        return initial_length

    def create_thumbnail(self) -> BytesIO:
        """
        Finds the smallest Zoom tile and returns this
        """
        from display.flight_order_and_maps.map_plotter import plot_editable_route

        image_stream = plot_editable_route(self)
        return image_stream

    def __str__(self):
        return self.name

    def get_features_type(self, feature_type: str) -> list[dict]:
        return [item for item in self.route if item["feature_type"] == feature_type]

    def get_feature_type(self, feature_type: str) -> Optional[dict]:
        try:
            return self.get_features_type(feature_type)[0]
        except IndexError:
            return None

    def get_track(self) -> Optional[dict]:
        return self.get_feature_type("track")

    def get_takeoff_gates(self) -> list:
        return self.get_features_type("to")

    def get_landing_gates(self) -> list:
        return self.get_features_type("ldg")

    @staticmethod
    def get_feature_coordinates(feature: dict, flip: bool = True) -> list[tuple[float, float]]:
        """
        Switch lon, lat to lat, lon.
        :param feature:
        :return:
        """
        try:
            coordinates = feature["geojson"]["geometry"]["coordinates"]
            if feature["geojson"]["geometry"]["type"] == "Polygon":
                coordinates = coordinates[0]
            if flip:
                return [tuple(reversed(item)) for item in coordinates]
        except KeyError as e:
            raise ValidationError(f"Malformed internal route: {e}")
        return coordinates

    def validate_valid_corridor_route(self, route_type: str):
        """
        Check that there are no unknown leg waypoints or dummy waypoints in the route. Raise ValidationError.
        """
        track = self.get_track()
        if track is None:
            return
        track_points = track.get("track_points", [])
        illegal_points = list(filter(lambda k: k["gateType"] in (DUMMY, UNKNOWN_LEG), track_points))
        if len(illegal_points) > 0:
            raise ValidationError(
                f"Waypoints of type 'dummy' or 'unknown leg' are not allowed for a {route_type} route. Please remove this from your route or choose another task type."
            )

    def create_landing_route(self):
        from display.models import Route

        route = Route.objects.create(name="", waypoints=[], use_procedure_turns=False)
        self.amend_route_with_additional_features(route)
        if route.landing_gates is None:
            raise ValidationError("Route must have a landing gate")
        route.waypoints = route.landing_gates
        route.save()
        return route

    def create_precision_route(self, use_procedure_turns: bool, scorecard: "Scorecard") -> Optional["Route"]:
        """
        Build a Route object self as a precision route using the provided scorecard.
        """
        from display.utilities.route_building_utilities import build_waypoint
        from display.utilities.route_building_utilities import create_precision_route_from_waypoint_list

        track = self.get_track()
        waypoint_list = []
        if track is None:
            return None
        coordinates = self.get_feature_coordinates(track)
        track_points = track["track_points"]
        for index, (latitude, longitude) in enumerate(coordinates):
            item = track_points[index]
            waypoint_list.append(
                build_waypoint(
                    item["name"],
                    latitude,
                    longitude,
                    item["gateType"],
                    item["gateWidth"],
                    item["timeCheck"],
                    item["timeCheck"],  # We do not include gate check in GUI
                )
            )
        route = create_precision_route_from_waypoint_list(track["name"], waypoint_list, use_procedure_turns, scorecard)
        self.amend_route_with_additional_features(route)
        return route

    def create_anr_route(self, rounded_corners: bool, corridor_width: float, scorecard: "Scorecard") -> "Route":
        """
        Build a Route object self as a ANR route using the provided scorecard.
        """
        from display.utilities.route_building_utilities import build_waypoint
        from display.utilities.route_building_utilities import create_anr_corridor_route_from_waypoint_list

        self.validate_valid_corridor_route("ANR")
        track = self.get_track()
        waypoint_list = []
        coordinates = self.get_feature_coordinates(track)
        track_points = track["track_points"]
        for index, (latitude, longitude) in enumerate(coordinates):
            item = track_points[index]
            waypoint_list.append(
                build_waypoint(item["name"], latitude, longitude, "secret", item["gateWidth"], False, False)
            )
        waypoint_list[0].type = STARTINGPOINT
        waypoint_list[0].gate_check = True
        waypoint_list[0].time_check = True
        waypoint_list[0].width = scorecard.get_extended_gate_width_for_gate_type(STARTINGPOINT)

        waypoint_list[-1].type = FINISHPOINT
        waypoint_list[-1].gate_check = True
        waypoint_list[-1].time_check = True
        waypoint_list[-1].width = scorecard.get_extended_gate_width_for_gate_type(FINISHPOINT)

        logger.debug(f"Created waypoints {waypoint_list}")
        route = create_anr_corridor_route_from_waypoint_list(
            track["name"], waypoint_list, rounded_corners, scorecard, corridor_width=corridor_width
        )
        self.amend_route_with_additional_features(route)
        return route

    def create_airsports_route(self, rounded_corners: bool, scorecard: "Scorecard") -> "Route":
        """
        Build a Route object self as a airsports race/challenge route using the provided scorecard.
        """
        from display.utilities.route_building_utilities import build_waypoint
        from display.utilities.route_building_utilities import create_anr_corridor_route_from_waypoint_list

        self.validate_valid_corridor_route("AirSports Challenge and Air Sports Race")

        track = self.get_track()
        waypoint_list = []
        coordinates = self.get_feature_coordinates(track)
        track_points = track["track_points"]
        for index, (latitude, longitude) in enumerate(coordinates):
            item = track_points[index]
            waypoint_list.append(
                build_waypoint(
                    item["name"],
                    latitude,
                    longitude,
                    item["gateType"],
                    item["gateWidth"],
                    item["timeCheck"],
                    item["timeCheck"],
                )
            )
        route = create_anr_corridor_route_from_waypoint_list(track["name"], waypoint_list, rounded_corners, scorecard)
        self.amend_route_with_additional_features(route)
        return route

    def amend_route_with_additional_features(self, route: "Route"):
        """
        Add common elements to the route, specifically information, penalty, prohibitive zones and gate polygons.
        """
        from display.models import Prohibited
        from display.utilities.route_building_utilities import create_gate_from_line

        takeoff_gates = self.get_takeoff_gates()
        for index, takeoff_gate in enumerate(takeoff_gates):
            takeoff_gate_line = self.get_feature_coordinates(takeoff_gate)
            if len(takeoff_gate_line) != 2:
                raise ValidationError("Take-off gate should have exactly 2 points")
            gate = create_gate_from_line(takeoff_gate_line, f"Takeoff {index + 1}", "to")
            gate.gate_line = takeoff_gate_line
            route.takeoff_gates.append(gate)
        landing_gates = self.get_landing_gates()
        for index, landing_gate in enumerate(landing_gates):
            landing_gate_line = self.get_feature_coordinates(landing_gate)
            if len(landing_gate_line) != 2:
                raise ValidationError("Landing gate should have exactly 2 points")
            gate = create_gate_from_line(landing_gate_line, f"Landing {index + 1}", "ldg")
            gate.gate_line = landing_gate_line
            route.landing_gates.append(gate)
        route.save()
        # Create prohibited zones
        for zone_type in ("info", "penalty", "prohibited", "gate"):
            for feature in self.get_features_type(zone_type):
                logger.debug(feature)
                Prohibited.objects.create(
                    name=feature["name"],
                    route=route,
                    path=self.get_feature_coordinates(feature, flip=True),
                    type=zone_type,
                    tooltip_position=feature.get("tooltip_position", []),
                )

    @classmethod
    def _create_route_and_thumbnail(cls, name: str, route: list[dict]) -> "EditableRoute":
        """
        Helper function to create the editable route andgenerate a thumbnail image
        """
        editable_route = EditableRoute.objects.create(name=name, route=route)
        try:
            editable_route.thumbnail.save(
                editable_route.name + "_thumbnail.png",
                ContentFile(editable_route.create_thumbnail().getvalue()),
                save=True,
            )
        except:
            logger.exception("Failed creating editable route thumbnail. Editable route is still created.")
        return editable_route

    def update_thumbnail(self):
        """
        Update the thumbnail image for the editable route.
        """
        try:
            self.thumbnail.save(
                self.name + "_thumbnail.png",
                ContentFile(self.create_thumbnail().getvalue()),
                save=True,
            )
        except:
            logger.exception("Failed updating editable route thumbnail")

    @classmethod
    def create_from_kml(cls, route_name: str, kml_content: TextIO) -> tuple[Optional["EditableRoute"], list[str]]:
        """Create a ediable route from our own kml format."""
        messages = []
        from display.utilities.route_building_utilities import load_features_from_kml

        features = load_features_from_kml(kml_content)
        if "route" not in features:
            messages.append(f"Fatal: Did not find a 'route' element in the KML file")
            return None, messages
        positions = features.get("route", [])
        if len(positions) == 0:
            messages.append(f"Fatal: The provided the route has zero length")
            return None, messages
        track = create_track_block([(item[0], item[1]) for item in positions])
        messages.append(f"Found route with {len(positions)} points")
        route = [track]
        if take_off_gate_line := features.get("to"):
            if len(take_off_gate_line) == 2:
                route.append(create_takeoff_gate([(item[1], item[0]) for item in take_off_gate_line]))
                messages.append("Found takeoff gate")
        if landing_gate_line := features.get("to"):
            if len(landing_gate_line) == 2:
                route.append(create_landing_gate([(item[1], item[0]) for item in landing_gate_line]))
                messages.append("Found landing gate")
        for name in features.keys():
            logger.debug(f"Found feature {name}")
            try:
                zone_type, zone_name = name.split("_")
                if zone_type == "prohibited":
                    route.append(create_prohibited_zone([(item[1], item[0]) for item in features[name]], zone_name))
                if zone_type == "info":
                    route.append(create_information_zone([(item[1], item[0]) for item in features[name]], zone_name))
                if zone_type == "penalty":
                    route.append(create_penalty_zone([(item[1], item[0]) for item in features[name]], zone_name))
                if zone_type == "gate":
                    route.append(create_gate_polygon([(item[1], item[0]) for item in features[name]], zone_name))
                messages.append(f"Found {zone_type} polygon {zone_name}")
            except ValueError:
                pass
        editable_route = cls._create_route_and_thumbnail(route_name, route)
        logger.debug(messages)
        return editable_route, messages

    @classmethod
    def create_from_csv(cls, name: str, csv_content: list[str]) -> tuple[Optional["EditableRoute"], list[str]]:
        """Create a editable route from our own CSV format."""
        messages = []
        positions = []
        gate_widths = []
        names = []
        types = []
        try:
            for line in csv_content:
                line = [item.strip() for item in line.split(",")]
                positions.append((float(line[2]), float(line[1])))  # CSV contains longitude, latitude
                names.append(line[0])
                gate_widths.append(float(line[4]))
                types.append(line[3])
            route = [create_track_block(positions, widths=gate_widths, names=names, types=types)]
            editable_route = cls._create_route_and_thumbnail(name, route)
            return editable_route, messages
        except Exception as ex:
            logger.exception("Failure when creating route from csv")
            messages.append(str(ex))
        return None, messages

    @classmethod
    def create_from_gpx(cls, name: str, gpx_content: bytes) -> tuple[Optional["EditableRoute"], list[str]]:
        """
        Create a route from flight contest GPX format. Note that this does not include the waypoint lines that are
        defined in the GPX file, these will be calculated internally.
        """
        gpx = gpxpy.parse(gpx_content)
        waypoint_order = []
        waypoint_definitions = {}
        my_route = []
        messages = []
        logger.debug(f"Routes {gpx.routes}")
        for route in gpx.routes:
            for extension in route.extensions:
                logger.debug(f'Extension {extension.find("route")}')
                if extension.find("route") is not None:
                    route_name = route.name
                    logger.debug("Loading GPX route {}".format(route_name))
                    for point in route.points:
                        waypoint_order.append(point.name)
                gate_extension = extension.find("gate")
                if gate_extension is not None:
                    gate_name = route.name
                    gate_type = gate_extension.attrib["type"].lower()
                    logger.debug(f"Gate {gate_name} is {gate_type}")
                    if gate_type == "to":
                        my_route.append(
                            create_takeoff_gate(
                                (
                                    (route.points[0].longitude, route.points[0].latitude),
                                    (route.points[1].longitude, route.points[1].latitude),
                                )
                            )
                        )
                        messages.append("Found take-off gate")
                    elif gate_type == "ldg":
                        my_route.append(
                            create_landing_gate(
                                (
                                    (route.points[0].longitude, route.points[0].latitude),
                                    (route.points[1].longitude, route.points[1].latitude),
                                )
                            )
                        )
                        messages.append("Found landing gate")
                    else:
                        waypoint_definitions[gate_name] = {
                            "position": (float(gate_extension.attrib["lat"]), float(gate_extension.attrib["lon"])),
                            "width": float(gate_extension.attrib["width"]),
                            "type": gate_type,
                            "time_check": gate_extension.attrib["notimecheck"] == "no",
                        }
        my_route.append(
            create_track_block(
                [waypoint_definitions[name]["position"] for name in waypoint_order],
                names=waypoint_order,
                types=[waypoint_definitions[name]["type"] for name in waypoint_order],
                widths=[waypoint_definitions[name]["width"] for name in waypoint_order],
            )
        )
        logger.debug(f"Found route with {len(waypoint_order)} gates")
        messages.append(f"Found route with {len(waypoint_order)} gates")
        editable_route = cls._create_route_and_thumbnail(name, my_route)
        return editable_route, messages

    def create_route(
        self, task_type: str, scorecard: "Scorecard", rounded_corners: bool, corridor_width: float
    ) -> "Route":
        if task_type in (PRECISION, POKER):
            use_procedure_turns = scorecard.use_procedure_turns
            route = self.create_precision_route(use_procedure_turns, scorecard)
        elif task_type == ANR_CORRIDOR:
            if rounded_corners is None:
                raise ValidationError(f"Missing 'rounded_corners' for task type {task_type}")
            if corridor_width is None:
                raise ValidationError(f"Missing 'corridor_width' for task type {task_type}")
            route = self.create_anr_route(rounded_corners, corridor_width, scorecard)
        elif task_type in (AIRSPORTS, AIRSPORT_CHALLENGE):
            if rounded_corners is None:
                raise ValidationError(f"Missing 'rounded_corners' for task type {task_type}")
            route = self.create_airsports_route(rounded_corners, scorecard)
        elif task_type == LANDING:
            route = self.create_landing_route()
        else:
            raise ValidationError(f"Unknown task type {task_type}")
        route.validate_gate_polygons()
        return route
