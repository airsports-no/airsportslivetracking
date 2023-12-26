from typing import Optional

from django.core.exceptions import ValidationError
from django.db import models

from display.fields.my_pickled_object_field import MyPickledObjectField
from display.waypoint import Waypoint


class Route(models.Model):
    name = models.CharField(max_length=200)
    use_procedure_turns = models.BooleanField(default=True, blank=True)
    rounded_corners = models.BooleanField(default=False, blank=True)
    corridor_width = models.FloatField(default=0.5, blank=True)
    waypoints = MyPickledObjectField(default=list)
    takeoff_gates = MyPickledObjectField(default=list, null=False)
    landing_gates = MyPickledObjectField(default=list, null=False)

    def create_copy(self) -> "Route":
        return Route.objects.create(
            name=self.name,
            use_procedure_turns=self.use_procedure_turns,
            rounded_corners=self.rounded_corners,
            corridor_width=self.corridor_width,
            waypoints=self.waypoints,
            takeoff_gates=self.takeoff_gates,
            landing_gates=self.landing_gates,
        )

    def get_extent(self) -> tuple[float, float, float, float]:
        """
        Returns the  minimum and maximum latitudes and longitudes for all features in the route.

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
            if waypoint.left_corridor_line is not None:
                latitudes.extend([item[0] for item in waypoint.left_corridor_line])
                longitudes.extend([item[1] for item in waypoint.left_corridor_line])
                latitudes.extend([item[0] for item in waypoint.right_corridor_line])
                longitudes.extend([item[1] for item in waypoint.right_corridor_line])
        for prohibited in self.prohibited_set.all():
            latitudes.extend([item[0] for item in prohibited.path])
            longitudes.extend([item[1] for item in prohibited.path])
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
    name = models.CharField(max_length=200)
    route = models.ForeignKey(Route, on_delete=models.CASCADE)
    path = MyPickledObjectField(default=list)  # List of (lat, lon)
    type = models.CharField(max_length=100, blank=True, default="")
    tooltip_position = models.JSONField(null=True, blank=True)

    def copy_to_new_route(self, route):
        return Prohibited.objects.create(
            name=self.name, route=route, path=self.path, type=self.type, tooltip_position=self.tooltip_position
        )
