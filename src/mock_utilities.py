from unittest.mock import Mock

TraccarMock = Mock()
TraccarMock.get_or_create_device.return_value = ({}, False)
TraccarMock.get_device_ids_for_contestant.return_value = []
