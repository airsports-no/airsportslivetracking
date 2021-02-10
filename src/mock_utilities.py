from unittest.mock import Mock

TraccarMock = Mock()
TraccarMock.get_or_create_device.return_value = ({}, False)
