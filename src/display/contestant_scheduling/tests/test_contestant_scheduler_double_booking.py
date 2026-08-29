"""
Regression tests for the 2026-08-28 security/correctness review's SEVERE scheduling finding:
Solver.schedule_teams() unconditionally overwrote the real solver status with
pulp.LpStatusOptimal, so an infeasible/non-optimal solve still returned a full schedule built
from whatever the (invalid) LP variables held - written to the database and reported as
"status": "success", with contestants silently double-booked on the same aircraft.

A second, compounding bug: the greedy warm-start's select_team() assigned
next_aircraft_available/next_tracker_available/next_crew_available with a plain "=" instead of
taking the max with any existing reservation - so when frozen teams sharing a resource were
processed out of chronological order, a shorter-duration team's assignment could erase a
longer-duration team's still-active reservation window. Since optimise=False (the scheduling
API's default) locks the greedy result in directly via fixValue(), this corrupted the actual
final schedule, not just an LP warm-start hint.
"""

import datetime
import unittest

from display.contestant_scheduling.contestant_scheduler import Solver, TeamDefinition

FIRST_TAKEOFF = datetime.datetime(2024, 1, 1, 10, 0, tzinfo=datetime.timezone.utc)


def _team(pk, flight_time, aircraft="LN-AAA", tracker=None, frozen=False, start_offset_minutes=None):
    return TeamDefinition(
        pk=pk,
        flight_time=flight_time,
        tracker_id=tracker or f"tracker{pk}",
        tracker_service="traccar",
        aircraft_registration=aircraft,
        member1=pk * 100,
        member2=None,
        frozen=frozen,
        start_time=(FIRST_TAKEOFF + datetime.timedelta(minutes=start_offset_minutes)) if frozen else None,
    )


def _aircraft_intervals(scheduled_teams, aircraft_switch_time=20):
    """[start_slot, end_slot) per team, end_slot including the aircraft switch/turnaround time."""
    intervals = []
    for team in scheduled_teams:
        start = team.start_slot
        end = start + team.flight_time + aircraft_switch_time
        intervals.append((team.pk, team.aircraft_registration, start, end))
    return intervals


def _overlaps(intervals):
    by_aircraft = {}
    for pk, aircraft, start, end in intervals:
        by_aircraft.setdefault(aircraft, []).append((start, end, pk))
    for aircraft, windows in by_aircraft.items():
        windows.sort()
        for (s1, e1, pk1), (s2, e2, pk2) in zip(windows, windows[1:]):
            if s2 < e1:
                return (aircraft, pk1, pk2, (s1, e1), (s2, e2))
    return None


class TestSchedulerNeverSilentlyDoubleBooks(unittest.TestCase):
    def test_genuinely_infeasible_frozen_teams_reports_failure_not_a_corrupted_schedule(self):
        # Two frozen teams on the same aircraft, pinned to slots that unavoidably overlap
        # (team A: slot 0, flies 100 minutes; team B: slot 30, flies 50 minutes - both on
        # LN-AAA). No valid non-overlapping assignment exists regardless of the warm start,
        # so the LP solve must be infeasible - and that must actually be reported now instead
        # of being masked into a fabricated "successful" schedule.
        team_a = _team(pk=1, flight_time=100, frozen=True, start_offset_minutes=0)
        team_b = _team(pk=2, flight_time=50, frozen=True, start_offset_minutes=30)

        solver = Solver(
            first_takeoff_time=FIRST_TAKEOFF,
            contest_duration=600,
            teams=[team_a, team_b],
            optimise=False,
        )
        result = solver.schedule_teams()

        self.assertEqual(result, [])
        self.assertFalse(solver.optimal_solution)
        self.assertTrue(
            len(solver.optimisation_messages) > 0,
            "expected a message explaining why no schedule was found",
        )

    def test_frozen_teams_sharing_an_aircraft_out_of_order_never_produce_an_overlap(self):
        # Reproduces the review's repro shape: a later-finishing frozen team listed BEFORE an
        # earlier-finishing frozen team sharing the same aircraft (triggers the select_team
        # overwrite-vs-max bug), plus one free team that must be fitted in around them. Whatever
        # the solver decides, it must never place two teams on the same aircraft with
        # overlapping [start, start+flight_time+switch_time) windows.
        team_b_long = _team(pk=2, flight_time=60, frozen=True, start_offset_minutes=100)  # finishes later
        team_a_short = _team(pk=1, flight_time=50, frozen=True, start_offset_minutes=0)  # finishes earlier
        team_c_free = _team(pk=3, flight_time=40, frozen=False)

        solver = Solver(
            first_takeoff_time=FIRST_TAKEOFF,
            contest_duration=600,
            # Deliberately b-then-a: the long-finishing team is select_team()'d first, so the
            # old plain-assignment bug lets the short-finishing team's later select_team() call
            # erase its still-active aircraft reservation.
            teams=[team_b_long, team_a_short, team_c_free],
            optimise=False,
        )
        result = solver.schedule_teams()

        if result:
            overlap = _overlaps(_aircraft_intervals(result, solver.aircraft_switch_time))
            self.assertIsNone(overlap, f"aircraft double-booked: {overlap}")
        else:
            # Also acceptable: correctly reporting infeasible rather than fabricating a bad
            # schedule - the one outcome that must never happen is a "successful" overlap.
            self.assertFalse(solver.optimal_solution)
