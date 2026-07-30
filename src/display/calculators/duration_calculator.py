import datetime

from shapely.geometry import Point, Polygon

from display.calculators.calculator import Calculator, LandingPassedEvent, TakeoffPassedEvent
from display.models import ANOMALY, INFORMATION
from display.calculators.update_score_message import UpdateScoreMessage


class DurationCalculator(Calculator):
    def __init__(self, contestant, scorecard, route, score_processing_queue, live_processing=True, projector=None):
        super().__init__(contestant, scorecard, route, score_processing_queue, live_processing=live_processing, projector=projector)
        self.takeoff_intersection_time = None
        self.scored_duration = False

    def on_takeoff_passed(self, event: TakeoffPassedEvent):
        self.takeoff_intersection_time = event.intersection_time

    def on_landing_passed(self, event: LandingPassedEvent):
        if self.scored_duration or self.takeoff_intersection_time is None:
            return
        self.scored_duration = True
        self.update_score(
            UpdateScoreMessage(
                event.intersection_time,
                event.gate,
                0,
                "airborne duration recorded",
                event.position.latitude,
                event.position.longitude,
                INFORMATION,
                "duration_airborne_time",
                planned=self.takeoff_intersection_time,
                actual=event.intersection_time,
            )
        )
        self._emit_normalized_duration_score(event)
        self._emit_landing_area_penalty(event)

    def _emit_normalized_duration_score(self, event: LandingPassedEvent):
        policy = getattr(self.scorecard, "duration_normalization_policy", "")
        if policy != "raw_minutes":
            return
        duration_seconds = (event.intersection_time - self.takeoff_intersection_time).total_seconds()
        duration_minutes = duration_seconds / 60
        self.update_score(
            UpdateScoreMessage(
                event.intersection_time,
                event.gate,
                duration_minutes,
                "duration normalized using raw minutes",
                event.position.latitude,
                event.position.longitude,
                INFORMATION,
                "duration_normalized_score",
                planned=self.takeoff_intersection_time,
                actual=event.intersection_time,
            )
        )

    def _emit_landing_area_penalty(self, event: LandingPassedEvent):
        editable_route = self.contestant.navigation_task.editable_route
        if editable_route is None:
            return
        polygons = editable_route.get_duration_landing_area_polygons()
        if not polygons:
            return
        polygon = polygons[0].get("geometry", {}).get("coordinates", [[]])[0]
        if len(polygon) < 3:
            return
        lon = float(event.position.longitude)
        lat = float(event.position.latitude)
        ring = [
            (float(point[0]), float(point[1]))
            for point in (polygon[:-1] if len(polygon) > 1 and polygon[0] == polygon[-1] else polygon)
        ]
        inside = Polygon(ring).covers(Point(lon, lat))
        if inside:
            return
        self.update_score(
            UpdateScoreMessage(
                event.intersection_time,
                event.gate,
                float(self.scorecard.prohibited_zone_penalty),
                "landing outside specified area",
                event.position.latitude,
                event.position.longitude,
                ANOMALY,
                "duration_landing_area_outside",
                planned=self.takeoff_intersection_time,
                actual=event.intersection_time,
            )
        )

    def finalise(self, track):
        return None
