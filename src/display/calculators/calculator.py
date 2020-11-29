import logging
import threading
from typing import List, TYPE_CHECKING

from display.calculators.positions_and_gates import Gate, Position
from display.models import ContestantTrack, Contestant

if TYPE_CHECKING:
    from influx_facade import InfluxFacade

logger = logging.getLogger(__name__)


class Calculator(threading.Thread):
    def __init__(self, contestant: "Contestant", influx: "InfluxFacade"):
        super().__init__()
        self.contestant = contestant
        self.influx = influx
        self.gates = []
        self.track = []
        self.score = 0
        self.score_by_gate = {}
        self.score_log = []
        self.process_event = threading.Event()
        self.contestant_track, _ = ContestantTrack.objects.get_or_create(contestant=self.contestant)
        self.scorecard = self.contestant.scorecard
        self.gates = self.create_gates()
        self.outstanding_gates = list(self.gates)
        self.starting_line = Gate(self.contestant.contest.track.starting_line, self.gates[0].expected_time)

    def update_score(self, gate: "Gate", score: float, message: str, latitude: float, longitude: float,
                     annotation_type: str):
        logger.info("UPDATE_SCORE {}: {}".format(self.contestant, message))
        self.score += score
        try:
            self.score_by_gate[gate.name] += score
        except KeyError:
            self.score_by_gate[gate.name] = self.score
        self.influx.add_annotation(self.contestant, latitude, longitude, message, annotation_type,
                                   self.track[-1].time)  # TODO: Annotations with the same time
        self.score_log.append(message)
        self.contestant.contestanttrack.update_score(self.score_by_gate, self.score, self.score_log)

    def create_gates(self) -> List:
        waypoints = self.contestant.contest.track.waypoints
        expected_times = self.contestant.gate_times
        gates = []
        for item in waypoints:
            gates.append(Gate(item, expected_times[item["name"]]))
        return gates

    def add_positions(self, positions):
        self.track.extend([Position(**position) for position in positions])
        self.process_event.set()
