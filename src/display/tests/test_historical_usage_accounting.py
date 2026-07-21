from django.test import TestCase
from django.utils import timezone

from display.models import Contest, TokenType, UserTokenGrant, ContestUsageLedger, NavigationTask, Route, Scorecard, ContestantTrack, Contestant, Team, Crew, Person, Aeroplane, MyUser, ContestTokenAssignment
from display.services.access_resolver import resolve_contest_access


class TestHistoricalUsageAccounting(TestCase):
    def setUp(self):
        self.user = MyUser.objects.create(email="usage-owner@example.com")
        self.owner_person = Person.objects.create(first_name="Owner", last_name="Pilot", email=self.user.email)
        self.person = Person.objects.create(first_name="Pilot", last_name="One", email="pilot@example.com")
        self.second_pilot = Person.objects.create(first_name="Pilot", last_name="Two", email="pilot2@example.com")
        self.team = Team.objects.create(
            crew=Crew.objects.create(member1=self.person),
            aeroplane=Aeroplane.objects.create(registration="LN-HIST"),
        )
        self.copilot = Person.objects.create(first_name="Copilot", last_name="One", email="copilot@example.com")
        self.recreated_team_same_pilot = Team.objects.create(
            crew=Crew.objects.create(member1=self.person, member2=self.copilot),
            aeroplane=Aeroplane.objects.create(registration="LN-HIST-2"),
        )
        self.second_pilot_team = Team.objects.create(
            crew=Crew.objects.create(member1=self.second_pilot),
            aeroplane=Aeroplane.objects.create(registration="LN-HIST-3"),
        )
        self.owner_team = Team.objects.create(
            crew=Crew.objects.create(member1=self.owner_person),
            aeroplane=Aeroplane.objects.create(registration="LN-OWNER"),
        )
        self.contest = Contest.objects.create(
            name="Historical Usage Contest",
            time_zone="Europe/Oslo",
            start_time=timezone.now(),
            finish_time=timezone.now() + timezone.timedelta(hours=8),
            location="60.0,11.0",
            created_by=self.user,
        )
        self.token_type = TokenType.objects.create(name="History token", contestant_limit=2, task_limit=1)
        self.token_grant = UserTokenGrant.objects.create(user=self.user, token_type=self.token_type, quantity_total=1, quantity_consumed=0)
        ContestTokenAssignment.objects.create(contest=self.contest, token_grant=self.token_grant, token_type=self.token_type)
        self.scorecard = Scorecard.objects.create(name="History card", shortcut_name="hist-card")
        self.task = NavigationTask.objects.create(
            name="History Task",
            contest=self.contest,
            route=Route.objects.create(name="History route"),
            original_scorecard=self.scorecard,
            start_time=timezone.now(),
            finish_time=timezone.now() + timezone.timedelta(hours=8),
        )
        takeoff = timezone.now()
        self.contestant = Contestant.objects.create(
            team=self.team,
            navigation_task=self.task,
            contestant_number=1,
            takeoff_time=takeoff,
            tracker_start_time=takeoff - timezone.timedelta(minutes=10),
            finished_by_time=takeoff + timezone.timedelta(hours=2),
            air_speed=70,
            minutes_to_starting_point=5,
            wind_speed=0,
            wind_direction=0,
            gate_times={},
        )
        self.owner_contestant = Contestant.objects.create(
            team=self.owner_team,
            navigation_task=self.task,
            contestant_number=2,
            takeoff_time=takeoff,
            tracker_start_time=takeoff - timezone.timedelta(minutes=10),
            finished_by_time=takeoff + timezone.timedelta(hours=2),
            air_speed=70,
            minutes_to_starting_point=5,
            wind_speed=0,
            wind_direction=0,
            gate_times={},
        )

    def _start_contestant(self):
        track = ContestantTrack.objects.get(contestant=self.contestant)
        track.set_calculator_started()

    def _start_owner_contestant(self):
        track = ContestantTrack.objects.get(contestant=self.owner_contestant)
        track.set_calculator_started()

    def test_starting_contestant_consumes_contest_team_slot_and_task_team_slot(self):
        self._start_contestant()

        resolution = resolve_contest_access(self.contest)
        self.assertEqual(1, resolution.contestants_used)
        self.assertEqual(1, resolution.tasks_used)
        self.assertTrue(ContestUsageLedger.objects.filter(contest=self.contest, kind=ContestUsageLedger.CONTEST_PILOT_STARTED, pilot=self.person).exists())
        self.assertTrue(ContestUsageLedger.objects.filter(contest=self.contest, kind=ContestUsageLedger.TASK_PILOT_STARTED, navigation_task=self.task, pilot=self.person).exists())

    def test_restarting_same_contestant_does_not_double_count(self):
        self._start_contestant()
        self._start_contestant()

        resolution = resolve_contest_access(self.contest)
        self.assertEqual(1, resolution.contestants_used)
        self.assertEqual(1, resolution.tasks_used)
        self.assertEqual(1, ContestUsageLedger.objects.filter(kind=ContestUsageLedger.CONTEST_PILOT_STARTED).count())
        self.assertEqual(1, ContestUsageLedger.objects.filter(kind=ContestUsageLedger.TASK_PILOT_STARTED).count())

    def test_deleting_started_contestant_does_not_remove_historical_usage(self):
        self._start_contestant()

        self.contestant.delete()

        resolution = resolve_contest_access(self.contest)
        self.assertEqual(1, resolution.contestants_used)
        self.assertEqual(1, ContestUsageLedger.objects.filter(kind=ContestUsageLedger.CONTEST_PILOT_STARTED).count())

    def test_deleting_task_with_started_contestant_does_not_remove_historical_usage(self):
        self._start_contestant()

        self.task.delete()

        resolution = resolve_contest_access(self.contest)
        self.assertEqual(1, resolution.tasks_used)
        self.assertEqual(1, ContestUsageLedger.objects.filter(kind=ContestUsageLedger.TASK_PILOT_STARTED).count())

    def test_owner_started_contestant_does_not_consume_guest_usage(self):
        self._start_owner_contestant()

        resolution = resolve_contest_access(self.contest)
        self.assertEqual(0, resolution.contestants_used)

    def test_same_primary_pilot_with_new_team_reuses_slot(self):
        self._start_contestant()
        recreated_contestant = Contestant.objects.create(
            team=self.recreated_team_same_pilot,
            navigation_task=self.task,
            contestant_number=3,
            takeoff_time=timezone.now(),
            tracker_start_time=timezone.now() - timezone.timedelta(minutes=10),
            finished_by_time=timezone.now() + timezone.timedelta(hours=2),
            air_speed=70,
            minutes_to_starting_point=5,
            wind_speed=0,
            wind_direction=0,
            gate_times={},
        )

        ContestantTrack.objects.get(contestant=recreated_contestant).set_calculator_started()

        resolution = resolve_contest_access(self.contest)
        self.assertEqual(1, resolution.contestants_used)

    def test_different_primary_pilot_consumes_new_slot(self):
        self._start_contestant()
        second_pilot_contestant = Contestant.objects.create(
            team=self.second_pilot_team,
            navigation_task=self.task,
            contestant_number=4,
            takeoff_time=timezone.now(),
            tracker_start_time=timezone.now() - timezone.timedelta(minutes=10),
            finished_by_time=timezone.now() + timezone.timedelta(hours=2),
            air_speed=70,
            minutes_to_starting_point=5,
            wind_speed=0,
            wind_direction=0,
            gate_times={},
        )

        ContestantTrack.objects.get(contestant=second_pilot_contestant).set_calculator_started()

        resolution = resolve_contest_access(self.contest)
        self.assertEqual(2, resolution.contestants_used)
