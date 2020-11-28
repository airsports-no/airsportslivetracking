import os

import secret_configuration

from traccar_facade import Traccar

local_traccar = Traccar(secret_configuration.PROTOCOL, secret_configuration.TRACCAR_ADDRESS, secret_configuration.TOKEN)
new_server = Traccar("https", "traccar.airsports.no", "Fujvpqg8oJWrlhuaHcXXvfRIMfdwGThs")
existing_devices = local_traccar.get_devices()
names = [item["name"] for item in existing_devices]

for item in names:
    new_server.create_device(item)

