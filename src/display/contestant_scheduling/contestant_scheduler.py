import datetime
import logging
from typing import List, Dict, Tuple, Optional
import numpy as np
import pulp as pulp

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class TeamDefinition:
    def __init__(
        self,
        pk: int,
        flight_time: float,
        tracker_id: str,
        tracker_service: str,
        aircraft_registration: str,
        member1: Optional[int],
        member2: Optional[int],
        frozen: bool,
        start_time: Optional[datetime.datetime],
    ):
        """

        :param pk:
        :param airspeed:
        :param flight_time: decimal_minutes
        :param tracker_id:
        :param tracker_service:
        :param member1: Key of crewmember or None
        :param member2: Key of crewmember or None
        :param aircraft_registration:
        """
        self.pk = pk
        self.flight_time = int(np.ceil(flight_time))
        self.tracker_id = tracker_id
        self.tracker_service = tracker_service
        self.aircraft_registration = aircraft_registration
        self.member1 = member1
        self.member2 = member2
        self.start_time = start_time
        self.start_slot = None
        self.frozen = frozen

    def get_tracker_id(self):
        return f"{self.tracker_id.replace(':', '_')}_{self.tracker_service}"


class Solver:
    def __init__(
        self,
        first_takeoff_time: datetime.datetime,
        contest_duration: int,
        teams: List[TeamDefinition],
        minimum_start_interval: int = 5,
        minimum_finish_interval: int = 5,
        aircraft_switch_time: int = 20,
        tracker_switch_time: int = 5,
        tracker_start_lead_time: int = 0,
        crew_switch_time: int = 20,
        optimise: bool = False,
    ):
        self.first_takeoff_time = first_takeoff_time
        self.teams = teams
        self.team_map = {team.pk: team for team in teams}
        self.optimise = optimise
        self.problem = None
        self.minutes_per_slot = 1
        self.contest_duration = 1440 * 2  # Two days # int(np.ceil(contest_duration / self.minutes_per_slot))
        self.minimum_start_interval = int(np.ceil(minimum_start_interval / self.minutes_per_slot))
        self.minimum_finish_interval = int(np.ceil(minimum_finish_interval / self.minutes_per_slot))
        self.aircraft_switch_time = int(np.ceil(aircraft_switch_time / self.minutes_per_slot))
        self.tracker_switch_time = int(np.ceil(tracker_switch_time / self.minutes_per_slot))
        self.crew_switch_time = int(np.ceil(crew_switch_time / self.minutes_per_slot))
        self.tracker_start_lead_time = int(np.ceil(tracker_start_lead_time / self.minutes_per_slot))
        self.very_large_variable = self.contest_duration**2
        self.optimisation_messages = []

    def time_to_slot(self, takeoff_time: datetime.datetime) -> int:
        return int(((takeoff_time - self.first_takeoff_time).total_seconds() / 60) / self.minutes_per_slot)

    def schedule_teams(self) -> List[TeamDefinition]:
        """

        :return: Dictionary where the keys are team pk and the values are takeoff times
        """
        self.__initiate_problem()
        self.__latest_finish_time_constraints()
        self.__nonoverlapping_aircraft()
        self.__nonoverlapping_trackers()
        self.__minimum_start_interval_between_teams()
        self.__minimum_finish_interval_between_teams()

        self.__create_obvious_solution()
        self.problem.writeLP("problem.lp")
        logger.debug("Running solve")
        # status = self.problem.solve(pulp.SCIP_CMD(timeLimit=600))
        status = self.problem.solve(pulp.PULP_CBC_CMD(maxSeconds=600, warmStart=True))
        # logger.debug(f"Optimisation status {pulp.LpStatus[status]}")
        # status = pulp.LpStatusOptimal
        logger.debug("Solver executed, solution status {}, {}".format(status, pulp.LpStatus[status]))
        logger.debug(f"Objective function value: {pulp.value(self.problem.objective)}")

        self.optimisation_messages.append(
            f"Time from first takeoff to last finish point is {datetime.timedelta(minutes=self.latest_finish_time.value())}"
        )
        if status == pulp.LpStatusOptimal:
            return self.__generate_takeoff_times_from_solution()
        return []

    def __generate_takeoff_times_from_solution(self) -> List[TeamDefinition]:
        for team in self.teams:
            slot = self.start_slot_numbers[f"{team.pk}"].value()
            self.team_map[team.pk].start_time = self.first_takeoff_time + datetime.timedelta(
                minutes=slot * self.minutes_per_slot
            )
            self.team_map[team.pk].start_slot = slot
        self.dump_solution()
        return self.teams

    def dump_solution(self):
        teams = sorted(self.teams, key=lambda t: t.start_slot if t.start_slot else -1)
        for team in teams:
            logger.debug(f"Team {team} will start in slot {team.start_slot} at {team.start_time}")

    def __initiate_problem(self):
        logger.debug("Initiating problem")
        self.problem = pulp.LpProblem("Minimise contest time", pulp.LpMinimize)
        self.start_slot_numbers = pulp.LpVariable.dicts(
            "start_slot_numbers",
            [f"{team.pk}" for team in self.teams],
            lowBound=0,
            upBound=self.contest_duration - min([team.flight_time for team in self.teams]),
            cat=pulp.LpInteger,
        )
        self.aircraft_team_variables = {}
        self.tracker_team_variables = {}
        self.start_after = {}
        for index in range(len(self.teams)):
            team = self.teams[index]
            for other_index in range(index + 1, len(self.teams)):
                other_team = self.teams[other_index]
                if team == other_team:
                    continue
                self.start_after[f"{team.pk}_{other_team.pk}"] = pulp.LpVariable(
                    f"{team.pk}_{other_team.pk}", lowBound=0, upBound=1, cat=pulp.LpInteger
                )

        self.latest_finish_time = pulp.LpVariable(
            "latest_finish_time", lowBound=min([team.flight_time for team in self.teams]), upBound=self.contest_duration
        )

        self.problem += self.latest_finish_time
        # self.problem += 999 * self.latest_finish_time + pulp.lpSum(
        #     [self.start_slot_numbers[f"{team.pk}"] * 1 / team.flight_time for team in self.teams])
        self.problem += pulp.lpSum([self.start_slot_numbers[f"{team.pk}"] * team.flight_time for team in self.teams])

    def __latest_finish_time_constraints(self):
        for team in self.teams:
            self.problem += (
                self.start_slot_numbers[f"{team.pk}"] + team.flight_time - self.latest_finish_time <= 0,
                f"latest_finish_time_{team.pk}",
            )

    def __create_obvious_solution(self):
        overlapping_trackers = {}
        overlapping_aircraft = {}
        overlapping_crew = {}
        for team in self.teams:
            if team.get_tracker_id() not in overlapping_trackers:
                overlapping_trackers[team.get_tracker_id()] = []
            overlapping_trackers[team.get_tracker_id()].append(team)
            if team.aircraft_registration not in overlapping_aircraft:
                overlapping_aircraft[team.aircraft_registration] = []
            overlapping_aircraft[team.aircraft_registration].append(team)
            if team.member1 is not None:
                if team.member1 not in overlapping_crew:
                    overlapping_crew[team.member1] = []
                overlapping_crew[team.member1].append(team)
            if team.member2 is not None:
                if team.member2 not in overlapping_crew:
                    overlapping_crew[team.member2] = []
                overlapping_crew[team.member2].append(team)
        used_teams = set()
        next_aircraft_available = {}
        next_tracker_available = {}
        next_crew_available = {}

        def get_next_possibility_for_team(team, earliest_slot):
            return np.amax(
                [
                    next_crew_available.get(team.member1, earliest_slot),
                    next_crew_available.get(team.member2, earliest_slot),
                    next_tracker_available.get(team.get_tracker_id(), earliest_slot),
                    next_aircraft_available.get(team.aircraft_registration, earliest_slot),
                    earliest_slot,
                ]
            )

        def select_team(team, selected_slot):
            used_teams.add(team)
            latest_finish = selected_slot + team.flight_time
            next_aircraft_available[team.aircraft_registration] = (
                selected_slot + team.flight_time + self.aircraft_switch_time
            )
            next_tracker_available[team.get_tracker_id()] = (
                selected_slot + team.flight_time + self.tracker_switch_time + self.tracker_start_lead_time
            )
            if team.member1 is not None:
                next_crew_available[team.member1] = (
                    selected_slot + team.flight_time + self.crew_switch_time + self.tracker_start_lead_time
                )
            if team.member2 is not None:
                next_crew_available[team.member2] = (
                    selected_slot + team.flight_time + self.crew_switch_time + self.tracker_start_lead_time
                )
            self.start_slot_numbers[f"{team.pk}"].setInitialValue(selected_slot)
            return latest_finish

        for team in self.teams:
            team.priority = (
                len(overlapping_trackers[team.get_tracker_id()])
                * len(overlapping_aircraft[team.aircraft_registration])
                * len(overlapping_crew.get(team.member1, [1]))
                * len(overlapping_crew.get(team.member2, [1]))
            )
            if team.frozen:
                # The team has to have a start time if it is frozen
                select_team(team, self.time_to_slot(team.start_time))

        current_slot = 0
        latest_finish = 0

        while len(used_teams) < len(self.teams):
            found = False
            increment = 0
            sorted_teams = sorted(
                set(self.teams) - used_teams, key=lambda k: (k.priority, -k.flight_time), reverse=True
            )
            while not found:
                for team in sorted_teams:
                    next_available = get_next_possibility_for_team(team, current_slot)
                    local_latest_finish = next_available + team.flight_time
                    while local_latest_finish <= latest_finish:
                        next_available += 1
                        local_latest_finish = next_available + team.flight_time
                    if next_available <= current_slot + increment:
                        found = True
                        latest_finish = select_team(team, next_available)
                        current_slot = next_available + self.minimum_start_interval
                        break
                increment += 1
        if not self.optimise:
            for team in self.teams:
                self.start_slot_numbers[f"{team.pk}"].fixValue()
        self.__initialise_extra_variables(latest_finish)

    def __nonoverlapping_aircraft(self):
        logger.debug("Nonoverlapping aircraft")
        overlapping_aircraft = {}
        for team in self.teams:
            if team.aircraft_registration not in overlapping_aircraft:
                overlapping_aircraft[team.aircraft_registration] = []
            overlapping_aircraft[team.aircraft_registration].append(team)
        for aircraft, teams in overlapping_aircraft.items():
            if len(teams) > 1:
                self.aircraft_team_variables.update(
                    pulp.LpVariable.dicts(
                        "team_aircraft_usage",
                        [f"{team.pk}_{other_team.pk}" for team in teams for other_team in teams],
                        lowBound=0,
                        upBound=1,
                        cat=pulp.LpInteger,
                    )
                )
                for team in teams:
                    # Get slot number of team aircraft usage
                    for other_team in teams:
                        if team != other_team:
                            # Ensure no overlap
                            self.problem += (
                                self.start_slot_numbers[f"{team.pk}"]
                                - self.start_slot_numbers[f"{other_team.pk}"]
                                + team.flight_time
                                + self.aircraft_switch_time
                                - self.very_large_variable * self.aircraft_team_variables[f"{team.pk}_{other_team.pk}"]
                                <= 0,
                                f"team_use_aircraft_before_other_{team.pk}_{other_team.pk}",
                            )
                            # 1 = before
                            self.problem += (
                                self.start_slot_numbers[f"{other_team.pk}"]
                                - self.start_slot_numbers[f"{team.pk}"]
                                + other_team.flight_time
                                + self.aircraft_switch_time
                                - self.very_large_variable
                                * (1 - self.aircraft_team_variables[f"{team.pk}_{other_team.pk}"])
                                <= 0,
                                f"other_use_aircraft_before_team_{team.pk}_{other_team.pk}",
                            )

    def __initialise_extra_variables(self, latest_finish):
        self.latest_finish_time.setInitialValue(latest_finish)
        for index in range(len(self.teams)):
            team = self.teams[index]
            for other_index in range(index + 1, len(self.teams)):
                other_team = self.teams[other_index]
                if team == other_team:
                    continue
                if self.start_slot_numbers[f"{team.pk}"].value() < self.start_slot_numbers[f"{other_team.pk}"].value():
                    self.start_after[f"{team.pk}_{other_team.pk}"].setInitialValue(0)
                else:
                    self.start_after[f"{team.pk}_{other_team.pk}"].setInitialValue(1)
        for name, parameter in self.aircraft_team_variables.items():
            team, other_team = name.split("_")
            if self.start_slot_numbers[f"{team}"].value() < self.start_slot_numbers[f"{other_team}"].value():
                self.aircraft_team_variables[name].setInitialValue(0)
            else:
                self.aircraft_team_variables[name].setInitialValue(1)
        for name, parameter in self.tracker_team_variables.items():
            team, other_team = name.split("_")
            if self.start_slot_numbers[f"{team}"].value() < self.start_slot_numbers[f"{other_team}"].value():
                self.tracker_team_variables[name].setInitialValue(0)
            else:
                self.tracker_team_variables[name].setInitialValue(1)

    def __nonoverlapping_trackers(self):
        logger.debug("Nonoverlapping trackers")
        overlapping_trackers = {}
        for team in self.teams:
            if team.aircraft_registration not in overlapping_trackers:
                overlapping_trackers[team.get_tracker_id()] = []
            overlapping_trackers[team.get_tracker_id()].append(team)
        for tracker, teams in overlapping_trackers.items():
            if len(teams) > 1:
                self.tracker_team_variables.update(
                    pulp.LpVariable.dicts(
                        "team_tracker_usage",
                        [f"{team.pk}_{other_team.pk}" for team in teams for other_team in teams],
                        lowBound=0,
                        upBound=1,
                        cat=pulp.LpInteger,
                    )
                )
                for team in teams:
                    # Get slot number of team aircraft usage
                    for other_team in teams:
                        if team != other_team:
                            # Ensure no overlap
                            self.problem += (
                                self.start_slot_numbers[f"{team.pk}"]
                                - self.start_slot_numbers[f"{other_team.pk}"]
                                + team.flight_time
                                + self.tracker_switch_time
                                - self.very_large_variable * self.tracker_team_variables[f"{team.pk}_{other_team.pk}"]
                                <= 0,
                                f"team_use_tracker_before_other_{team.pk}_{other_team.pk}",
                            )
                            # 1 = before
                            self.problem += (
                                self.start_slot_numbers[f"{other_team.pk}"]
                                - self.start_slot_numbers[f"{team.pk}"]
                                + other_team.flight_time
                                + self.tracker_switch_time
                                - self.very_large_variable
                                * (1 - self.tracker_team_variables[f"{team.pk}_{other_team.pk}"])
                                <= 0,
                                f"other_use_tracker_before_team_{team.pk}_{other_team.pk}",
                            )

    def __minimum_start_interval_between_teams(self):
        logger.debug("Minimum start interval between teams")
        for index in range(len(self.teams)):
            team = self.teams[index]
            for other_index in range(index + 1, len(self.teams)):
                other_team = self.teams[other_index]
                if team == other_team:
                    continue
                flight_time_difference = team.flight_time - other_team.flight_time
                if flight_time_difference >= self.minimum_start_interval:  # other_team is fastest
                    # 0 = after
                    self.problem += (
                        self.start_slot_numbers[f"{team.pk}"]
                        - self.start_slot_numbers[f"{other_team.pk}"]
                        + flight_time_difference
                        + 1
                        - self.very_large_variable * self.start_after[f"{team.pk}_{other_team.pk}"]
                        <= 0,
                        f"team_start_flight_difference_before_other_{team.pk}_{other_team.pk}",
                    )
                    # 1 = before
                    self.problem += (
                        self.start_slot_numbers[f"{other_team.pk}"]
                        - self.start_slot_numbers[f"{team.pk}"]
                        + self.minimum_start_interval
                        - self.very_large_variable * (1 - self.start_after[f"{team.pk}_{other_team.pk}"])
                        <= 0,
                        f"other_start_immediately_before_team_{team.pk}_{other_team.pk}",
                    )
                elif flight_time_difference <= -self.minimum_start_interval:  # team is fastest
                    flight_time_difference *= -1
                    # 0 = after
                    self.problem += (
                        self.start_slot_numbers[f"{other_team.pk}"]
                        - self.start_slot_numbers[f"{team.pk}"]
                        + flight_time_difference
                        + 1
                        - self.very_large_variable * self.start_after[f"{team.pk}_{other_team.pk}"]
                        <= 0,
                        f"team_start_flight_difference_before_other_{team.pk}_{other_team.pk}",
                    )
                    # 1 = before
                    self.problem += (
                        self.start_slot_numbers[f"{team.pk}"]
                        - self.start_slot_numbers[f"{other_team.pk}"]
                        + self.minimum_start_interval
                        - self.very_large_variable * (1 - self.start_after[f"{team.pk}_{other_team.pk}"])
                        <= 0,
                        f"other_start_immediately_before_team_{team.pk}_{other_team.pk}",
                    )
                else:  # both teams are equally fast
                    # 0 = after
                    self.problem += (
                        self.start_slot_numbers[f"{team.pk}"]
                        - self.start_slot_numbers[f"{other_team.pk}"]
                        + self.minimum_start_interval
                        - self.very_large_variable * self.start_after[f"{team.pk}_{other_team.pk}"]
                        <= 0,
                        f"team_start_flight_difference_before_other_{team.pk}_{other_team.pk}",
                    )
                    # 1 = before
                    self.problem += (
                        self.start_slot_numbers[f"{other_team.pk}"]
                        - self.start_slot_numbers[f"{team.pk}"]
                        + self.minimum_start_interval
                        - self.very_large_variable * (1 - self.start_after[f"{team.pk}_{other_team.pk}"])
                        <= 0,
                        f"other_start_immediately_before_team_{team.pk}_{other_team.pk}",
                    )

    def __minimum_finish_interval_between_teams(self):
        logger.debug("Minimum finish interval between teams")
        for index in range(len(self.teams)):
            team = self.teams[index]
            for other_index in range(index + 1, len(self.teams)):
                other_team = self.teams[other_index]
                if team == other_team:
                    continue
                flight_time_difference = team.flight_time - other_team.flight_time
                if flight_time_difference >= self.minimum_finish_interval:  # other_team is fastest
                    # 0 = after
                    self.problem += (
                        (self.start_slot_numbers[f"{team.pk}"] + team.flight_time)
                        - (self.start_slot_numbers[f"{other_team.pk}"] + other_team.flight_time)
                        + flight_time_difference
                        + 1
                        - self.very_large_variable * self.start_after[f"{team.pk}_{other_team.pk}"]
                        <= 0,
                        f"team_finish_flight_difference_before_other_{team.pk}_{other_team.pk}",
                    )
                    # 1 = before
                    self.problem += (
                        (self.start_slot_numbers[f"{other_team.pk}"] + other_team.flight_time)
                        - (self.start_slot_numbers[f"{team.pk}"] + team.flight_time)
                        + self.minimum_finish_interval
                        - self.very_large_variable * (1 - self.start_after[f"{team.pk}_{other_team.pk}"])
                        <= 0,
                        f"other_finish_immediately_before_team_{team.pk}_{other_team.pk}",
                    )
                elif flight_time_difference <= -self.minimum_finish_interval:  # team is fastest
                    flight_time_difference *= -1
                    # 0 = after
                    self.problem += (
                        (self.start_slot_numbers[f"{other_team.pk}"] + other_team.flight_time)
                        - (self.start_slot_numbers[f"{team.pk}"] + team.flight_time)
                        + flight_time_difference
                        + 1
                        - self.very_large_variable * self.start_after[f"{team.pk}_{other_team.pk}"]
                        <= 0,
                        f"team_finish_flight_difference_before_other_{team.pk}_{other_team.pk}",
                    )
                    # 1 = before
                    self.problem += (
                        (self.start_slot_numbers[f"{team.pk}"] + team.flight_time)
                        - (self.start_slot_numbers[f"{other_team.pk}"] + other_team.flight_time)
                        + self.minimum_finish_interval
                        - self.very_large_variable * (1 - self.start_after[f"{team.pk}_{other_team.pk}"])
                        <= 0,
                        f"other_finish_immediately_before_team_{team.pk}_{other_team.pk}",
                    )
                else:  # both teams are equally fast
                    # We need to keep this in case the finish spacing is larger than the start spacing (although this is unlikely).
                    # 0 = after
                    self.problem += (
                        self.start_slot_numbers[f"{team.pk}"]
                        - self.start_slot_numbers[f"{other_team.pk}"]
                        + self.minimum_finish_interval
                        - self.very_large_variable * self.start_after[f"{team.pk}_{other_team.pk}"]
                        <= 0,
                        f"team_finish_flight_difference_before_other_{team.pk}_{other_team.pk}",
                    )
                    # 1 = before
                    self.problem += (
                        self.start_slot_numbers[f"{other_team.pk}"]
                        - self.start_slot_numbers[f"{team.pk}"]
                        + self.minimum_finish_interval
                        - self.very_large_variable * (1 - self.start_after[f"{team.pk}_{other_team.pk}"])
                        <= 0,
                        f"other_finish_immediately_before_team_{team.pk}_{other_team.pk}",
                    )
