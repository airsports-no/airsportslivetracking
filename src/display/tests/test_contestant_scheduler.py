import datetime
from unittest import TestCase

from display.contestant_scheduling.contestant_scheduler import TeamDefinition, Solver


class TestContestantScheduler(TestCase):
    def test_overlapping_aircraft(self):
        teams = [
            TeamDefinition(0, 5, "something1", "traccar", "aircraft_one", 1, 2, False, None),
            TeamDefinition(1, 5, "something2", "traccar", "aircraft_one", 3, 4, False, None),
        ]
        now = datetime.datetime.now(datetime.timezone.utc)
        solver = Solver(
            now, 60, teams, minimum_start_interval=0, aircraft_switch_time=0
        )
        team_definitions = solver.schedule_teams()
        self.assertEqual(2, len(team_definitions))
        self.assertEqual(now, min([item.start_time for item in team_definitions]))
        self.assertEqual(
            5 * 60,
            abs(
                (
                    team_definitions[0].start_time - team_definitions[1].start_time
                ).total_seconds()
            ),
        )

    def test_overtaking(self):
        teams = [
            TeamDefinition(0, 2, "something", "traccar", "aircraft_one", 1, 2, False, None),
            TeamDefinition(1, 5, "something2", "traccar", "aircraft_two", 3, 4, False, None),
        ]
        now = datetime.datetime.now(datetime.timezone.utc)
        solver = Solver(now, 8, teams, minimum_start_interval=2)
        team_definitions = solver.schedule_teams()
        print(now)
        self.assertEqual(now, min([item.start_time for item in team_definitions]))
        self.assertEqual(0, team_definitions[0].start_slot)
        self.assertEqual(2, team_definitions[1].start_slot)

    def test_overlapping_tracker(self):
        teams = [
            TeamDefinition(0, 5, "something", "traccar", "aircraft_one", 1, 2, False, None),
            TeamDefinition(1, 5, "something", "traccar", "aircraft_two", 3, 4, False, None),
        ]
        now = datetime.datetime.now(datetime.timezone.utc)
        solver = Solver(
            now,
            60,
            teams,
            minimum_start_interval=0,
            tracker_switch_time=0,
            tracker_start_lead_time=1,
        )
        team_definitions = solver.schedule_teams()
        self.assertEqual(2, len(team_definitions))
        self.assertEqual(now, min([item.start_time for item in team_definitions]))
        self.assertEqual(
            6 * 60,
            abs(
                (
                    team_definitions[0].start_time - team_definitions[1].start_time
                ).total_seconds()
            ),
        )
        team_definitions = sorted(team_definitions, key=lambda k: k.start_slot)
        self.assertEqual(0, team_definitions[0].start_slot)
        self.assertEqual(6, team_definitions[1].start_slot)

    def test_overlapping_crew(self):
        teams = [
            TeamDefinition(0, 5, "something", "traccar", "aircraft_one", 1, 2, False, None),
            TeamDefinition(1, 5, "something", "traccar", "aircraft_one", 1, None, False, None),
        ]
        now = datetime.datetime.now(datetime.timezone.utc)
        solver = Solver(
            now,
            60,
            teams,
            minimum_start_interval=0,
            tracker_switch_time=0,
            tracker_start_lead_time=1,
            crew_switch_time=10,
            aircraft_switch_time=0,
        )
        team_definitions = solver.schedule_teams()
        self.assertEqual(2, len(team_definitions))
        self.assertEqual(now, min([item.start_time for item in team_definitions]))
        self.assertEqual(
            16 * 60,
            abs(
                (
                    team_definitions[0].start_time - team_definitions[1].start_time
                ).total_seconds()
            ),
        )
        team_definitions = sorted(team_definitions, key=lambda k: k.start_slot)
        self.assertEqual(0, team_definitions[0].start_slot)
        self.assertEqual(
            16, team_definitions[1].start_slot
        )  # Flight time of the first team plus crew switch time
