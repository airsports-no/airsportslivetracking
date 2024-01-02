import datetime
import logging

import json
import ssl
import threading
from typing import Dict

import requests
import websocket
from androidhelper import Android
droid = Android()
droid.startLocating()
locproviders = droid.locationProviders().result
print("locproviders:"+repr(locproviders))

requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS = "TLS13-CHACHA20-POLY1305-SHA256:TLS13-AES-128-GCM-SHA256:TLS13-AES-256-GCM-SHA384:ECDHE:!COMPLEMENTOFDEFAULT"

from gdl90.encoder import Encoder

logger = logging.getLogger(__name__)
FETCH_INTERVAL = datetime.timedelta(seconds=5)
import socket

UDP_IP = "127.0.0.255"
UDP_PORT = 4000

encoder = Encoder()
s = socket.socket(socket.AF_INET,  # Internet
                  socket.SOCK_DGRAM)  # UDP
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)


print("Started locating")

def transmit_position(message: Dict):
    global s
    if isinstance(message["deviceId"], str):
        address = int.from_bytes(bytes.fromhex(message["deviceId"]), "big")
    else:
        address = message["deviceId"]
    logger.debug(
        f"{message['latitude']}, {message['longitude']}, {message['name']} {message['deviceId']} {address:02x}")
    message = encoder.msgTrafficReport(latitude=message['latitude'], longitude=message["longitude"],
                                       altitude=message.get("baro_altitude", message["altitude"]),
                                       hVelocity=message["speed"],
                                       callSign=message["name"],
                                       address=address,
                                       trackHeading=message["course"])
    s.sendto(message, (UDP_IP, UDP_PORT))
    # logger.debug("Sent message")


def on_message(ws, message):
    data = json.loads(message)
    transmit_position(data)


def on_error(ws, error):
    print(error)


def on_close(ws):
    print("### closed ###")


def get_position():
    # return {
    #     "type": "location",
    #     "latitude": 60,
    #     "longitude": 11,
    #     "range": 40
    # }
    # droid.eventWaitFor('location', int(9000))
    location = droid.getLastKnownLocation().result
    logger.info(f"Location {location}")
    if location and len(location) > 0:
        # print('\n', location)
        key = None
        if 'gps' in location:
            key = 'gps'
        elif 'network' in location:
            key = 'network'
        if key:
            return {
                "type": "location",
                "latitude": location[key]['latitude'],
                "longitude": location[key]['longitude'],
                "range": 80
            }


def on_open(ws):
    p = get_position()
    if p:
        logger.info(f"p {p}")
        ws.send(json.dumps(p))


def periodically_transmit_position(ws):
    p = get_position()
    if p:
        logger.info(f"p {p}")
        ws.send(json.dumps(p))
    threading.Timer(60, periodically_transmit_position, (ws,))


headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36'}

headers['Upgrade'] = 'websocket'

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(threadName)-15s %(name)-15s: %(levelname)-8s %(message)s',
                        datefmt='%d/%m/%Y %H:%M:%S')


    # while True:
    websocket.enableTrace(True)
    # droid.startLocating()
    ws = websocket.WebSocketApp("wss://airsports.no/ws/tracks/global/",
                                on_message=on_message,
                                on_error=on_error,
                                on_open=on_open,
                                on_close=on_close,
                                header=headers)

    threading.Timer(60, periodically_transmit_position, (ws,))

    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
    logger.warning("Websocket terminated, restarting")
    droid.stopLocating()
