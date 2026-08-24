import datetime
import dateutil.parser
from unittest.mock import MagicMock, patch
import pytest
import position_processor_process as ppp
from position_processor_process import map_positions_to_contestants, CONTESTANT_TYPE, add_positions_to_calculator

@patch('position_processor_process.cache')
@patch('position_processor_process.cached_find_contestant')
def test_map_positions_to_multiple_contestants(mocked_find, mock_cache):
    # Mock traccar
    traccar = MagicMock()
    traccar.device_map = {"device1": "device_name1"}
    
    # Mock positions
    now = datetime.datetime.now(datetime.timezone.utc)
    device_time_str = now.isoformat().replace("+00:00", "Z")
    server_time_str = now.isoformat().replace("+00:00", "Z")
    positions = [
        {
            "deviceId": "device1",
            "deviceTime": device_time_str,
            "serverTime": server_time_str,
            "latitude": 60.0,
            "longitude": 10.0,
            "altitude": 1000,
            "speed": 70,
            "course": 180,
            "attributes": {"id": 123}
        }
    ]
    
    # Mock global_map_queue
    global_map_queue = MagicMock()
    
    # Mock contestants
    contestant1 = MagicMock()
    contestant1.pk = 101
    contestant2 = MagicMock()
    contestant2.pk = 102
    
    # Mock cache to allow the position to pass (not seen before)
    mock_cache.get.return_value = None
    
    # Mock cached_find_contestant to return multiple contestants with different simulator flags
    mocked_find.return_value = [(contestant1, False), (contestant2, True)]
    
    # Call the function
    received_tracks = map_positions_to_contestants(traccar, positions, global_map_queue)
    
    # 1. Check if received_tracks contains both contestants as keys
    assert contestant1 in received_tracks
    assert contestant2 in received_tracks
    
    # 2. Check if the position data was appended to each contestant's track
    assert len(received_tracks[contestant1]) == 1
    assert len(received_tracks[contestant2]) == 1
    assert received_tracks[contestant1][0]["deviceId"] == "device1"
    assert received_tracks[contestant2][0]["deviceId"] == "device1"
    
    # 3. Check if global_map_queue.put was called for each contestant
    assert global_map_queue.put.call_count == 2
    
    calls = global_map_queue.put.call_args_list
    
    # Expected message format: (CONTESTANT_TYPE, contestant.pk, position_data, device_time, is_simulator)
    
    # Validate first contestant (contestant1, not simulator)
    msg1 = calls[0][0][0]
    assert msg1[0] == CONTESTANT_TYPE
    assert msg1[1] == 101
    assert msg1[2]["deviceId"] == "device1"
    assert msg1[3] == dateutil.parser.parse(device_time_str)
    assert msg1[4] is False
    
    # Validate second contestant (contestant2, is simulator)
    msg2 = calls[1][0][0]
    assert msg2[0] == CONTESTANT_TYPE
    assert msg2[1] == 102
    assert msg2[2]["deviceId"] == "device1"
    assert msg2[3] == dateutil.parser.parse(device_time_str)
    assert msg2[4] is True


class TestAddPositionsToCalculatorDispatchLock:
    """
    add_positions_to_calculator runs once per contestant for every incoming
    position batch, i.e. continuously for the whole flight, not just on first
    dispatch. It used to unconditionally build a fresh Redis connection and
    acquire a distributed lock on every single call just to read two cache
    keys it usually already knows the answer to from the local `processes`
    dict - these tests lock in the fast, unlocked path added to fix that,
    and confirm the locked path is still taken when a dispatch decision is
    genuinely needed.
    """

    def teardown_method(self):
        ppp.processes.clear()

    @patch("position_processor_process.redis_lock.Lock")
    @patch("position_processor_process.is_dispatch_pending", return_value=False)
    @patch("position_processor_process.is_calculator_running", return_value=True)
    def test_skips_lock_when_already_known_running(self, mock_running, mock_pending, mock_lock_cls):
        contestant = MagicMock()
        contestant.pk = 900001
        fake_queue = MagicMock()
        ppp.processes[contestant.pk] = (fake_queue, None)

        add_positions_to_calculator(contestant, [{"id": 1}, {"id": 2}])

        mock_lock_cls.assert_not_called()
        assert fake_queue.append.call_count == 2

    @patch("position_processor_process.redis_lock.Lock")
    @patch("position_processor_process.is_dispatch_pending", return_value=False)
    @patch("position_processor_process.is_calculator_running", return_value=False)
    def test_still_appends_positions_when_running_but_not_yet_confirmed(
        self, mock_running, mock_pending, mock_lock_cls
    ):
        # key already in `processes` (a task was dispatched) but the
        # heartbeat/pending signals both read False right now - this must
        # still take the locked path (a real dead-calculator recovery could
        # be needed), not silently skip dispatch.
        contestant = MagicMock()
        contestant.pk = 900002
        fake_queue = MagicMock()
        ppp.processes[contestant.pk] = (fake_queue, None)

        with patch("position_processor_process.settings") as mock_settings:
            mock_settings.CALCULATOR_DISPATCH_VIA_CELERY = False
            with (
                patch("position_processor_process.RedisQueue", return_value=MagicMock()),
                patch("position_processor_process.Process"),
                patch("position_processor_process.calculator_is_alive"),
                patch("position_processor_process._get_dispatch_lock_connection"),
            ):
                add_positions_to_calculator(contestant, [])

        mock_lock_cls.assert_called_once()

    @patch("position_processor_process.redis_lock.Lock")
    @patch("position_processor_process._get_dispatch_lock_connection")
    @patch("position_processor_process.is_dispatch_pending", return_value=False)
    @patch("position_processor_process.is_calculator_running", return_value=False)
    def test_acquires_lock_on_first_dispatch(self, mock_running, mock_pending, mock_conn, mock_lock_cls):
        contestant = MagicMock()
        contestant.pk = 900003
        # Not in processes at all - genuinely the first sighting of this contestant.
        assert contestant.pk not in ppp.processes

        with patch("position_processor_process.settings") as mock_settings:
            mock_settings.CALCULATOR_DISPATCH_VIA_CELERY = False
            with patch("position_processor_process.RedisQueue", return_value=MagicMock()), patch(
                "position_processor_process.Process"
            ), patch("position_processor_process.calculator_is_alive"):
                add_positions_to_calculator(contestant, [])

        mock_lock_cls.assert_called_once()
        mock_conn.assert_called_once()
