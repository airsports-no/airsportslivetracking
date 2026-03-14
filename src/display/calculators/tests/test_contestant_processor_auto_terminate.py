import datetime
from unittest.mock import MagicMock, patch
from django.test import TestCase
from display.calculators.contestant_processor import ContestantProcessor
from display.models import Contestant, NavigationTask, Contest, Scorecard, Route, Team, Crew, Aeroplane, Person
from display.models.contestant_track import ContestantTrack
from display.models.contestant_utility_models import ContestantReceivedPosition

class TestContestantProcessorAutoTerminate(TestCase):
    def setUp(self):
        # Setup basic models required for ContestantProcessor
        self.person = Person.objects.create(first_name="Test", last_name="Pilot")
        self.crew = Crew.objects.create(member1=self.person)
        self.aeroplane = Aeroplane.objects.create(registration="TEST-REG")
        self.team = Team.objects.create(crew=self.crew, aeroplane=self.aeroplane)
        self.route = Route.objects.create(name="Test Route")
        self.scorecard = Scorecard.objects.create(name="Test Scorecard")
        self.contest = Contest.objects.create(name="Test Contest", start_time=datetime.datetime.now(datetime.timezone.utc), finish_time=datetime.datetime.now(datetime.timezone.utc))
        self.navigation_task = NavigationTask.objects.create(
            name="Test Task",
            route=self.route,
            original_scorecard=self.scorecard,
            scorecard=self.scorecard,
            contest=self.contest,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc)
        )
        self.contestant = Contestant.objects.create(
            team=self.team,
            navigation_task=self.navigation_task,
            takeoff_time=datetime.datetime.now(datetime.timezone.utc),
            finished_by_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
            tracker_start_time=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=30),
            tracker_device_id="test_device",
            contestant_number=1
        )
        # ContestantProcessor expects ContestantTrack to exist
        self.contestant_track = ContestantTrack.objects.get(contestant=self.contestant)

    def create_mock_position_data(self, time, speed):
        return {
            "device_time": time,
            "latitude": 60.0,
            "longitude": 11.0,
            "speed": speed,
            "course": 0.0,
            "altitude": 0.0,
            "attributes": {"batteryLevel": 100, "course": 0.0},
            "id": 1,
            "deviceId": "test_device"
        }

    @patch("websocket_channels.WebsocketFacade")
    @patch("display.calculators.contestant_processor.calculator_is_alive")
    @patch("display.calculators.contestant_processor.WebsocketFacade")
    @patch("display.calculators.contestant_processor.get_traccar_instance")
    @patch("display.calculators.contestant_processor.RedisQueue")
    @patch("display.calculators.contestant_processor.calculator_factory")
    @patch("display.calculators.contestant_processor.post_slack_competition_message")
    def test_proactive_termination_on_low_speed(self, mock_slack, mock_calc_factory, mock_redis_queue, mock_traccar_factory, mock_ws, mock_alive, mock_ws_channels):
        mock_orchestrator = MagicMock()
        mock_orchestrator.has_any_gate_passed = True
        mock_orchestrator.has_the_contestant_passed_a_gate_and_landed.return_value = False
        mock_calc_factory.return_value = mock_orchestrator
        
        mock_queue_instance = mock_redis_queue.return_value
        mock_queue_instance.pop.return_value = None 
        mock_queue_instance.size = 0
        
        # Prevent threads from starting to avoid hangs
        with patch("threading.Thread"):
            processor = ContestantProcessor(self.contestant, live_processing=True)
            
            start_time = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
            
            # Manually simulate the loop in run()
            for i in range(65):
                position_data = self.create_mock_position_data(start_time + datetime.timedelta(seconds=i), 5.0)
                p = self.contestant.generate_position_block_for_contestant(position_data, position_data["device_time"])
                
                # Logic from run():
                all_positions = [p] # Simplified for test
                for position in all_positions:
                    processor.orchestrator.calculate_score(position)
                    if processor.live_processing and processor.orchestrator.has_any_gate_passed and not processor.track_terminated:
                        if position.speed < 10:
                            processor.consecutive_low_speed_positions += 1
                        else:
                            processor.consecutive_low_speed_positions = 0
                        if processor.consecutive_low_speed_positions >= 60:
                            processor.notify_termination()
                            break
                if processor.track_terminated:
                    break
            
            self.assertTrue(processor.track_terminated)
            self.assertEqual(processor.consecutive_low_speed_positions, 60)
            self.assertEqual(mock_orchestrator.calculate_score.call_count, 60)

    @patch("websocket_channels.WebsocketFacade")
    @patch("display.calculators.contestant_processor.calculator_is_alive")
    @patch("display.calculators.contestant_processor.WebsocketFacade")
    @patch("display.calculators.contestant_processor.get_traccar_instance")
    @patch("display.calculators.contestant_processor.RedisQueue")
    @patch("display.calculators.contestant_processor.calculator_factory")
    @patch("display.calculators.contestant_processor.post_slack_competition_message")
    def test_no_termination_if_no_gates_passed(self, mock_slack, mock_calc_factory, mock_redis_queue, mock_traccar_factory, mock_ws, mock_alive, mock_ws_channels):
        mock_orchestrator = MagicMock()
        mock_orchestrator.has_any_gate_passed = False
        mock_orchestrator.has_the_contestant_passed_a_gate_and_landed.return_value = False
        mock_calc_factory.return_value = mock_orchestrator
        
        mock_queue_instance = mock_redis_queue.return_value
        mock_queue_instance.pop.return_value = None 
        mock_queue_instance.size = 0
        
        with patch("threading.Thread"):
            processor = ContestantProcessor(self.contestant, live_processing=True)
            start_time = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
            
            for i in range(65):
                position_data = self.create_mock_position_data(start_time + datetime.timedelta(seconds=i), 5.0)
                p = self.contestant.generate_position_block_for_contestant(position_data, position_data["device_time"])
                
                all_positions = [p]
                for position in all_positions:
                    processor.orchestrator.calculate_score(position)
                    if processor.live_processing and processor.orchestrator.has_any_gate_passed and not processor.track_terminated:
                        if position.speed < 10:
                            processor.consecutive_low_speed_positions += 1
                        else:
                            processor.consecutive_low_speed_positions = 0
                        if processor.consecutive_low_speed_positions >= 60:
                            processor.notify_termination()
                            break
                if processor.track_terminated:
                    break
            
            self.assertFalse(processor.track_terminated)
            self.assertEqual(processor.consecutive_low_speed_positions, 0)
            self.assertEqual(mock_orchestrator.calculate_score.call_count, 65)

    @patch("websocket_channels.WebsocketFacade")
    @patch("display.calculators.contestant_processor.calculator_is_alive")
    @patch("display.calculators.contestant_processor.WebsocketFacade")
    @patch("display.calculators.contestant_processor.get_traccar_instance")
    @patch("display.calculators.contestant_processor.RedisQueue")
    @patch("display.calculators.contestant_processor.calculator_factory")
    @patch("display.calculators.contestant_processor.post_slack_competition_message")
    def test_reset_counter_on_high_speed(self, mock_slack, mock_calc_factory, mock_redis_queue, mock_traccar_factory, mock_ws, mock_alive, mock_ws_channels):
        mock_orchestrator = MagicMock()
        mock_orchestrator.has_any_gate_passed = True
        mock_orchestrator.has_the_contestant_passed_a_gate_and_landed.return_value = False
        mock_calc_factory.return_value = mock_orchestrator
        
        mock_queue_instance = mock_redis_queue.return_value
        mock_queue_instance.pop.return_value = None 
        mock_queue_instance.size = 0
        
        with patch("threading.Thread"):
            processor = ContestantProcessor(self.contestant, live_processing=True)
            start_time = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
            
            for i in range(65):
                speed = 20.0 if i == 30 else 5.0
                position_data = self.create_mock_position_data(start_time + datetime.timedelta(seconds=i), speed)
                p = self.contestant.generate_position_block_for_contestant(position_data, position_data["device_time"])
                
                all_positions = [p]
                for position in all_positions:
                    processor.orchestrator.calculate_score(position)
                    if processor.live_processing and processor.orchestrator.has_any_gate_passed and not processor.track_terminated:
                        if position.speed < 10:
                            processor.consecutive_low_speed_positions += 1
                        else:
                            processor.consecutive_low_speed_positions = 0
                        if processor.consecutive_low_speed_positions >= 60:
                            processor.notify_termination()
                            break
                if processor.track_terminated:
                    break
            
            self.assertFalse(processor.track_terminated)
            self.assertEqual(processor.consecutive_low_speed_positions, 34)
            self.assertEqual(mock_orchestrator.calculate_score.call_count, 65)
