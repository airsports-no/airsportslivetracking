from django.conf import settings

from traccar_facade import Traccar


def get_traccar_instance() -> Traccar:
    if settings.IS_UNIT_TESTING:
        # Person pre_save and Contestant save/post_save each register devices with
        # traccar. Tests that care about those interactions patch this function
        # themselves; this only keeps the rest of the suite off the network. A fresh
        # mock per call keeps call history from accumulating across the whole session.
        from utilities.mock_utilities import build_traccar_mock

        return build_traccar_mock()
    return Traccar.create_from_configuration()
