import logging
import typing
from io import BytesIO
from typing import Optional, TextIO

from display.waypoint import Waypoint
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
    get_quadratic_bezier_points,
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
    settings = MyPickledObjectField(default=dict, help_text="Settings for the route editor")
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
            return len(track["geometry"]["coordinates"])
        return 0

    def calculate_route_length(self) -> float:
        """
        Returns the length of the route (m)
        """
        initial_length = 0
        if track := self.get_track():
            path = track["geometry"]["coordinates"]
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

        image_stream: BytesIO = plot_editable_route(self)
        return image_stream

    def __str__(self):
        return self.name

    @property
    def validation_errors(self) -> list[str]:
        """
        Returns a list of validation warnings/errors for the route using its default widths.
        """
        return self.get_validation_errors()

    def get_validation_errors(self, corridor_width: Optional[float] = None) -> list[str]:
        """
        Returns a list of validation warnings/errors for the route.
        :param corridor_width: Optional override for corridor width in NM.
        """
        from display.utilities.corridor_renderer import validate_corridor

        errors = []
        waypoint_list = self._create_waypoint_list(corridor_width=corridor_width)
        if waypoint_list:
            errors.extend(validate_corridor(waypoint_list))
        return errors

    def get_features_type(self, feature_type: str) -> list[dict]:
        return [
            item for item in self.route["features"] if item.get("properties", {}).get("featureType") == feature_type
        ]

    def get_feature_type(self, feature_type: str) -> Optional[dict]:
        try:
            return self.get_features_type(feature_type)[0]
        except IndexError:
            return None

    def get_track(self) -> Optional[dict]:
        return self.get_feature_type("route_path")

    def get_track_waypoints(self) -> list[dict]:
        return self.get_features_type("route_waypoint")

    def get_ordered_track_waypoints(self) -> list[dict]:
        """
        Returns track waypoints sorted by their sequence number.
        """
        waypoints = self.get_features_type("route_waypoint")
        return sorted(waypoints, key=lambda x: x["properties"].get("sequence", 0))

    def get_takeoff_gates(self) -> list:
        return self.get_features_type("takeoff_gate")

    def get_landing_gates(self) -> list:
        return self.get_features_type("landing_gate")

    @staticmethod
    def get_feature_coordinates(feature: dict, flip: bool = True) -> list[tuple[float, float]]:
        """
        Switch lon, lat to lat, lon.
        :param feature:
        :return:
        """
        try:
            coordinates = feature["geometry"]["coordinates"]
            if feature["geometry"]["type"] == "Polygon":
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
        track_points = self.get_track_waypoints()
        illegal_points = list(filter(lambda k: k["properties"]["pointType"] in (DUMMY, UNKNOWN_LEG), track_points))
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

    def _create_waypoint_list(
        self,
        precision_mode: bool = False,
        force_secret_type: bool = False,
        override_timing_passing_false: bool = False,
        corridor_width: float | None = None,
    ) -> list[Waypoint]:
        """
        Docstring for _create_waypoint_list

        :param self: Description
        :param precision_mode: Description
        :type precision_mode: bool
        :param force_secret_type: Description
        :type force_secret_type: bool
        :param override_timing_passing_false: Description
        :param corridor_width: Width of the corridor in nautical miles
        :return: Description
        :rtype: list[Any]
        """
        from display.utilities.route_building_utilities import build_waypoint

        track_waypoints = self.get_ordered_track_waypoints()
        if not track_waypoints:
            return []

        waypoint_list = []

        for index, item in enumerate(track_waypoints):
            props = item["properties"]
            lon, lat = item["geometry"]["coordinates"]

            width = corridor_width if corridor_width else props["width"] / 1852

            # Determine type
            point_type = "secret" if force_secret_type else props["pointType"]

            # Determine timing/passing
            if override_timing_passing_false:
                is_timing = False
                is_passing = False
            else:
                is_timing = props["isTiming"]
                is_passing = props["isPassing"]

            # Check for curve from previous point
            if index > 0 and props.get("segmentType") == "curved":
                control_lat = props.get("controlLat")
                control_lng = props.get("controlLng")

                if control_lat:
                    prev_item = track_waypoints[index - 1]
                    prev_lon, prev_lat = prev_item["geometry"]["coordinates"]

                    # Calculate Bezier points
                    num_points = 20
                    intermediate_points = get_quadratic_bezier_points(
                        (prev_lat, prev_lon),
                        (lat, lon),
                        (control_lat, control_lng),
                        num_points=num_points,
                    )

                    # Intermediate points (indices 1 to num_points-1)
                    for i in range(1, num_points):
                        p_lat, p_lon = intermediate_points[i]

                        if precision_mode:
                            w = 0.001
                        else:
                            # Linear interpolation
                            prev_width = prev_item["properties"]["width"] / 1852
                            curr_width = props["width"] / 1852
                            t = i / num_points
                            w = prev_width + (curr_width - prev_width) * t

                        waypoint_list.append(
                            build_waypoint(f"Curve {index}.{i}", p_lat, p_lon, "secret", w, False, False)
                        )

            # Add the current waypoint
            waypoint_list.append(
                build_waypoint(
                    props["name"],
                    lat,
                    lon,
                    point_type,
                    width,
                    is_timing,
                    is_passing,
                    control_latitude=props.get("controlLat"),
                    control_longitude=props.get("controlLng"),
                    end_curved=props.get("segmentType") == "curved",
                )
            )

        return waypoint_list

    def create_precision_route(self, use_procedure_turns: bool, scorecard: "Scorecard") -> Optional["Route"]:
        """
        Build a Route object self as a precision route using the provided scorecard.
        """
        from display.utilities.route_building_utilities import create_precision_route_from_waypoint_list

        waypoint_list = self._create_waypoint_list(precision_mode=True)
        if not waypoint_list:
            return None

        route = create_precision_route_from_waypoint_list(self.name, waypoint_list, use_procedure_turns, scorecard)
        self.amend_route_with_additional_features(route)
        return route

    def create_anr_route(self, rounded_corners: bool, corridor_width: float, scorecard: "Scorecard") -> "Route|None":
        """
        Build a Route object self as a ANR route using the provided scorecard.
        """
        from display.utilities.route_building_utilities import create_anr_corridor_route_from_waypoint_list

        self.validate_valid_corridor_route("ANR")
        waypoint_list = self._create_waypoint_list(
            force_secret_type=True, override_timing_passing_false=True, corridor_width=corridor_width
        )
        if not waypoint_list:
            return None

        waypoint_list[0].type = STARTINGPOINT
        waypoint_list[0].gate_check = True
        waypoint_list[0].time_check = True
        # waypoint_list[0].width = scorecard.get_extended_gate_width_for_gate_type(STARTINGPOINT)

        waypoint_list[-1].type = FINISHPOINT
        waypoint_list[-1].gate_check = True
        waypoint_list[-1].time_check = True
        # waypoint_list[-1].width = scorecard.get_extended_gate_width_for_gate_type(FINISHPOINT)

        logger.debug(f"Created waypoints {waypoint_list}")
        route = create_anr_corridor_route_from_waypoint_list(self.name, waypoint_list, rounded_corners, scorecard)
        self.amend_route_with_additional_features(route)
        return route

    def create_airsports_route(self, rounded_corners: bool, scorecard: "Scorecard") -> "Route|None":
        """
        Build a Route object self as a airsports race/challenge route using the provided scorecard.
        """
        from display.utilities.route_building_utilities import create_anr_corridor_route_from_waypoint_list

        self.validate_valid_corridor_route("AirSports Challenge and Air Sports Race")
        waypoint_list = self._create_waypoint_list()
        if not waypoint_list:
            return None

        route = create_anr_corridor_route_from_waypoint_list(self.name, waypoint_list, rounded_corners, scorecard)
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
        for feature in self.get_features_type("zone"):
            logger.debug(feature)
            Prohibited.objects.create(
                name=feature["properties"]["name"],
                route=route,
                path=self.get_feature_coordinates(feature, flip=False),
                type=feature["properties"]["polygonType"],
                # tooltip_position=feature.get("tooltip_position", []),
            )
        from display.models.route import Photo

        for photo in self.get_features_type("observation_photo"):
            Photo.objects.create(
                name=photo["properties"]["name"],
                route=route,
                latitude=photo["geometry"]["coordinates"][1],
                longitude=photo["geometry"]["coordinates"][0],
            )

    @classmethod
    def _create_route_and_thumbnail(cls, name: str, route: dict) -> "EditableRoute":
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
            messages.append("Fatal: Did not find a 'route' element in the KML file")
            return None, messages
        positions = features.get("route", [])
        if len(positions) == 0:
            messages.append("Fatal: The provided the route has zero length")
            return None, messages

        feature_list = create_track_block([(item[0], item[1]) for item in positions])
        messages.append(f"Found route with {len(positions)} points")

        if take_off_gate_line := features.get("to"):
            if len(take_off_gate_line) == 2:
                feature_list.append(
                    create_takeoff_gate(
                        (
                            (take_off_gate_line[0][1], take_off_gate_line[0][0]),
                            (take_off_gate_line[1][1], take_off_gate_line[1][0]),
                        )
                    )
                )
                messages.append("Found takeoff gate")
        if landing_gate_line := features.get("ldg"):
            if len(landing_gate_line) == 2:
                feature_list.append(
                    create_landing_gate(
                        (
                            (landing_gate_line[0][1], landing_gate_line[0][0]),
                            (landing_gate_line[1][1], landing_gate_line[1][0]),
                        )
                    )
                )
                messages.append("Found landing gate")

        # Map zone types to their creator functions
        zone_creators = {
            "prohibited": create_prohibited_zone,
            "info": create_information_zone,
            "penalty": create_penalty_zone,
            "gate": create_gate_polygon,
        }

        for name in features.keys():
            logger.debug(f"Found feature {name}")
            try:
                zone_type, zone_name = name.split("_", 1)
                if creator := zone_creators.get(zone_type):
                    # Should be lon, lat now.
                    zone_points = [(item[0], item[1]) for item in features[name]]
                    feature_list.append(creator(zone_points, zone_name))
                    messages.append(f"Found {zone_type} polygon {zone_name}")
            except ValueError:
                pass

        route_json = {"type": "FeatureCollection", "features": feature_list}
        editable_route = cls._create_route_and_thumbnail(route_name, route_json)
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
                gate_widths.append(float(line[4]) * 1852)
                types.append(line[3])
            feature_list = create_track_block(positions, widths=gate_widths, names=names, types=types)
            editable_route = cls._create_route_and_thumbnail(
                name, {"type": "FeatureCollection", "features": feature_list}
            )
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
        feature_list = []
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
                        feature_list.append(
                            create_takeoff_gate(
                                (
                                    (route.points[0].latitude, route.points[0].longitude),
                                    (route.points[1].latitude, route.points[1].longitude),
                                )
                            )
                        )
                        messages.append("Found take-off gate")
                    elif gate_type == "ldg":
                        feature_list.append(
                            create_landing_gate(
                                (
                                    (route.points[0].latitude, route.points[0].longitude),
                                    (route.points[1].latitude, route.points[1].longitude),
                                )
                            )
                        )
                        messages.append("Found landing gate")
                    else:
                        waypoint_definitions[gate_name] = {
                            "position": (float(gate_extension.attrib["lat"]), float(gate_extension.attrib["lon"])),
                            "width": float(gate_extension.attrib["width"]) * 1852,
                            "type": gate_type,
                            "time_check": gate_extension.attrib["notimecheck"] == "no",
                        }

        track_features = create_track_block(
            [waypoint_definitions[name]["position"] for name in waypoint_order],
            names=waypoint_order,
            types=[waypoint_definitions[name]["type"] for name in waypoint_order],
            widths=[waypoint_definitions[name]["width"] for name in waypoint_order],
        )
        feature_list.extend(track_features)
        logger.debug(f"Found route with {len(waypoint_order)} gates")
        messages.append(f"Found route with {len(waypoint_order)} gates")
        editable_route = cls._create_route_and_thumbnail(name, {"type": "FeatureCollection", "features": feature_list})
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
