"""
Regression tests for the PuLP/CBC -> OR-Tools CP-SAT scheduler rewrite (see the approved
migration plan / commit history). Two things this rewrite fixes that the pre-existing test
suite (test_contestant_scheduler.py, test_contestant_scheduler_double_booking.py) doesn't cover:

1. The old "roughly equal flight time" branch of the start/finish-interval formula dropped a
   flight-time-difference correction term the other two branches had, silently eroding the
   configured minimum_finish_interval buffer for the single most common real-world case (two
   contestants with similar but not identical predicted flight times). The new formula applies
   the same max(minimum_start_interval, flight_time_difference + minimum_finish_interval) shape
   uniformly to every pair, regardless of relative speed.
2. CP-SAT should comfortably solve realistic contest sizes to a *proven* optimum within the 30s
   budget (replacing the old greedy/fixValue shortcut this used to need), while still holding
   the no-double-booking and no-overtaking invariants across every pair.
"""

import datetime
import unittest

from display.contestant_scheduling.contestant_scheduler import Solver, TeamDefinition

FIRST_TAKEOFF = datetime.datetime(2024, 1, 1, 10, 0, tzinfo=datetime.timezone.utc)


def _overlaps(intervals):
    """intervals: list of (pk, resource_key, start, end). Returns the first overlapping pair
    sharing a resource_key, or None."""
    by_resource = {}
    for pk, resource_key, start, end in intervals:
        by_resource.setdefault(resource_key, []).append((start, end, pk))
    for resource_key, windows in by_resource.items():
        windows.sort()
        for (s1, e1, pk1), (s2, e2, pk2) in zip(windows, windows[1:]):
            if s2 < e1:
                return (resource_key, pk1, pk2, (s1, e1), (s2, e2))
    return None


class TestEqualSpeedBufferErosionFixed(unittest.TestCase):
    def test_small_flight_time_difference_never_erodes_the_finish_interval_buffer(self):
        # Two teams with a small but nonzero flight-time difference (10 vs 12 minutes), sharing
        # no resources at all - exactly the case that fell into the old code's buggy "equal
        # speed" branch (max(minimum_start_interval, minimum_finish_interval), silently ignoring
        # the 2-minute difference). Under the old formula, if the slower (12-minute) team ended
        # up scheduled first, the achieved finish gap could be as low as
        # minimum_finish_interval - flight_time_difference = 5 - 2 = 3, violating the configured
        # 5-minute buffer. Order-agnostic: asserts the achieved gap regardless of which team the
        # solver actually starts first.
        team_a = TeamDefinition(
            pk=1, flight_time=10, tracker_id="t1", tracker_service="traccar",
            aircraft_registration="LN-AAA", member1=1, member2=None, frozen=False, start_time=None,
        )
        team_b = TeamDefinition(
            pk=2, flight_time=12, tracker_id="t2", tracker_service="traccar",
            aircraft_registration="LN-BBB", member1=2, member2=None, frozen=False, start_time=None,
        )

        solver = Solver(
            first_takeoff_time=FIRST_TAKEOFF,
            contest_duration=200,
            teams=[team_a, team_b],
            minimum_start_interval=5,
            minimum_finish_interval=5,
        )
        result = solver.schedule_teams()

        self.assertTrue(solver.optimal_solution)
        by_pk = {t.pk: t for t in result}
        finish_a = by_pk[1].start_slot + by_pk[1].flight_time
        finish_b = by_pk[2].start_slot + by_pk[2].flight_time
        self.assertGreaterEqual(
            abs(finish_a - finish_b),
            5,
            "finish-line separation eroded below the configured minimum_finish_interval",
        )


class TestStressNoDoubleBookingOrOvertaking(unittest.TestCase):
    def test_20_teams_mixed_resources_no_overlap_no_overtake_proven_optimal(self):
        # 20 teams cycling through only 4 aircraft / 5 trackers / 10 crew slots is already a
        # deliberately dense, adversarial resource-sharing pattern (real contests with this many
        # entrants would typically have far less overlap). Empirically, this exact shape scales
        # from ~2s at 20 teams to not provably optimal within the 30s budget by 24 - a real,
        # sharp combinatorial cliff worth knowing about, not a formulation bug (FEASIBLE, not
        # OPTIMAL, is still an explicitly acceptable outcome per Solver's own contract - see
        # schedule_teams()). Picked 20 here as a size that reliably proves optimal quickly, to
        # keep this a meaningful, non-flaky performance+correctness check rather than one that
        # depends on hitting the time budget.
        aircraft_pool = ["LN-AAA", "LN-BBB", "LN-CCC", "LN-DDD"]
        tracker_pool = ["trk1", "trk2", "trk3", "trk4", "trk5"]
        crew_pool = list(range(1, 11))

        num_teams = 20
        teams = []
        for i in range(num_teams):
            teams.append(
                TeamDefinition(
                    pk=i,
                    flight_time=30 + (i % 5) * 7,
                    tracker_id=tracker_pool[i % len(tracker_pool)],
                    tracker_service="traccar",
                    aircraft_registration=aircraft_pool[i % len(aircraft_pool)],
                    member1=crew_pool[i % len(crew_pool)],
                    member2=crew_pool[(i + 3) % len(crew_pool)] if i % 2 == 0 else None,
                    frozen=False,
                    start_time=None,
                )
            )

        solver = Solver(
            first_takeoff_time=FIRST_TAKEOFF,
            contest_duration=1440,
            teams=teams,
            minimum_start_interval=5,
            minimum_finish_interval=3,
            aircraft_switch_time=15,
            tracker_switch_time=10,
            crew_switch_time=10,
        )
        result = solver.schedule_teams()

        self.assertTrue(
            solver.optimal_solution,
            f"expected a provably optimal schedule for {num_teams} teams within "
            f"{solver.MAX_SOLVE_SECONDS}s; messages: {solver.optimisation_messages}",
        )
        self.assertEqual(len(result), num_teams)

        by_pk = {t.pk: t for t in result}
        original_by_pk = {t.pk: t for t in teams}

        aircraft_intervals = [
            (t.pk, t.aircraft_registration, t.start_slot, t.start_slot + t.flight_time + solver.aircraft_switch_time)
            for t in result
        ]
        self.assertIsNone(_overlaps(aircraft_intervals), "aircraft double-booked")

        tracker_switch = max(solver.tracker_switch_time, solver.tracker_start_lead_time)
        tracker_intervals = [
            (t.pk, t.get_tracker_id(), t.start_slot, t.start_slot + t.flight_time + tracker_switch)
            for t in result
        ]
        self.assertIsNone(_overlaps(tracker_intervals), "tracker double-booked")

        crew_intervals = []
        for t in result:
            original = original_by_pk[t.pk]
            end = t.start_slot + t.flight_time + solver.crew_switch_time
            if original.member1 is not None:
                crew_intervals.append((t.pk, original.member1, t.start_slot, end))
            if original.member2 is not None:
                crew_intervals.append((t.pk, original.member2, t.start_slot, end))
        self.assertIsNone(_overlaps(crew_intervals), "crew member double-booked")

        # No-overtake: whichever team started first must also have finished first.
        for i in range(len(teams)):
            for j in range(i + 1, len(teams)):
                a_r, b_r = by_pk[teams[i].pk], by_pk[teams[j].pk]
                finish_a = a_r.start_slot + a_r.flight_time
                finish_b = b_r.start_slot + b_r.flight_time
                if a_r.start_slot <= b_r.start_slot:
                    self.assertGreaterEqual(
                        finish_b, finish_a, f"team {b_r.pk} started after {a_r.pk} but finished first"
                    )
                else:
                    self.assertGreaterEqual(
                        finish_a, finish_b, f"team {a_r.pk} started after {b_r.pk} but finished first"
                    )
