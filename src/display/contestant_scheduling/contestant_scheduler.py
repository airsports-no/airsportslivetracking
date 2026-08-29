import datetime
import logging
import os
from typing import Dict, List, Optional

import numpy as np
from ortools.sat.python import cp_model

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
    """
    Schedules contestant takeoff times for a navigation task: minimise the makespan (first
    takeoff -> last landing) subject to two kinds of hard constraint -

    - Resource exclusivity: two contestants sharing an aircraft, tracker, or crew member cannot
      fly simultaneously, and need a resource-specific switch-time buffer between one landing
      and the next one taking off (aircraft_switch_time / tracker_switch_time / crew_switch_time).
    - No overtaking: for every pair of contestants (regardless of shared resources), whichever
      one starts first must also finish first - by at least minimum_finish_interval - and starts
      must be at least minimum_start_interval apart. Aircraft flying the same route must never
      cross the finish line out of the order they crossed the start line in.

    Modelled as a CP-SAT constraint-satisfaction problem (see __add_resource_no_overlap_constraints
    and __add_precedence_constraints). Previously a big-M MILP solved with PuLP/CBC, with a
    hand-rolled greedy heuristic used as the actual production schedule whenever optimise=False;
    CP-SAT solves this problem shape (interval scheduling, disjunctive resource constraints,
    precedence) fast enough that the greedy shortcut is no longer needed - optimise is still
    accepted for call-site compatibility but no longer changes behaviour, this always solves
    for a real optimum (or best-found-within-budget) schedule.
    """

    MAX_SOLVE_SECONDS = 60

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
        optimise: bool = True,
    ):
        self.first_takeoff_time = first_takeoff_time
        self.teams = teams
        self.team_map = {team.pk: team for team in teams}
        self.optimise = optimise  # retained for call-site compatibility; no longer used.
        self.minutes_per_slot = 1
        self.contest_duration = 1440 * 2  # Two days
        self.minimum_start_interval = int(np.ceil(minimum_start_interval / self.minutes_per_slot))
        self.minimum_finish_interval = int(np.ceil(minimum_finish_interval / self.minutes_per_slot))
        self.aircraft_switch_time = int(np.ceil(aircraft_switch_time / self.minutes_per_slot))
        self.tracker_switch_time = int(np.ceil(tracker_switch_time / self.minutes_per_slot))
        self.crew_switch_time = int(np.ceil(crew_switch_time / self.minutes_per_slot))
        self.tracker_start_lead_time = int(np.ceil(tracker_start_lead_time / self.minutes_per_slot))
        self.optimisation_messages = []

        self.optimal_solution = False

    def time_to_slot(self, takeoff_time: datetime.datetime) -> int:
        return int(((takeoff_time - self.first_takeoff_time).total_seconds() / 60) / self.minutes_per_slot)

    def schedule_teams(self) -> List[TeamDefinition]:
        """

        :return: Dictionary where the keys are team pk and the values are takeoff times
        """
        model = cp_model.CpModel()
        start_vars = self.__create_start_variables(model)

        finish_exprs = [start_vars[team.pk] + team.flight_time for team in self.teams]
        latest_finish = model.NewIntVar(
            min(team.flight_time for team in self.teams), self.contest_duration, "latest_finish"
        )
        model.AddMaxEquality(latest_finish, finish_exprs)
        model.Minimize(latest_finish)

        self.__add_resource_no_overlap_constraints(model, start_vars)
        self.__add_precedence_constraints(model, start_vars)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.MAX_SOLVE_SECONDS
        # CP-SAT defaults to single-threaded search; proving optimality (not just finding a
        # feasible schedule) on this problem shape benefits substantially from parallel search
        # portfolios sharing learned clauses.
        solver.parameters.num_search_workers = min(8, os.cpu_count() or 1)
        logger.debug("Running CP-SAT solve")
        status = solver.Solve(model)

        self.optimal_solution = status == cp_model.OPTIMAL
        status_name = solver.StatusName(status)
        logger.debug(f"CP-SAT solve status: {status_name}")

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            if not self.optimal_solution:
                self.optimisation_messages.append(
                    f"Schedule found but not proven optimal within {self.MAX_SOLVE_SECONDS}s (status: "
                    f"{status_name}). All constraints are still satisfied - this is a valid, safe "
                    "schedule, just not guaranteed to minimise total contest time."
                )
            return self.__generate_takeoff_times_from_solution(solver, start_vars)

        # A genuinely infeasible/unsolvable input (e.g. conflicting frozen contestants) correctly
        # returns [] here rather than a corrupted schedule - see the fixed status-masking bug
        # this replaces (commit 5054bc0d) for why that distinction matters.
        self.optimisation_messages.append(
            f"No feasible schedule found (solver status: {status_name}). This usually means "
            "the frozen/locked contestants' start times conflict with each other or with the "
            "minimum start/finish intervals - try unlocking one of them or widening the intervals."
        )
        return []

    def __create_start_variables(self, model: cp_model.CpModel) -> Dict[int, cp_model.IntVar]:
        max_duration = self.contest_duration - min(team.flight_time for team in self.teams)
        start_vars = {}
        for team in self.teams:
            if team.frozen:
                if team.start_time is None:
                    # Should not happen for frozen teams, but fallback
                    lower_bound, upper_bound = 0, max_duration
                else:
                    slot = self.time_to_slot(team.start_time)
                    lower_bound = upper_bound = slot
            else:
                lower_bound, upper_bound = 0, max_duration
            start_vars[team.pk] = model.NewIntVar(lower_bound, upper_bound, f"start_{team.pk}")
        return start_vars

    def __generate_takeoff_times_from_solution(
        self, solver: cp_model.CpSolver, start_vars: Dict[int, cp_model.IntVar]
    ) -> List[TeamDefinition]:
        for team in self.teams:
            slot = solver.Value(start_vars[team.pk])
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

    def __resource_groups(self):
        aircraft_groups, tracker_groups, crew_groups = {}, {}, {}
        for team in self.teams:
            aircraft_groups.setdefault(team.aircraft_registration, []).append(team)
            tracker_groups.setdefault(team.get_tracker_id(), []).append(team)
            if team.member1 is not None:
                crew_groups.setdefault(team.member1, []).append(team)
            if team.member2 is not None:
                crew_groups.setdefault(team.member2, []).append(team)
        return aircraft_groups, tracker_groups, crew_groups

    def __add_resource_no_overlap_constraints(
        self, model: cp_model.CpModel, start_vars: Dict[int, cp_model.IntVar]
    ):
        """
        Two contestants sharing an aircraft/tracker/crew member cannot fly simultaneously, and
        need that resource's switch-time buffer between one landing and the next taking off.
        One NewFixedSizeIntervalVar per team per resource it participates in (sized
        flight_time + switch_time so the buffer is baked into the interval itself), then a
        single native AddNoOverlap per resource group - replaces the old ~150 lines of
        hand-rolled big-M pairwise constraints (display/contestant_scheduling/contestant_scheduler.py
        pre-rewrite, __nonoverlapping_aircraft/_trackers/_team_members) with no big-M numerical
        fragility and no risk of the two directions of a pair being independently non-binding.
        """
        aircraft_groups, tracker_groups, crew_groups = self.__resource_groups()
        # Tracker switch uses the more conservative (larger) of the two buffers the old code used
        # inconsistently depending on direction - see the migration plan for why.
        tracker_switch = max(self.tracker_switch_time, self.tracker_start_lead_time)

        for groups, switch_time, label in (
            (aircraft_groups, self.aircraft_switch_time, "aircraft"),
            (tracker_groups, tracker_switch, "tracker"),
            (crew_groups, self.crew_switch_time, "crew"),
        ):
            for key, teams in groups.items():
                if len(teams) <= 1:
                    continue
                intervals = [
                    model.NewFixedSizeIntervalVar(
                        start_vars[team.pk],
                        team.flight_time + switch_time,
                        f"{label}_{key}_{team.pk}",
                    )
                    for team in teams
                ]
                model.AddNoOverlap(intervals)

    def __add_precedence_constraints(self, model: cp_model.CpModel, start_vars: Dict[int, cp_model.IntVar]):
        """
        No-overtaking: for every pair of teams (independent of shared resources - all
        contestants in one navigation task fly the same route), whichever one starts first must
        also finish first, with the configured minimum_finish_interval buffer, and starts must
        be at least minimum_start_interval apart. One reified boolean per pair
        (OnlyEnforceIf/.Not() - a true either/or, unlike the old independent-binary-per-direction
        formulation this replaces) picks which team starts first; the required gap in each
        direction is max(minimum_start_interval, (starter's flight_time - other's flight_time) +
        minimum_finish_interval) - applied uniformly regardless of which team is faster, fixing
        the bug where the "roughly equal speed" case dropped this flight-time-difference
        correction term and could silently erode the configured finish-line buffer.
        """
        for i in range(len(self.teams)):
            team = self.teams[i]
            for j in range(i + 1, len(self.teams)):
                other_team = self.teams[j]
                team_first = model.NewBoolVar(f"before_{team.pk}_{other_team.pk}")
                gap_if_team_first = max(
                    self.minimum_start_interval,
                    (team.flight_time - other_team.flight_time) + self.minimum_finish_interval,
                )
                gap_if_other_first = max(
                    self.minimum_start_interval,
                    (other_team.flight_time - team.flight_time) + self.minimum_finish_interval,
                )
                model.Add(start_vars[other_team.pk] >= start_vars[team.pk] + gap_if_team_first).OnlyEnforceIf(
                    team_first
                )
                model.Add(start_vars[team.pk] >= start_vars[other_team.pk] + gap_if_other_first).OnlyEnforceIf(
                    team_first.Not()
                )
