import datetime
import sys
import threading
import time
import logging
import os
import requests
requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS = "TLS13-CHACHA20-POLY1305-SHA256:TLS13-AES-128-GCM-SHA256:TLS13-AES-256-GCM-SHA384:ECDHE:!COMPLEMENTOFDEFAULT"

from opensky_api import OpenSkyApi
from requests import ReadTimeout

import gdl90
from gdl90.encoder import Encoder

logger = logging.getLogger(__name__)
FETCH_INTERVAL = datetime.timedelta(seconds=5)
import socket

UDP_IP = "127.0.0.255"
UDP_PORT = 4000

print("UDP target IP: %s" % UDP_IP)
print("UDP target port: %s" % UDP_PORT)
total_packets = 0
encoder = Encoder()


def transmit_positions(socket, states):
    global total_packets
    for state in states:
        if state.time_position and state.latitude and state.longitude and state.velocity and state.geo_altitude:
            altitude_feet = state.geo_altitude * 3.281
            timestamp = datetime.datetime.fromtimestamp(state.time_position, datetime.timezone.utc)
            address = int.from_bytes(bytes.fromhex(state.icao24), "big")
            logger.debug(f"{state.latitude}, {state.longitude}, {state.callsign} {state.icao24} {address:02x}")
            message = encoder.msgTrafficReport(latitude=state.latitude, longitude=state.longitude,
                                               altitude=state.geo_altitude, hVelocity=state.velocity * 1,
                                               callSign=state.callsign,
                                               address=address,
                                               trackHeading=state.heading)
            socket.sendto(message, (UDP_IP, UDP_PORT))
            total_packets += 1
            logger.debug("Sent message")


def transmit_ownship(socket):
    global total_packets
    message = encoder.msgOwnershipReport(latitude=60, longitude=11, altitude=200, callSign="Me")
    socket.sendto(message, (UDP_IP, UDP_PORT))
    total_packets += 1
    message = encoder.msgOwnershipGeometricAltitude(altitude=200)
    socket.sendto(message, (UDP_IP, UDP_PORT))
    total_packets += 1

towers = [
    (60, 11, 'HYI01'),
]
def print_bytes(to_print, joiner: str = " ") -> str:
    try:
        return joiner.join(["%02X" % x for x in to_print])
    except Exception as exception:
        logger.exception("Failed printing string {} as hex string".format(to_print))
        return str(to_print)

traffic = [
        (61, 11.1, 3000, 100, 500, 45, 'NBNDT1', 0x000001),
    ]

def test_messages():
    """
    expected:
    7E 14 00 00 00 01 15 C2 8F BA 4F A5 0A 09 88 06 40 07 20 01 4E 42 4E 44 54 31 20 20 00 E5 1A 7E
    7E 14 00 00 00 02 15 C2 8F BA 06 D4 08 C9 88 07 80 00 D1 01 4E 42 4E 44 54 32 20 20 00 98 4B 7E
    7E 14 00 00 00 03 15 76 19 BA 37 FB 0A 89 88 09 6F FE CA 01 4E 42 4E 44 54 33 20 20 00 0A 90 7E
    7E 14 00 00 00 04 15 6C FF BA 19 08 07 89 88 06 E0 03 07 01 4E 42 4E 44 54 34 20 20 00 CC AC 7E
    actual:
    7E 14 00 00 00 01 15 C2 8F BA 4F A5 0A 09 88 06 40 07 20 01 4E 42 4E 44 54 31 20 20 00 E5 1A 7E
    7E 14 00 00 00 02 15 C2 8F BA 06 D4 08 C9 88 07 80 00 D1 01 4E 42 4E 44 54 32 20 20 00 98 4B 7E
    7E 14 00 00 00 03 15 76 19 BA 37 FB 0A 89 88 09 6F FF CA 01 4E 42 4E 44 54 33 20 20 00 4F FF 7E
    7E 14 00 00 00 04 15 6C FF BA 19 08 07 89 88 06 E0 03 07 01 4E 42 4E 44 54 34 20 20 00 CC AC 7E
    :return:
    """
    traffic = [
        (30.60, -98.00, 3000, 100, 500, 45, 'NBNDT1', 0x000001),
        (30.60, -98.40, 2500, 120, 0, 295, 'NBNDT2', 0x000002),
        (30.18, -98.13, 3200, 150, -100, 285, 'NBNDT3', 0x000003),
        (30.13, -98.30, 2000, 110, 250, 10, 'NBNDT4', 0x000004),
    ]
    for t in traffic:
        (tlat, tlong, talt, tspeed, tvspeed, thdg, tcall, taddr) = t
        buf = encoder.msgTrafficReport(latitude=tlat, longitude=tlong, altitude=talt, hVelocity=tspeed,
                                       vVelocity=tvspeed, trackHeading=thdg, callSign=tcall, address=taddr)
        print(print_bytes(buf))


def transmit_ownship_reports(s):
    global total_packets
    buf = encoder.msgHeartbeat()
    s.sendto(buf, (UDP_IP, UDP_PORT))
    total_packets += 1
    buf = encoder.msgStratuxHeartbeat()
    s.sendto(buf, (UDP_IP, UDP_PORT))
    total_packets += 1
    buf = encoder.msgSXHeartbeat(towers=[])
    s.sendto(buf, (UDP_IP, UDP_PORT))
    total_packets += 1
    transmit_ownship(s)
    message = encoder.msgGpsTime(count=total_packets)
    s.sendto(message, (UDP_IP, UDP_PORT))
    total_packets += 1
    threading.Timer(1, transmit_ownship_reports, (s,)).start()

if __name__ == "__main__":
    # test_messages()
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(threadName)-15s %(name)-15s: %(levelname)-8s %(message)s',
                        datefmt='%d/%m/%Y %H:%M:%S')

    s = socket.socket(socket.AF_INET,  # Internet
                      socket.SOCK_DGRAM)  # UDP
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    # username, password = sys.argv[1:]
    username, password = "kolaf", "fypRL64DRuNGKyG"
    api = OpenSkyApi(username, password)
    transmit_ownship_reports(s)
    while True:
        # for t in traffic:
        #     (tlat, tlong, talt, tspeed, tvspeed, thdg, tcall, taddr) = t
        #     buf = encoder.msgTrafficReport(latitude=tlat, longitude=tlong, altitude=talt, hVelocity=tspeed,
        #                                    vVelocity=tvspeed, trackHeading=thdg, callSign=tcall, address=taddr)
        #     s.sendto(buf, (UDP_IP, UDP_PORT))
        #     total_packets += 1
        # time.sleep(5)
        # continue
        try:
            response = api.get_states(bbox=(58, 62, 9, 12))
        except ReadTimeout:
            time.sleep(3)
            continue
        last_fetch = datetime.datetime.now()

        if response:
            logger.info(f"Received {len(response.states)} states")
            transmit_positions(s, response.states)
            logger.info("Done")
            elapsed = datetime.datetime.now() - last_fetch
            sleep_interval = max(2, (FETCH_INTERVAL - elapsed).total_seconds())
            logger.info(f"Elapsed {elapsed.total_seconds()}, sleeping {sleep_interval}")
            time.sleep(sleep_interval)
        else:
            logger.warning("Failed fetching")
            time.sleep(1)
