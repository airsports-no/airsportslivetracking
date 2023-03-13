import datetime
import os


if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()
from display.models import Person
from display.serialisers import PersonSerialiserExcludingTracking
from websocket_channels import WebsocketFacade
now = datetime.datetime.now(datetime.timezone.utc)
position = {
    "deviceId": "zOX3bSWKexoAJIlEpT4yx3lou5cl",
    "latitude": 60,
    "longitude": 11,
    "altitude": 0,
    "attributes": {"batteryLevel": 1.0},
    "speed": 0.0,
    "course": 0.0,
    "deviceTime": now.isoformat()
}
websocket=WebsocketFacade()
person = Person.objects.get(app_tracking_id="zOX3bSWKexoAJIlEpT4yx3lou5cl")
websocket.transmit_global_position_data("LN", PersonSerialiserExcludingTracking(person).data, position, now, None)
