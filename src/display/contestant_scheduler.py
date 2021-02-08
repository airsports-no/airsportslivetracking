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
        return f"{self.tracker_id.replace(':', '_')}_{self.tracker_service}"


class Solver:
    def __init__(self, first_takeoff_time: datetime.datetime, contest_duration: int, teams: List[TeamDefinition],
                 minimum_start_interval: int = 5, aircraft_switch_time: int = 0,
                 tracker_switch_time: int = 5, tracker_start_lead_time: int = 0, optimise: bool = False):
        self.first_takeoff_time = first_takeoff_time
        self.teams = teams
        self.team_map = {team.pk: team for team in teams}
        self.optimise = optimise
        self.problem = None
        self.minutes_per_slot = 1
        self.contest_duration = 1440 * 2  # Two days # int(np.ceil(contest_duration / self.minutes_per_slot))
        self.minimum_start_interval = int(np.ceil(minimum_start_interval / self.minutes_per_slot))
        self.aircraft_switch_time = int(np.ceil(aircraft_switch_time / self.minutes_per_slot))
        self.tracker_switch_time = int(np.ceil(tracker_switch_time / self.minutes_per_slot))
        self.tracker_start_lead_time = int(np.ceil(tracker_start_lead_time / self.minutes_per_slot))
        self.very_large_variable = self.contest_duration ** 2

    def schedule_teams(self) -> List[TeamDefinition]:
        """

        :return: Dictionary where the keys are team pk and the values are takeoff times
        """
        self.__initiate_problem()
        # self.__invalidate_slots_that_do_not_complete_in_time()
        # self.__minimum_start_interval()
        self.__latest_finish_time_constraints()
        # self.__unique_start_slot()
        # self.__one_and_only_one_start_time()
        # self.__generate_and_group_overlapping_aircraft_slots()
        self.__nonoverlapping_aircraft()
        self.__nonoverlapping_trackers()
        # self.__generate_and_group_overlapping_tracker_slots()
        self.__minimum_interval_between_teams()

        self.__create_obvious_solution()
        # self.__generate_not_overtaking_constraints()
        # self.__equal_start_and_finish_before()
        self.problem.writeLP("problem.lp")
        logger.info("Running solve")
        # status = self.problem.solve(pulp.SCIP_CMD(timeLimit=600))
        status = self.problem.solve(pulp.PULP_CBC_CMD(maxSeconds=600, warmStart=True))
        status = pulp.LpStatusOptimal
        logger.info("Solver executed, solution status {}, {}".format(status, pulp.LpStatus[status]))
        logger.info(f"Objective function value: {pulp.value(self.problem.objective)}")
        if status == pulp.LpStatusOptimal:
            return self.__generate_takeoff_times_from_solution()
        return []

    def __generate_takeoff_times_from_solution(self) -> List[TeamDefinition]:
        for team in self.teams:
            slot = self.start_slot_numbers[f"{team.pk}"].value()
            self.team_map[team.pk].start_time = self.first_takeoff_time + datetime.timedelta(
                minutes=slot * self.minutes_per_slot)
            self.team_map[team.pk].start_slot = slot
        return self.teams

    def __initiate_problem(self):
        logger.info("Initiating problem")
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
            # self.problem += self.start_slot_number[f"{team.pk}"] - pulp.lpSum(
            #     self.start_slots[f"{team.pk}_{slot}"] * slot for slot in
            #     range(self.contest_duration - self.minimum_start_interval)) == 0, f"start_slot_number_{team.pk}"
            # Get all teams with a shorter flight time
            for other_index in range(index + 1, len(self.teams)):
                other_team = self.teams[other_index]
                if team == other_team:
                    continue
                self.start_after[f"{team.pk}_{other_team.pk}"] = pulp.LpVariable(f"{team.pk}_{other_team.pk}",
                                                                                 lowBound=0,
                                                                                 upBound=1,
                                                                                 cat=pulp.LpInteger)

        self.latest_finish_time = pulp.LpVariable("latest_finish_time",
                                                  lowBound=min([team.flight_time for team in self.teams]),
                                                  upBound=self.contest_duration)

        self.problem += self.latest_finish_time
        # self.problem += 999 * self.latest_finish_time + pulp.lpSum(
        #     [self.start_slot_numbers[f"{team.pk}"] * 1 / team.flight_time for team in self.teams])
        self.problem += pulp.lpSum(
            [self.start_slot_numbers[f"{team.pk}"] * team.flight_time for team in self.teams])
        # def __invalidate_slots_that_do_not_complete_in_time(self):
        #     logger.info("Invalidating slots that are too late")
        #     for team in self.teams:
        #         # For all time slots that do not allow finishing before the end of the contest duration, disable them
        #         for slot in range(self.contest_duration - team.flight_time + 1, self.contest_duration):
        #             self.problem += self.start_slots[f"{team.pk}_{slot}"] == 0, f"invalid_slot_{team.pk}_{slot}"

    def __latest_finish_time_constraints(self):
        for team in self.teams:
            self.problem += self.start_slot_numbers[
                                f"{team.pk}"] + team.flight_time - self.latest_finish_time <= 0, f"latest_finish_time_{team.pk}"

    def __create_obvious_solution(self):
        overlapping_trackers = {}
        overlapping_aircraft = {}
        for team in self.teams:
            if team.get_tracker_id() not in overlapping_trackers:
                overlapping_trackers[team.get_tracker_id()] = []
            overlapping_trackers[team.get_tracker_id()].append(team)
            if team.aircraft_registration not in overlapping_aircraft:
                overlapping_aircraft[team.aircraft_registration] = []
            overlapping_aircraft[team.aircraft_registration].append(team)
        used_teams = set()
        next_aircraft_available = {}
        next_tracker_available = {}

        def get_next_possibility_for_team(team, earliest_slot):
            return max(next_tracker_available.get(team.get_tracker_id(), earliest_slot), max(earliest_slot,
                                                                                             next_aircraft_available.get(
                                                                                                 team.aircraft_registration,
                                                                                                 earliest_slot)))

        for key, value in overlapping_trackers.items():
            overlapping_trackers[key] = sorted(value, key=lambda k: k.flight_time)

        for key, value in overlapping_aircraft.items():
            overlapping_aircraft[key] = sorted(value, key=lambda k: k.flight_time)

        current_slot = 0
        latest_finish = 0
        while len(used_teams) < len(self.teams):
            used_trackers = set()
            used_aircraft = set()
            initial_aircraft_list = []
            initial_tracker_list = []
            initial_list = []
            for aircraft, teams in overlapping_aircraft.items():
                if len(teams) > 1:
                    for team in teams:
                        if team.aircraft_registration not in used_aircraft and team.get_tracker_id() not in used_trackers and team not in used_teams:
                            initial_aircraft_list.append(team)
                            used_teams.add(team)
                            used_trackers.add(team.get_tracker_id())
                            used_aircraft.add(team.aircraft_registration)
                            overlapping_aircraft[team.aircraft_registration].remove(team)
                            break
            for tracker, teams in overlapping_trackers.items():
                if len(teams) > 1:
                    for team in teams:
                        if team.aircraft_registration not in used_aircraft and team.get_tracker_id() not in used_trackers and team not in used_teams:
                            initial_tracker_list.append(team)
                            used_teams.add(team)
                            used_trackers.add(team.get_tracker_id())
                            used_aircraft.add(team.aircraft_registration)
                            overlapping_trackers[team.get_tracker_id()].remove(team)
                            break
                elif len(teams) == 1 and teams[0] not in used_teams:
                    team = teams[0]
                    initial_list.append(team)
                    used_teams.add(team)
                    used_trackers.add(team.get_tracker_id())
                    used_aircraft.add(team.aircraft_registration)
                    overlapping_trackers[team.get_tracker_id()].remove(team)
            # for team in set(self.teams) - used_teams:
            #     if len(overlapping_aircraft[
            #                team.aircraft_registration]) > 1 and team.aircraft_registration not in used_aircraft and team.get_tracker_id() not in used_trackers:
            #         initial_aircraft_list.append(team)
            #         used_teams.add(team)
            #         used_trackers.add(team.get_tracker_id())
            #         used_aircraft.add(team.aircraft_registration)
            #         overlapping_aircraft[team.aircraft_registration].remove(team)
            #     elif len(overlapping_trackers[
            #                  team.get_tracker_id()]) > 1 and team.aircraft_registration not in used_aircraft and team.get_tracker_id() not in used_trackers:
            #         initial_tracker_list.append(team)
            #         used_teams.add(team)
            #         used_trackers.add(team.get_tracker_id())
            #         used_aircraft.add(team.aircraft_registration)
            #         overlapping_trackers[team.get_tracker_id()].remove(team)
            #     else:
            #         initial_list.append(team)
            #         used_teams.add(team)
            aircraft_list = sorted(initial_aircraft_list,
                                   key=lambda k: (get_next_possibility_for_team(k, 0), k.flight_time))
            tracker_list = sorted(initial_tracker_list,
                                  key=lambda k: (get_next_possibility_for_team(k, 0), k.flight_time))
            single_list = sorted(initial_list, key=lambda k: (get_next_possibility_for_team(k, 0), k.flight_time))
            for team in aircraft_list:
                next_available = get_next_possibility_for_team(team, current_slot)
                local_latest_finish = next_available + team.flight_time
                while local_latest_finish < latest_finish:
                    next_available += self.minimum_start_interval
                    local_latest_finish = next_available + team.flight_time
                latest_finish = next_available + team.flight_time
                next_aircraft_available[
                    team.aircraft_registration] = next_available + team.flight_time + self.aircraft_switch_time
                next_tracker_available[
                    team.get_tracker_id()] = next_available + team.flight_time + self.tracker_switch_time
                self.start_slot_numbers[f"{team.pk}"].setInitialValue(next_available)
                current_slot = next_available + self.minimum_start_interval
            for team in tracker_list:
                next_available = get_next_possibility_for_team(team, current_slot)
                local_latest_finish = next_available + team.flight_time
                while local_latest_finish < latest_finish:
                    next_available += self.minimum_start_interval
                    local_latest_finish = next_available + team.flight_time
                latest_finish = next_available + team.flight_time
                next_aircraft_available[
                    team.aircraft_registration] = next_available + team.flight_time + self.aircraft_switch_time
                next_tracker_available[
                    team.get_tracker_id()] = next_available + team.flight_time + self.tracker_switch_time

                self.start_slot_numbers[f"{team.pk}"].setInitialValue(next_available)
                current_slot = next_available + self.minimum_start_interval
            for team in single_list:
                next_available = get_next_possibility_for_team(team, current_slot)
                local_latest_finish = next_available + team.flight_time
                while local_latest_finish < latest_finish:
                    next_available += self.minimum_start_interval
                    local_latest_finish = next_available + team.flight_time
                latest_finish = next_available + team.flight_time
                next_aircraft_available[
                    team.aircraft_registration] = next_available + team.flight_time + self.aircraft_switch_time
                next_tracker_available[
                    team.get_tracker_id()] = next_available + team.flight_time + self.tracker_switch_time

                self.start_slot_numbers[f"{team.pk}"].setInitialValue(next_available)
                current_slot = next_available + self.minimum_start_interval
        if not self.optimise:
            for team in self.teams:
                self.start_slot_numbers[f"{team.pk}"].fixValue()
        self.__initialise_extra_variables(latest_finish)

    def __nonoverlapping_aircraft(self):
        logger.info("Nonoverlapping aircraft")
        overlapping_aircraft = {}
        for team in self.teams:
            if team.aircraft_registration not in overlapping_aircraft:
                overlapping_aircraft[team.aircraft_registration] = []
            overlapping_aircraft[team.aircraft_registration].append(team)
        for aircraft, teams in overlapping_aircraft.items():
            if len(teams) > 1:
                self.aircraft_team_variables.update(pulp.LpVariable.dicts(
                    "team_aircraft_usage",
                    [f"{team.pk}_{other_team.pk}" for team in teams for other_team in teams],
                    lowBound=0,
                    upBound=1,
                    cat=pulp.LpInteger
                ))
                for team in teams:
                    # Get slot number of team aircraft usage
                    for other_team in teams:
                        if team != other_team:
                            # Ensure no overlap
                            self.problem += self.start_slot_numbers[
                                                f"{team.pk}"] - self.start_slot_numbers[
                                                f"{other_team.pk}"] + team.flight_time + self.aircraft_switch_time - self.very_large_variable * \
                                            self.aircraft_team_variables[
                                                f"{team.pk}_{other_team.pk}"] <= 0, f"team_use_aircraft_before_other_{team.pk}_{other_team.pk}"
                            # 1 = before
                            self.problem += self.start_slot_numbers[
                                                f"{other_team.pk}"] - self.start_slot_numbers[
                                                f"{team.pk}"] + other_team.flight_time + self.aircraft_switch_time - self.very_large_variable * (
                                                    1 - self.aircraft_team_variables[
                                                f"{team.pk}_{other_team.pk}"]) <= 0, f"other_use_aircraft_before_team_{team.pk}_{other_team.pk}"

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
        logger.info("Nonoverlapping trackers")
        overlapping_trackers = {}
        for team in self.teams:
            if team.aircraft_registration not in overlapping_trackers:
                overlapping_trackers[team.get_tracker_id()] = []
            overlapping_trackers[team.get_tracker_id()].append(team)
        for tracker, teams in overlapping_trackers.items():
            if len(teams) > 1:
                self.tracker_team_variables.update(pulp.LpVariable.dicts(
                    "team_tracker_usage",
                    [f"{team.pk}_{other_team.pk}" for team in teams for other_team in teams],
                    lowBound=0,
                    upBound=1,
                    cat=pulp.LpInteger
                ))
                for team in teams:
                    # Get slot number of team aircraft usage
                    for other_team in teams:
                        if team != other_team:
                            # Ensure no overlap
                            self.problem += self.start_slot_numbers[
                                                f"{team.pk}"] - self.start_slot_numbers[
                                                f"{other_team.pk}"] + team.flight_time + self.tracker_switch_time - self.very_large_variable * \
                                            self.tracker_team_variables[
                                                f"{team.pk}_{other_team.pk}"] <= 0, f"team_use_tracker_before_other_{team.pk}_{other_team.pk}"
                            # 1 = before
                            self.problem += self.start_slot_numbers[
                                                f"{other_team.pk}"] - self.start_slot_numbers[
                                                f"{team.pk}"] + other_team.flight_time + self.tracker_switch_time - self.very_large_variable * (
                                                    1 - self.tracker_team_variables[
                                                f"{team.pk}_{other_team.pk}"]) <= 0, f"other_use_tracker_before_team_{team.pk}_{other_team.pk}"

    # def __generate_and_group_overlapping_aircraft_slots(self):
    #     logger.info("Avoiding overlapping aircraft slots")
    #     # Generate nonoverlapping aircraft constraints
    #     overlapping_aircraft = {}
    #     for team in self.teams:
    #         if team.aircraft_registration not in overlapping_aircraft:
    #             overlapping_aircraft[team.aircraft_registration] = []
    #         overlapping_aircraft[team.aircraft_registration].append(team)
    #     for team in self.teams:
    #         if len(overlapping_aircraft[team.aircraft_registration]) > 1:
    #             for slot in range(self.contest_duration - team.flight_time - self.aircraft_switch_time):
    #                 self.problem += pulp.lpSum(
    #                     self.aircraft_usage[f"{team.aircraft_registration}_{aircraft_slot}"] for aircraft_slot in
    #                     range(slot + 1, slot + team.flight_time + self.aircraft_switch_time)) + self.aircraft_usage[
    #                                     f"{team.aircraft_registration}_{slot}"] <= 1, f"aircraft_not_overlapping_with_itself_{team.pk}_{slot}"
    #
    #     for aircraft, teams in overlapping_aircraft.items():
    #         if len(teams) > 1:
    #             for slot in range(self.contest_duration):
    #                 # Only one team can use the aircraft for a single slot
    #                 self.problem += pulp.lpSum(self.start_slots[f"{team.pk}_{slot}"] for team in teams) - \
    #                                 self.aircraft_usage[
    #                                     f"{aircraft}_{slot}"] == 0, f"aircraft_not_overlapping_multiple_teams_{aircraft}_{slot}"

    # def __generate_and_group_overlapping_tracker_slots(self):
    #     logger.info("Avoiding overlapping tracker slots")
    #     overlapping_trackers = {}
    #     for team in self.teams:
    #         if team.get_tracker_id() not in overlapping_trackers:
    #             overlapping_trackers[team.get_tracker_id()] = []
    #         overlapping_trackers[team.get_tracker_id()].append(team)
    #     for team in self.teams:
    #         if len(overlapping_trackers[team.get_tracker_id()]) > 1:
    #             # Overlapping with itself is not an issue when it has a single usage
    #             for slot in range(self.contest_duration - team.flight_time - self.tracker_switch_time):
    #                 self.problem += pulp.lpSum(
    #                     self.tracker_usage[f"{team.get_tracker_id()}_{tracker_slot}"] for tracker_slot in
    #                     range(max(0, slot - self.tracker_start_lead_time),
    #                           slot + team.flight_time + self.tracker_switch_time)) <= 1, f"tracker_not_overlapping_with_itself_{team.pk}_{slot}"
    #
    #     for tracker, teams in overlapping_trackers.items():
    #         if len(teams) > 1:
    #             for slot in range(self.contest_duration):
    #                 # Only one team can use the tracker for a single slot
    #                 self.problem += pulp.lpSum(self.start_slots[f"{team.pk}_{slot}"] for team in teams) - \
    #                                 self.tracker_usage[
    #                                     f"{tracker}_{slot}"] == 0, f"tracker_not_overlapping_multiple_teams_{tracker}_{slot}"

    # def __one_and_only_one_start_time(self):
    #     for team in self.teams:
    #         # Only a single start slot for a team
    #         self.problem += pulp.lpSum(self.start_slots[f"{team.pk}_{slot}"] for slot in range(
    #             self.contest_duration)) == 1, f"single_start_time_{team.pk}"

    # def __generate_not_overtaking_constraints(self):
    #     logger.info("Avoid overtaking others")
    #     # Identify all other teams that will finish before this one if started at the same time or later
    #     for team in self.teams:
    #         # Get all teams with a shorter flight time
    #         for other_team in self.teams:
    #             if team == other_team:
    #                 continue
    #             flight_time_difference = team.flight_time - other_team.flight_time + 1
    #             if flight_time_difference > self.minimum_start_interval:
    #                 for start_slot in range(self.contest_duration - flight_time_difference):
    #                     self.problem += self.start_slots[f"{team.pk}_{start_slot}"] + pulp.lpSum(
    #                         self.start_slots[f"{other_team.pk}_{possible_slot}"] for possible_slot in
    #                         range(start_slot + self.minimum_start_interval,
    #                               flight_time_difference + start_slot,
    #                               1)) <= 1, f"no_overtake_{team.pk}_{other_team.pk}_{start_slot}"

    # def __unique_start_slot(self):
    #     for slot in range(self.contest_duration - self.minimum_start_interval):
    #         self.problem += pulp.lpSum(
    #             self.start_slots[f"{team.pk}_{slot}"] for team in self.teams) <= 1, f"single_start_{slot}"

    # def __start_and_finish_slot_numbers(self):
    #     for team in self.teams:
    #         self.problem += self.start_slot_number[f"{team.pk}"] - pulp.lpSum(
    #             self.start_slots[f"{team.pk}_{slot}"] * slot for slot in
    #             range(self.contest_duration - self.minimum_start_interval)) == 0, f"start_slot_number_{team.pk}"
    #         # self.problem += self.finish_number[f"team.pk"] - pulp.lpSum(
    #         #     self.finish_slots[f"{team.pk}_{slot}"] * slot for slot in
    #         #     range(self.contest_duration )), f"finish_number_{team.pk}"

    def __minimum_interval_between_teams(self):
        logger.info("Minimum interval between teams")
        # self.__combined_finish_slot_with_start_slot()
        # self.__start_and_finish_slot_numbers()
        for index in range(len(self.teams)):
            team = self.teams[index]
            # self.problem += self.start_slot_number[f"{team.pk}"] - pulp.lpSum(
            #     self.start_slots[f"{team.pk}_{slot}"] * slot for slot in
            #     range(self.contest_duration - self.minimum_start_interval)) == 0, f"start_slot_number_{team.pk}"
            # Get all teams with a shorter flight time
            for other_index in range(index + 1, len(self.teams)):
                other_team = self.teams[other_index]
                if team == other_team:
                    continue
                flight_time_difference = team.flight_time - other_team.flight_time
                if flight_time_difference >= self.minimum_start_interval:  # other_team is fastest
                    # 0 = after
                    self.problem += self.start_slot_numbers[
                                        f"{team.pk}"] - self.start_slot_numbers[
                                        f"{other_team.pk}"] + flight_time_difference + 1 - self.very_large_variable * \
                                    self.start_after[
                                        f"{team.pk}_{other_team.pk}"] <= 0, f"team_start_flight_difference_before_other_{team.pk}_{other_team.pk}"
                    # 1 = before
                    self.problem += self.start_slot_numbers[
                                        f"{other_team.pk}"] - self.start_slot_numbers[
                                        f"{team.pk}"] + self.minimum_start_interval - self.very_large_variable * (
                                            1 - self.start_after[
                                        f"{team.pk}_{other_team.pk}"]) <= 0, f"other_start_immediately_before_team_{team.pk}_{other_team.pk}"
                elif flight_time_difference <= -self.minimum_start_interval:  # team is fastest
                    flight_time_difference *= -1
                    # 0 = after
                    self.problem += self.start_slot_numbers[
                                        f"{other_team.pk}"] - self.start_slot_numbers[
                                        f"{team.pk}"] + flight_time_difference + 1 - self.very_large_variable * \
                                    self.start_after[
                                        f"{team.pk}_{other_team.pk}"] <= 0, f"team_start_flight_difference_before_other_{team.pk}_{other_team.pk}"
                    # 1 = before
                    self.problem += self.start_slot_numbers[
                                        f"{team.pk}"] - self.start_slot_numbers[
                                        f"{other_team.pk}"] + self.minimum_start_interval - self.very_large_variable * (
                                            1 - self.start_after[
                                        f"{team.pk}_{other_team.pk}"]) <= 0, f"other_start_immediately_before_team_{team.pk}_{other_team.pk}"
                else:  # both teams are equally fast
                    # 0 = after
                    self.problem += self.start_slot_numbers[
                                        f"{team.pk}"] - self.start_slot_numbers[
                                        f"{other_team.pk}"] + self.minimum_start_interval - self.very_large_variable * \
                                    self.start_after[
                                        f"{team.pk}_{other_team.pk}"] <= 0, f"team_start_flight_difference_before_other_{team.pk}_{other_team.pk}"
                    # 1 = before
                    self.problem += self.start_slot_numbers[
                                        f"{other_team.pk}"] - self.start_slot_numbers[
                                        f"{team.pk}"] + self.minimum_start_interval - self.very_large_variable * (
                                            1 - self.start_after[
                                        f"{team.pk}_{other_team.pk}"]) <= 0, f"other_start_immediately_before_team_{team.pk}_{other_team.pk}"

    # def __equal_start_and_finish_before(self):
    #     logger.info("Equal earlier takeoff and landings")
    #     for team in self.teams:
    #         for slot in range(self.contest_duration - team.flight_time):
    #             self.problem += pulp.lpSum(
    #                 self.takeoff_slots[f"{internal_slot}"] for internal_slot in range(slot)) - pulp.lpSum(
    #                 self.landing_slots[f"{internal_slot}"] for internal_slot in
    #                 range(slot + team.flight_time)) <= 0, f"equal_landing_and_takeoff_{team.pk}_{slot}"

    def __minimum_start_interval(self):
        logger.info("Minimum start interval")
        start_after = pulp.LpVariable.dicts(
            "start_after",
            [f"{team.pk}_{other_team.pk}" for team in self.teams for other_team in self.teams],
            lowBound=0,
            upBound=1,
            cat=pulp.LpInteger
        )
        for team in self.teams:
            for other_team in self.teams:
                if team != other_team:
                    # 0 = after
                    self.problem += self.start_slot_numbers[
                                        f"{team.pk}"] - self.start_slot_numbers[
                                        f"{other_team.pk}"] + self.minimum_start_interval - self.very_large_variable * \
                                    start_after[
                                        f"{team.pk}_{other_team.pk}"] <= 0, f"team_start_minimum_after_other_{team.pk}_{other_team.pk}"
                    # 1 = before
                    self.problem += self.start_slot_numbers[
                                        f"{other_team.pk}"] - self.start_slot_numbers[
                                        f"{team.pk}"] + self.minimum_start_interval - self.very_large_variable * (
                                            1 - start_after[
                                        f"{team.pk}_{other_team.pk}"]) <= 0, f"other_start_before_team_{team.pk}_{other_team.pk}"
    #     for slot in range(self.contest_duration - self.minimum_start_interval):
    #         self.problem += pulp.lpSum(self.takeoff_slots[f"{takeoff_range}"] for takeoff_range in range(slot,
    #                                                                                                      slot + self.minimum_start_interval)) <= 1, f"takeoff_slot_interval_{slot}"
    #         self.problem += self.takeoff_slots[f"{slot}"] - pulp.lpSum(
    #             self.start_slots[f"{team.pk}_{slot}"] for team in self.teams) == 0, f"used_takeoff_slot_{slot}"
    #         # self.problem += self.landing_slots[f"{slot}"] - pulp.lpSum(
    #         #     self.start_slots[f"{team.pk}_{slot - team.flight_time}"] for team in self.teams if
    #         #     slot - team.flight_time >= 0) == 0, f"used_landing_slot_{slot}"
