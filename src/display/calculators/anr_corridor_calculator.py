import logging
from typing import TYPE_CHECKING

from display.calculators.calculator_utilities import cross_track_gate
from display.calculators.precision_calculator import PrecisionCalculator
from display.models import Contestant

if TYPE_CHECKING:
    from influx_facade import InfluxFacade

logger = logging.getLogger(__name__)


class AnrCorridorCalculator(PrecisionCalculator):
    """
    Implements https://www.fai.org/sites/default/files/documents/gac_2020_precision_flying_rules_final.pdf
    """
    INSIDE_CORRIDOR = 0
    OUTSIDE_CORRIDOR = 1

    def __init__(self, contestant: "Contestant", influx: "InfluxFacade", live_processing: bool = True):
        super().__init__(contestant, influx, live_processing)
        self.corridor_state = self.INSIDE_CORRIDOR
        self.crossed_outside_time = None

    def calculate_score(self):
        super().calculate_score()
        self.check_outside_corridor()

    def check_outside_corridor(self):
        if self.last_gate and len(self.outstanding_gates) > 0:
            cross_track_distance = cross_track_gate(self.last_gate, self.outstanding_gates[0],
                                                    self.track[-1]) / 1852  # NM
            if cross_track_distance > self.scorecard.get_corridor_width(self.contestant) / 2:
                # We are outside the corridor
                if self.corridor_state == self.INSIDE_CORRIDOR:
                    self.corridor_state = self.OUTSIDE_CORRIDOR
                    self.crossed_outside_time = self.track[-1].time
                if self.crossed_outside_time is not None and (self.track[
                                                                  -1].time - self.crossed_outside_time).total_seconds() > self.scorecard.get_corridor_grace_time(
                    self.contestant):
                    # We have exceeded the grace time. Reset outside time and award penalty
                    self.crossed_outside_time = None
                    self.update_score(self.last_gate,
                                      self.scorecard.get_corridor_outside_penalty(self.contestant),
                                      "outside corridor",
                                      self.track[-1].latitude, self.track[-1].longitude, "anomaly", "outside_corridor",
                                      maximum_score=self.scorecard.get_corridor_outside_maximum_penalty(
                                          self.contestant))
