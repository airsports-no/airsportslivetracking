from typing import Optional

from django.core.exceptions import ValidationError
from django.db import models

from display.fields.my_pickled_object_field import MyPickledObjectField
from display.waypoint import Waypoint


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

    def deep_copy(self) -> "Route":
        clone = Route.objects.get(pk=self.pk)
        clone.pk = None
        clone.id = None
        clone.save()
        for prohibited in self.prohibited_set.all():
            prohibited.pk = None
            prohibited.id = None
            prohibited.route = clone
            prohibited.save()
        for photo in self.photo_set.all():
            photo.pk = None
            photo.id = None
            photo.route = clone
            photo.save()
        for free_waypoint in self.freewaypoint_set.all():
            free_waypoint.pk = None
            free_waypoint.id = None
            free_waypoint.route = clone
            free_waypoint.save()
        return clone

    def get_extent(self) -> tuple[float, float, float, float]:
        """
        Returns the minimum and maximum latitudes and longitudes for all features in the route.

        (minimum_latitude, maximum_latitude, minimum_longitude, maximum_longitude)
        """
        latitudes = []
        longitudes = []
        waypoint: Waypoint
        for waypoint in self.waypoints:
            latitudes.append(waypoint.latitude)
            longitudes.append(waypoint.longitude)
            latitudes.append(waypoint.gate_line[0][0])
            latitudes.append(waypoint.gate_line[1][0])
            longitudes.append(waypoint.gate_line[0][1])
            longitudes.append(waypoint.gate_line[1][1])
            latitudes.extend([item[0] for item in waypoint.left_corridor_line])
            longitudes.extend([item[1] for item in waypoint.left_corridor_line])
            latitudes.extend([item[0] for item in waypoint.right_corridor_line])
            longitudes.extend([item[1] for item in waypoint.right_corridor_line])
        for prohibited in self.prohibited_set.all():
            latitudes.extend([item[0] for item in prohibited.path])
            longitudes.extend([item[1] for item in prohibited.path])
        for free in self.freewaypoint_set.all():
            latitudes.append(free.latitude)
            longitudes.append(free.longitude)
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

    def clean(self):
        return

    def validate_gate_polygons(self):
        """
        Validate that the gate polygons must contain exactly one waypoint
        """
        waypoint_names = [gate.name for gate in self.waypoints if gate.type != "secret"]
        if self.prohibited_set.filter(type="gate"):
            if len(waypoint_names) != len(set(waypoint_names)):
                self.delete()
                raise ValidationError("You cannot have multiple waypoints with the same name if you use gate polygons")
        for gate_polygon in self.prohibited_set.filter(type="gate"):
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

    @property
    def leg(self) -> Waypoint | None:
        from display.utilities.route_building_utilities import find_closest_leg_to_point

        if self._leg is None:
            result = find_closest_leg_to_point(self.latitude, self.longitude, self.route.waypoints)
            if result:
                self._leg = result[0]
                self.save(update_fields=["_leg"])
        return self._leg


class FreeWaypoint(models.Model):
    class WaypointType(models.IntegerChoices):
        WAYPOINT = 1
        CIRCLE_START = 2
        CIRCLE_CENTER = 3

    name = models.CharField(max_length=200)
    route = models.ForeignKey(Route, on_delete=models.CASCADE)
    latitude = models.FloatField()
    longitude = models.FloatField()
    waypoint_type = models.IntegerField(choices=WaypointType)
