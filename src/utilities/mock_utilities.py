from unittest.mock import Mock


def build_traccar_mock() -> Mock:
    """
    A stand-in for Traccar that mirrors the shapes the real client returns.

    get_device must return None rather than an auto-created child Mock: callers do
    `if original_device is not None: traccar.delete_device(original_device["id"])`,
    and a bare Mock is both truthy and not subscriptable, so it would raise TypeError.
    """
    mock = Mock()
    mock.get_or_create_device.return_value = ({}, False)
    mock.get_device_ids_for_contestant.return_value = []
    mock.get_device.return_value = None
    return mock


TraccarMock = build_traccar_mock()
