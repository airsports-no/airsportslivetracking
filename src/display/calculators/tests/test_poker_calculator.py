import datetime
from unittest.mock import MagicMock, patch
from django.test import TransactionTestCase
from display.calculators.poker_calculator import PokerCalculator
from display.calculators.calculator import OrchestratorState, PokerGatePassedEvent
from display.models import Contest, NavigationTask, Contestant, Team, Crew, Person, Aeroplane, PlayingCard, Route, ContestantTrack
from display.models.contestant_utility_models import ContestantReceivedPosition
from display.utilities.coordinate_utilities import Projector
from queue import Queue

class TestPokerCalculator(TransactionTestCase):
    def setUp(self):
        from display.default_scorecards import default_scorecard_poker_run
        self.scorecard = default_scorecard_poker_run.get_default_scorecard()
        
        self.contest = Contest.objects.create(
            name="Poker Run Contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=5),
            time_zone="Europe/Oslo",
        )
        
        self.route = Route.objects.create(name="Poker Route")
        from display.waypoint import Waypoint as WP
        self.wp1 = WP("WP1")
        self.wp1.latitude = 60.0
        self.wp1.longitude = 11.0
        self.wp1.type = "tp"
        self.wp1.width = 0.5 # 0.5 NM
        self.wp1.gate_line = [[60.0, 10.9], [60.0, 11.1]]
        
        self.route.waypoints = [self.wp1]
        self.route.save()
        
        self.nav_task = NavigationTask.create(
            name="Poker Task",
            route=self.route,
            original_scorecard=self.scorecard,
            contest=self.contest,
            start_time=self.contest.start_time,
            finish_time=self.contest.finish_time,
        )
        
        self.person = Person.objects.create(first_name="Pilot", last_name="One", email="pilot@test.com")
        self.crew = Crew.objects.create(member1=self.person)
        self.aeroplane = Aeroplane.objects.create(registration="LN-TEST")
        self.team = Team.objects.create(crew=self.crew, aeroplane=self.aeroplane)
        
        self.contestant = Contestant.objects.create(
            navigation_task=self.nav_task,
            team=self.team,
            takeoff_time=self.contest.start_time,
            tracker_start_time=self.contest.start_time,
            finished_by_time=self.contest.finish_time,
            contestant_number=1,
            air_speed=100,
        )
        
        # Ensure gate_times is populated
        self.contestant.gate_times = {"WP1": self.contestant.takeoff_time}
        self.contestant.save()

        self.queue = Queue()
        self.projector = Projector(60.0, 11.0)
        
        self.calculator = PokerCalculator(
            contestant=self.contestant,
            scorecard=self.scorecard,
            route=self.route,
            score_processing_queue=self.queue,
            live_processing=True,
            projector=self.projector
        )

    @patch("websocket_channels.WebsocketFacade.transmit_playing_cards")
    def test_poker_gate_passed_logic(self, mock_transmit):
        # 1. Create a position inside the gate (at the center)
        pos = ContestantReceivedPosition.objects.create(
            contestant=self.contestant,
            latitude=60.0,
            longitude=11.0,
            time=self.contestant.takeoff_time
        )
        # Project it
        proj = self.projector.project_point(pos.latitude, pos.longitude)
        pos.projected_x = proj.projected_x
        pos.projected_y = proj.projected_y
        
        state = OrchestratorState(
            last_gate=None,
            last_visible_gate=None,
            next_gate=None,
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=False,
            recalculation_completed=False
        )
        
        # 2. Check polygons (which should trigger the distance fallback)
        events = self.calculator.check_polygons(pos, state)
        
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], PokerGatePassedEvent)
        self.assertEqual(events[0].gate.name, "WP1")
        
        # 3. Handle the event
        # This will trigger PlayingCard.add_contestant_card
        self.calculator.on_poker_gate_passed(events[0])
        
        # 4. Verify a card was assigned
        self.assertEqual(PlayingCard.objects.filter(contestant=self.contestant).count(), 1)
        card = PlayingCard.objects.get(contestant=self.contestant)
        self.assertEqual(card.waypoint_name, "WP1")
        
        # 5. Verify websocket transmit was called
        mock_transmit.assert_called_once()
        
        # 6. Verify serialization doesn't crash (Regression for the AttributeError)
        from websocket_channels import serialize_playing_card
        serialized = serialize_playing_card(card)
        self.assertEqual(serialized["gate"], "WP1")
        self.assertEqual(serialized["card_string"], card.card)
        self.assertEqual(serialized["card_value"], card.rank)
        self.assertEqual(serialized["card_suit"], card.suit)
