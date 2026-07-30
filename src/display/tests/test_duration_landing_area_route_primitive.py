from django.test import TestCase

from display.models import EditableRoute


class TestDurationLandingAreaRoutePrimitive(TestCase):
    def test_can_fetch_duration_landing_area_polygons(self):
        editable_route = EditableRoute.objects.create(
            name="Duration Landing Area",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "dla-1",
                            "name": "Duration Landing Area 1",
                            "featureType": "zone",
                            "polygonType": "duration_landing_area",
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[11.0, 60.0], [11.2, 60.0], [11.2, 60.2], [11.0, 60.2], [11.0, 60.0]]],
                        },
                    }
                ],
            },
        )

        result = editable_route.get_duration_landing_area_polygons()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["properties"]["name"], "Duration Landing Area 1")
