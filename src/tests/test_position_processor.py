import datetime
import dateutil.parser
from unittest.mock import MagicMock, patch
import pytest
from position_processor_process import map_positions_to_contestants, CONTESTANT_TYPE

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
