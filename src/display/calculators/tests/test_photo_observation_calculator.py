import math

from django.test import SimpleTestCase

from display.calculators.photo_observation_calculator import (
    calculate_photo_observation,
    estimate_fit_page_scale_thousands,
    metres_per_millimetre,
    project_onto_polyline,
)

# A straight leg heading due north, roughly 11.1 km long (0.1 degrees of latitude)
LEG = [(60.0, 11.0), (60.1, 11.0)]
METRES_PER_DEGREE_LAT = math.radians(1) * 6371008.8


def north_of_start(metres: float, east_metres: float = 0.0):
    lat = 60.0 + metres / METRES_PER_DEGREE_LAT
    lon = 11.0 + east_metres / (METRES_PER_DEGREE_LAT * math.cos(math.radians(60.0)))
    return lat, lon


class ProjectionTestCase(SimpleTestCase):
    def test_distance_along_and_cross_track(self):
        lat, lon = north_of_start(3000, east_metres=400)
        projection = project_onto_polyline(lat, lon, LEG)
        self.assertAlmostEqual(projection.distance_along_m, 3000, delta=1)
        self.assertAlmostEqual(projection.cross_track_m, 400, delta=1)
        self.assertAlmostEqual(projection.longitude, 11.0, places=6)

    def test_clamps_beyond_the_ends(self):
        lat, lon = north_of_start(-500)
        self.assertEqual(project_onto_polyline(lat, lon, LEG).distance_along_m, 0)

    def test_distance_accumulates_over_legs(self):
        polyline = [(60.0, 11.0), (60.01, 11.0), (60.01, 11.02)]
        projection = project_onto_polyline(60.01, 11.01, polyline)
        leg_one = METRES_PER_DEGREE_LAT * 0.01
        self.assertEqual(projection.segment_index, 1)
        self.assertGreater(projection.distance_along_m, leg_one)

    def test_distance_does_not_depend_on_query_point(self):
        polyline = [(59.0, 10.0), (60.0, 11.0), (61.0, 12.0)]
        end = polyline[-1]
        far = project_onto_polyline(*end, polyline)
        near = project_onto_polyline(60.99, 11.99, polyline)
        self.assertAlmostEqual(far.distance_along_m, near.distance_along_m, delta=2000)
        self.assertAlmostEqual(
            project_onto_polyline(*polyline[1], polyline).distance_along_m,
            project_onto_polyline(60.0, 11.0000001, polyline).distance_along_m,
            delta=1,
        )


class ScoringTestCase(SimpleTestCase):
    def score(self, user_metres, photo_metres=5000, metres_per_mm=200.0, user_east=0.0):
        user = north_of_start(user_metres, user_east)
        photo = north_of_start(photo_metres, east_metres=150)  # the photo target is beside the track
        return calculate_photo_observation(
            user_latitude=user[0],
            user_longitude=user[1],
            photo_latitude=photo[0],
            photo_longitude=photo[1],
            polyline=LEG,
            metres_per_mm=metres_per_mm,
        )

    def test_metres_per_millimetre_from_scale(self):
        self.assertEqual(metres_per_millimetre(200), 200.0)

    def test_exactly_abeam_scores_full(self):
        result = self.score(5000)
        self.assertTrue(result.scored)
        self.assertAlmostEqual(result.error_mm, 0, places=1)
        self.assertEqual(result.score_fraction, 1.0)

    def test_within_one_millimetre_either_side(self):
        # 1:200,000 -> 1 mm is 200 m
        self.assertEqual(self.score(5000 + 190).score_fraction, 1.0)
        self.assertEqual(self.score(5000 - 190).score_fraction, 1.0)

    def test_beyond_one_millimetre_scores_zero(self):
        result = self.score(5000 + 260)
        self.assertAlmostEqual(result.error_mm, 1.3, delta=0.02)
        self.assertEqual(result.score_fraction, 0.0)

    def test_scale_changes_the_tolerance_in_metres(self):
        # 1:50,000 -> 1 mm is 50 m, so 190 m is nearly four millimetres off
        result = self.score(5000 + 190, metres_per_mm=50.0)
        self.assertAlmostEqual(result.error_mm, 3.8, delta=0.05)
        self.assertEqual(result.score_fraction, 0.0)

    def test_far_from_track_is_out_of_track(self):
        result = self.score(5000, user_east=6000)
        self.assertEqual(result.reason, "out_of_track")
        self.assertEqual(result.score_fraction, 0.0)

    def test_unknown_scale_is_not_scored(self):
        result = self.score(5000, metres_per_mm=None)
        self.assertFalse(result.scored)
        self.assertEqual(result.reason, "map_scale_unknown")

    def test_neighbouring_parallel_leg_does_not_capture_the_position(self):
        # A route that doubles back alongside itself 100 m away
        polyline = [(60.0, 11.0), (60.1, 11.0), (60.1, 11.002), (60.0, 11.002), (60.0, 11.004), (60.1, 11.004)]
        photo = north_of_start(5000)
        user = north_of_start(5000, east_metres=60)
        result = calculate_photo_observation(
            user_latitude=user[0],
            user_longitude=user[1],
            photo_latitude=photo[0],
            photo_longitude=photo[1],
            polyline=polyline,
            metres_per_mm=200.0,
        )
        self.assertEqual(result.photo_projection.segment_index, 0)
        self.assertEqual(result.user_projection.segment_index, 0)


class FitPageScaleTestCase(SimpleTestCase):
    def test_estimate_matches_hand_calculation(self):
        # About 111 km north-south on A4 portrait: 277 mm of usable height
        scale = estimate_fit_page_scale_thousands([(60.0, 11.0), (61.0, 11.0)], "A4", landscape=False)
        self.assertAlmostEqual(scale, 111195 / 277, delta=2)

    def test_degenerate_route(self):
        self.assertIsNone(estimate_fit_page_scale_thousands([(60.0, 11.0)]))
