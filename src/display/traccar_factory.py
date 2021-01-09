from traccar_facade import Traccar


def get_traccar_instance() -> Traccar:
    from display.models import TraccarCredentials
    configuration = TraccarCredentials.objects.get()
    return Traccar.create_from_configuration(configuration)
