import json
import argparse
from datetime import datetime

from dateutil import parser
import gpxpy
from requests.auth import HTTPBasicAuth
import requests


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
    create_gpx(r.json())
    with open('my-data.json', 'w') as f:
        f.write(r.text)


def create_gpx(positions):
    gpx = gpxpy.gpx.GPX()
    track = gpxpy.gpx.GPXTrack()
    gpx.tracks.append(track)
    segment = gpxpy.gpx.GPXTrackSegment()
    track.segments.append(segment)
    for position in positions:
        segment.points.append(
            gpxpy.gpx.GPXTrackPoint(position["latitude"], position["longitude"], elevation=position["altitude"],
                                    time=parser.parse(position["deviceTime"])))
    with open("track.gpx", "w") as f:
        f.write(gpx.to_xml())


if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument('--from_time', default='2021-03-23')
    argparser.add_argument('--to_time', default='2021-03-24')
    args = argparser.parse_args()
    from_time = datetime.strptime(args.from_time, '%Y-%m-%d')
    to_time = datetime.strptime(args.to_time, '%Y-%m-%d')
    get_data(from_time, to_time)
