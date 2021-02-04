import datetime
import logging
from typing import List, Dict, Tuple
import numpy as np
import pulp as pulp

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class TeamDefinition:
    def __init__(self, pk: int, flight_time: float, tracker_id: str, tracker_service: str,
                 aircraft_registration: str):
        """

        :param pk:
        :param airspeed:
        :param flight_time: decimal_minutes
        :param tracker_id:
        :param tracker_service:
        :param aircraft_registration:
        """
        self.pk = pk
        self.flight_time = int(np.ceil(flight_time))
        self.tracker_id = tracker_id
        self.tracker_service = tracker_service
        self.aircraft_registration = aircraft_registration
        self.start_time = None
        self.start_slot = None

    def get_tracker_id(self):
        return f"{self.tracker_id}_{self.tracker_service}"


class Solver:
    def __init__(self, first_takeoff_time: datetime.datetime, contest_duration: int, teams: List[TeamDefinition],
                 minimum_start_interval: int = 5, aircraft_switch_time: int = 0,
                 tracker_switch_time: int = 5, tracker_start_lead_time: int = 0):
        self.contest_duration = contest_duration
        self.first_takeoff_time = first_takeoff_time
        self.teams = teams
        self.team_map = {team.pk: team for team in teams}
        self.problem = None
        self.minimum_start_time = minimum_start_interval
        self.aircraft_switch_time = aircraft_switch_time
        self.tracker_switch_time = tracker_switch_time
        self.tracker_start_lead_time = tracker_start_lead_time

    def schedule_teams(self) -> List[TeamDefinition]:
        """

        :return: Dictionary where the keys are team pk and the values are takeoff times
        """
        self.__initiate_problem()
        self.__invalidate_slots_that_do_not_complete_in_time()
        self.__minimum_start_interval()
        self.__generate_and_group_overlapping_aircraft_slots()
        self.__generate_and_group_overlapping_tracker_slots()
        self.__generate_not_overtaking_constraints()
        self.problem.writeLP("problem.lp")
        logger.info("Running solve")
        status = self.problem.solve()
        logger.info("Solver executed, solution status {}, {}".format(status, pulp.LpStatus[status]))
        if status == pulp.LpStatusOptimal:
            return self.__generate_takeoff_times_from_solution()
        return []

    def __generate_takeoff_times_from_solution(self) -> List[TeamDefinition]:
        for team in self.teams:
            for slot in range(self.contest_duration):
                if self.start_slots[f"{team.pk}_{slot}"].value() == 1.0:
                    logger.info(f"Team {team.pk} is starting in slot {slot}")
                    self.team_map[team.pk].start_time = self.first_takeoff_time + datetime.timedelta(minutes=slot)
                    self.team_map[team.pk].start_slot = slot
        return self.teams

    def __initiate_problem(self):
        logger.info("Initiating problem")
        self.problem = pulp.LpProblem("Minimise contest time", pulp.LpMinimize)
        self.start_slots = pulp.LpVariable.dicts(
            "start_slots",
            [f"{team.pk}_{slot}" for team in self.teams for slot in
             range(self.contest_duration)],
            lowBound=0,
            upBound=1,
            cat=pulp.LpInteger,
        )
        aeroplanes = set([item.aircraft_registration for item in self.teams])
        trackers = set([item.get_tracker_id() for item in self.teams])
        self.aircraft_usage = pulp.LpVariable.dicts(
            "aircraft_busy",
            [f"{aeroplane}_{slot}" for aeroplane in aeroplanes for slot in
             range(self.contest_duration + self.aircraft_switch_time)],
            lowBound=0,
            upBound=1,
            cat=pulp.LpInteger
        )
        self.tracker_usage = pulp.LpVariable.dicts(
            "aircraft_busy",
            [f"{tracker}_{slot}" for tracker in trackers for slot in
             range(self.contest_duration + self.tracker_switch_time)],
            lowBound=0,
            upBound=1,
            cat=pulp.LpInteger
        )
        self.takeoff_slots = pulp.LpVariable.dicts(
            "takeoff_slot",
            [f"{slot}" for slot in
             range(self.contest_duration)],
            lowBound=0,
            upBound=1,
            cat=pulp.LpInteger
        )

        self.start_number = pulp.LpVariable.dicts(
            "start_number",
            [f"{team.pk}" for team in self.teams],
            lowBound=0,
            cat=pulp.LpInteger
        )

        self.finish_number = pulp.LpVariable.dicts(
            "finish_number",
            [f"{team.pk}" for team in self.teams],
            lowBound=0,
            cat=pulp.LpInteger
        )

        self.problem += pulp.lpSum(
            [self.start_slots[f"{team.pk}_{slot}"] * (slot + team.flight_time) for team in self.teams for slot in
             range(self.contest_duration)])

    def __invalidate_slots_that_do_not_complete_in_time(self):
        logger.info("Invalidating slots that are too late")
        for team in self.teams:
            # For all time slots that do not allow finishing before the end of the contest duration, disable them
            for slot in range(self.contest_duration - team.flight_time + 1, self.contest_duration):
                self.problem += self.start_slots[f"{team.pk}_{slot}"] == 0, f"invalid_slot_{team.pk}_{slot}"

    def __generate_and_group_overlapping_aircraft_slots(self):
        logger.info("Avoiding overlapping aircraft slots")
        # Generate nonoverlapping aircraft constraints
        overlapping_aircraft = {}
        for team in self.teams:
            if team.aircraft_registration not in overlapping_aircraft:
                overlapping_aircraft[team.aircraft_registration] = []
            overlapping_aircraft[team.aircraft_registration].append(team)
        for team in self.teams:
            if len(overlapping_aircraft[team.aircraft_registration]) > 0:
                for slot in range(self.contest_duration - team.flight_time):
                    self.problem += pulp.lpSum(
                        self.aircraft_usage[f"{team.aircraft_registration}_{aircraft_slot}"] for aircraft_slot in
                        range(slot + 1, slot + team.flight_time + self.aircraft_switch_time)) + self.aircraft_usage[
                                        f"{team.aircraft_registration}_{slot}"] <= 1, f"aircraft_not_overlapping_with_itself_{team.pk}_{slot}"

        for aircraft, teams in overlapping_aircraft.items():
            for slot in range(self.contest_duration):
                # Only one team can use the aircraft for a single slot
                self.problem += pulp.lpSum(self.start_slots[f"{team.pk}_{slot}"] for team in teams) - \
                                self.aircraft_usage[
                                    f"{aircraft}_{slot}"] == 0, f"aircraft_not_overlapping_multiple_teams_{aircraft}_{slot}"

    def __generate_and_group_overlapping_tracker_slots(self):
        logger.info("Avoiding overlapping tracker slots")
        overlapping_trackers = {}
        for team in self.teams:
            if team.get_tracker_id() not in overlapping_trackers:
                overlapping_trackers[team.get_tracker_id()] = []
            overlapping_trackers[team.get_tracker_id()].append(team)
        for team in self.teams:
            if len(overlapping_trackers[team.get_tracker_id()]) > 1:
                # Overlapping with itself is not an issue when it has a single usage
                for slot in range(self.contest_duration - team.flight_time):
                    self.problem += pulp.lpSum(
                        self.tracker_usage[f"{team.get_tracker_id()}_{tracker_slot}"] for tracker_slot in
                        range(max(0, slot - self.tracker_start_lead_time),
                              slot + team.flight_time + self.tracker_switch_time)) <= 1, f"tracker_not_overlapping_with_itself_{team.pk}_{slot}"

        for tracker, teams in overlapping_trackers.items():
            for slot in range(self.contest_duration):
                # Only one team can use the tracker for a single slot
                self.problem += pulp.lpSum(self.start_slots[f"{team.pk}_{slot}"] for team in teams) - \
                                self.tracker_usage[
                                    f"{tracker}_{slot}"] == 0, f"tracker_not_overlapping_multiple_teams_{tracker}_{slot}"

    def __generate_not_overtaking_constraints(self):
        logger.info("Avoid overtaking others")
        # Identify all other teams that will finish before this one if started at the same time or later
        for team in self.teams:
            # Only a single start slot for a team
            self.problem += pulp.lpSum(self.start_slots[f"{team.pk}_{slot}"] for slot in range(
                self.contest_duration)) == 1, f"single_start_time_{team.pk}"
            # Get all teams with a shorter flight time
            for other_team in self.teams:
                if team == other_team:
                    continue
                flight_time_difference = team.flight_time - other_team.flight_time + 1  # finish at least one minute later than the other team
                if flight_time_difference > self.minimum_start_time:
                    for start_slot in range(self.contest_duration - flight_time_difference):
                        self.problem += self.start_slots[f"{team.pk}_{start_slot}"] + pulp.lpSum(
                            self.start_slots[f"{other_team.pk}_{possible_slot}"] for possible_slot in
                            range(start_slot + self.minimum_start_time,
                                  flight_time_difference + start_slot,
                                  1)) <= 1, f"no_overtake_{team.pk}_{other_team.pk}_{start_slot}"


    def __minimum_start_interval(self):
        logger.info("Minimum start interval")
        for slot in range(self.contest_duration - self.minimum_start_time):
            self.problem += pulp.lpSum(self.takeoff_slots[f"{takeoff_range}"] for takeoff_range in range(slot,
                                                                                                         slot + self.minimum_start_time)) <= 1, f"takeoff_slot_interval_{slot}"
            self.problem += self.takeoff_slots[f"{slot}"] - pulp.lpSum(
                self.start_slots[f"{team.pk}_{slot}"] for team in self.teams) == 0, f"used_takeoff_slot_{slot}"
