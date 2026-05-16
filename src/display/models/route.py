from typing import Optional

from django.core.exceptions import ValidationError
from django.db import models

from display.fields.my_pickled_object_field import MyPickledObjectField
from display.waypoint import Waypoint


from display.utilities.coordinate_utilities import calculate_distance_lat_lon

class Route(models.Model):
    """
    An internal representation of a route used by the calculators. It is created based on an EditableRoute and depends
    on the navigation task type and scorecard.
    """

    name = models.CharField(max_length=200)
    use_procedure_turns = models.BooleanField(default=True, blank=True)
    rounded_corners = models.BooleanField(default=False, blank=True)
    corridor_width = models.FloatField(default=0.5, blank=True)
    waypoints = MyPickledObjectField(default=list)
    takeoff_gates = MyPickledObjectField(default=list, null=False)
    landing_gates = MyPickledObjectField(default=list, null=False)
    # List of dictionary objects representing the corridor polygon with the keys lat and lng
    corridor_polygon = MyPickledObjectField(default=list, null=False)

    def create_copy(self) -> "Route":
        return Route.objects.create(
            name=self.name,
            use_procedure_turns=self.use_procedure_turns,
            rounded_corners=self.rounded_corners,
            corridor_width=self.corridor_width,
            waypoints=self.waypoints,
            takeoff_gates=self.takeoff_gates,
            landing_gates=self.landing_gates,
            corridor_polygon=self.corridor_polygon,
        )

    def get_extent(self) -> tuple[float, float, float, float]:
        """
        Returns the minimum and maximum latitudes and longitudes for all features in the route.

        (minimum_latitude, maximum_latitude, minimum_longitude, maximum_longitude)
        """
        latitudes = []
        longitudes = []
        for waypoint in self.waypoints:  # type: Waypoint
            latitudes.append(waypoint.latitude)
            longitudes.append(waypoint.longitude)
            latitudes.append(waypoint.gate_line[0][0])
            latitudes.append(waypoint.gate_line[1][0])
            longitudes.append(waypoint.gate_line[0][1])
            longitudes.append(waypoint.gate_line[1][1])
        for prohibited in self.prohibited_set.all():
            latitudes.extend([item[1] for item in prohibited.path])
            longitudes.extend([item[0] for item in prohibited.path])
        return min(latitudes), max(latitudes), min(longitudes), max(longitudes)

    @property
    def first_takeoff_gate(self) -> Optional[Waypoint]:
        try:
            return self.takeoff_gates[0]
        except IndexError:
            return None

    @property
    def first_landing_gate(self) -> Optional[Waypoint]:
        try:
            return self.landing_gates[0]
        except IndexError:
            return None

    def get_location(self) -> Optional[tuple[float, float]]:
        """
        Get the approximate location (latitude, longitude) of the route
        """
        if self.waypoints and len(self.waypoints) > 0:
            return self.waypoints[0].latitude, self.waypoints[0].longitude
        if len(self.takeoff_gates) > 0:
            return self.takeoff_gates[0].latitude, self.takeoff_gates[0].longitude
        if len(self.landing_gates) > 0:
            return self.landing_gates[0].latitude, self.landing_gates[0].longitude
        return None

    @property
    def number_of_wayoints(self):
        return len(self.waypoints)

    @property
    def route_length_nm(self):
        total_length_meters = 0.0
        path = [(wp.longitude, wp.latitude) for wp in self.waypoints]

        for index in range(0, len(path) - 1):
            total_length_meters += calculate_distance_lat_lon(
                (path[index][1], path[index][0]),
                (path[index + 1][1], path[index + 1][0])
            )

        return total_length_meters / 1852.0 # Convert meters to nautical miles (1 nautical mile = 1852 meters)

    @property
    def number_of_prohibited_zones(self):
        return self.prohibited_set.filter(type='prohibited').count()

    @property
    def number_of_penalty_zones(self):
        return self.prohibited_set.filter(type='penalty').count()

    @property
    def has_landing_gate(self):
        return len(self.landing_gates) > 0

    @property
    def has_takeoff_gate(self):
        return len(self.takeoff_gates) > 0

    @property
    def number_of_photos(self):
        return self.photo_set.count()



    def clean(self):
        return

    def validate_gate_polygons(self):
        """
        Validate that the gate polygons must contain exactly one waypoint
        """
        waypoint_names = [gate.name for gate in self.waypoints if gate.type != "secret"]
        if self.prohibited_set.filter(type="waypoint"):
            if len(waypoint_names) != len(set(waypoint_names)):
                self.delete()
                raise ValidationError("You cannot have multiple waypoints with the same name if you use gate polygons")
        for gate_polygon in self.prohibited_set.filter(type="waypoint"):
            if gate_polygon.name not in waypoint_names:
                self.delete()
                raise ValidationError(f"Gate polygon '{gate_polygon.name}' is not matched by any turning point names.")

    def __str__(self):
        return self.name


class Prohibited(models.Model):
    """
    Models information, penalty, and prohibited zones, as well as gate polygons.
    """

    name = models.CharField(max_length=200)
    route = models.ForeignKey(Route, on_delete=models.CASCADE)
    path = MyPickledObjectField(default=list)  # List of (lat, lon)
    type = models.CharField(max_length=100, blank=True, default="")
    tooltip_position = models.JSONField(null=True, blank=True)

    def copy_to_new_route(self, route):
        return Prohibited.objects.create(
            name=self.name, route=route, path=self.path, type=self.type, tooltip_position=self.tooltip_position
        )


class Photo(models.Model):
    """Represents photos to be used for observation task"""

    name = models.CharField(max_length=200)
    route = models.ForeignKey(Route, on_delete=models.CASCADE)
    latitude = models.FloatField()
    longitude = models.FloatField()
    _leg = MyPickledObjectField(default=None, null=True)
    file = models.ImageField(upload_to="photos/", null=True, blank=True)

    @property
    def leg(self) -> Waypoint | None:
        from display.utilities.route_building_utilities import find_closest_leg_to_point

        if self._leg is None:
            result = find_closest_leg_to_point(self.latitude, self.longitude, self.route.waypoints)
            if result:
                self._leg = result[0]
                self.save(update_fields=["_leg"])
        return self._leg

    def generate_image(self, force=False):
        if (not self.file or force) and self.route:
            from display.flight_order_and_maps.generate_flight_orders import generate_photo
            from django.core.files import File
            import os
            import logging

            logger = logging.getLogger(__name__)

            # Try to get configuration from navigation task
            try:
                # navigationtask is a OneToOneField on Route
                nav_task = self.route.navigationtask
                config = nav_task.flightorderconfiguration
                meters_across = config.photos_meters_across
                zoom_level = config.photos_zoom_level
            except:
                # Fallback to defaults
                meters_across = 350
                zoom_level = 17

            logger.info(f"Generating image for photo {self.name} at {self.latitude}, {self.longitude}")
            if waypoint := self.leg:
                logger.info(f"Found closest leg {waypoint.name} for photo {self.name}")
                try:
                    temp_file = generate_photo(self, waypoint, meters_across, zoom_level)
                    try:
                        with open(temp_file.name, "rb") as f:
                            self.file.save(f"{self.name}_{self.pk}.png", File(f), save=True)
                        logger.info(f"Successfully saved image for photo {self.name}")
                    finally:
                        if os.path.exists(temp_file.name):
                            os.remove(temp_file.name)
                except Exception as e:
                    logger.exception(f"Failed to generate photo image for {self.name}: {e}")
            else:
                logger.warning(f"Could not find closest leg for photo {self.name} - image generation skipped")
