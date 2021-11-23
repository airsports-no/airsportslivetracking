import matplotlib.pyplot as plt
import numpy as np
import json
import argparse
from datetime import datetime
from typing import List, Dict

import dateutil
from dateutil import parser
import gpxpy
from requests.auth import HTTPBasicAuth
import requests


# 10977 Espen

def load_config():
    with open('config.json') as f:
        return json.load(f)


def get_data(from_time, to_time):
    config_dic = load_config()
    url = config_dic['root_url'] + '/positions'
    a = HTTPBasicAuth(config_dic['email'], config_dic['password'])
    payload = {
        'deviceId': config_dic['deviceId'],
        'from': datetime.isoformat(from_time) + 'Z',
        'to': datetime.isoformat(to_time) + 'Z'
    }
    # headers = {'Accept': 'application/gpx+xml'}
    headers = {}
    r = requests.get(url, auth=a, params=payload, headers=headers)
    print(url)
    if r.status_code != 200:
        raise ValueError(f'{r.text}')
    positions = r.json()
    for item in positions:
        item["serverTime"] = dateutil.parser.parse(item["serverTime"])
        item["deviceTime"] = dateutil.parser.parse(item["deviceTime"])
        item["fixTime"] = dateutil.parser.parse(item["fixTime"])
    check_order(positions)


def check_order(positions: List[Dict]):
    sorted_positions = sorted(positions, key=lambda k: k["serverTime"])
    print(f"Received {len(sorted_positions)} positions")
    last_position = None
    position_delays = []
    for position in sorted_positions:
        position_delays.append((position["serverTime"] - position["deviceTime"]).total_seconds())
        if last_position and last_position["deviceTime"] > position["deviceTime"]:
            print(f"Position error: {last_position} > {position}")
        last_position = position
    print(f"Maximum delay: {max(position_delays)} seconds")
    plt.hist(position_delays, density=True, bins=30)  # density=False would make counts
    plt.ylabel('Probability')
    plt.xlabel('Seconds')
    plt.savefig("position_delay.png")


if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument('--from_time', default='2021-11-21')
    argparser.add_argument('--to_time', default='2021-11-22')
    args = argparser.parse_args()
    from_time = datetime.strptime(args.from_time, '%Y-%m-%d')
    to_time = datetime.strptime(args.to_time, '%Y-%m-%d')
    get_data(from_time, to_time)
