from traccar_facade import Traccar


def get_traccar_instance() -> Traccar:
    return Traccar.create_from_configuration()
