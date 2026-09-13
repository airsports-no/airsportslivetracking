"""Regression test for Sentry PYTHON-DJANGO-14: plot_editable_route (used to generate an
EditableRoute's preview thumbnail) crashed with IndexError whenever a route's path geometry had
more vertices than named waypoints - the normal case for any curved/multi-point path, not an edge
case. See the matching comment in map_plotter.py for the full explanation.
"""

from django.test import TestCase

from display.flight_order_and_maps.map_plotter import plot_editable_route
from display.models import EditableRoute


class TestPlotEditableRouteThumbnail(TestCase):
    def test_does_not_crash_when_path_has_more_vertices_than_waypoints(self):
        editable_route = EditableRoute.objects.create(
            name="Curved route with extra path vertices",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"featureType": "route_path"},
                        "geometry": {
                            "type": "LineString",
                            # 4 vertices along the path, but only 2 named waypoints below - a
                            # normal shape for a route with intermediate/curve points.
                            "coordinates": [[11.0, 60.0], [11.05, 60.05], [11.1, 60.1], [11.2, 60.2]],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "sp-1", "name": "SP", "pointType": "sp", "featureType": "route_waypoint", "sequence": 0},
                        "geometry": {"type": "Point", "coordinates": [11.0, 60.0]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "fp-1", "name": "FP", "pointType": "fp", "featureType": "route_waypoint", "sequence": 1},
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    },
                ],
            },
        )

        # Must not raise IndexError.
        image_stream = plot_editable_route(editable_route)

        self.assertGreater(len(image_stream.getvalue()), 0)
