import base64
import json
from unittest.mock import Mock

from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TransactionTestCase
from rest_framework.test import APITestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Contest, NavigationTask
from display.serialisers import ExternalNavigationTaskNestedSerialiser

data = {
    "contestant_set": [
        {
            "id": 23,
            "team": {
                "id": 23,
                "aeroplane": {
                    "id": 1,
                    "registration": "LN-YDB",
                    "colour": "",
                    "type": ""
                },
                "crew": {
                    "pilot": "pilot"
                },
                "nation": "Norway"
            },
            "gate_times": {
                "SP": "2020-08-01T08:06:00Z",
                "SC 1/1": "2020-08-01T08:07:47.777621Z",
                "TP1": "2020-08-01T08:12:58.229939Z",
                "SC 2/1": "2020-08-01T08:16:00.945257Z",
                "TP2": "2020-08-01T08:18:37.703942Z",
                "SC 3/1": "2020-08-01T08:20:24.127429Z",
                "SC 3/2": "2020-08-01T08:22:58.527963Z",
                "TP3": "2020-08-01T08:27:35.440298Z",
                "TP4": "2020-08-01T08:31:55.786556Z",
                "SC 5/1": "2020-08-01T08:35:35.660024Z",
                "TP5": "2020-08-01T08:39:25.622820Z",
                "SC 6/1": "2020-08-01T08:42:27.912264Z",
                "TP6": "2020-08-01T08:48:40.701664Z",
                "SC 7/1": "2020-08-01T08:51:27.611618Z",
                "SC 7/2": "2020-08-01T08:55:36.733318Z",
                "FP": "2020-08-01T08:59:38.293518Z"
            },
            "scorecard": "FAI Precision 2020",
            "takeoff_time": "2020-08-01T08:00:00Z",
            "minutes_to_starting_point": 6,
            "finished_by_time": "2020-08-01T10:00:00Z",
            "air_speed": 75,
            "contestant_number": 0,
            "traccar_device_name": "Anders",
            "tracker_start_time": "0001-01-01T00:00:00Z",
            "wind_speed": 0,
            "wind_direction": 0
        },
        {
            "id": 24,
            "team": {
                "id": 24,
                "aeroplane": {
                    "id": 1,
                    "registration": "LN-YDB",
                    "colour": "",
                    "type": ""
                },
                "crew": {
                    "pilot": "pilot"
                },
                "nation": "Norway"
            },
            "gate_times": {
                "SP": "2020-08-01T08:16:00Z",
                "SC 1/1": "2020-08-01T08:17:55.476023Z",
                "TP1": "2020-08-01T08:23:28.103507Z",
                "SC 2/1": "2020-08-01T08:26:39.584205Z",
                "TP2": "2020-08-01T08:29:27.539939Z",
                "SC 3/1": "2020-08-01T08:31:21.565103Z",
                "SC 3/2": "2020-08-01T08:34:06.994246Z",
                "TP3": "2020-08-01T08:39:03.686033Z",
                "TP4": "2020-08-01T08:43:42.628452Z",
                "SC 5/1": "2020-08-01T08:47:33.921454Z",
                "TP5": "2020-08-01T08:51:40.310164Z",
                "SC 6/1": "2020-08-01T08:54:55.620283Z",
                "TP6": "2020-08-01T09:01:35.037497Z",
                "SC 7/1": "2020-08-01T09:04:29.583876Z",
                "SC 7/2": "2020-08-01T09:08:56.499983Z",
                "FP": "2020-08-01T09:13:15.314483Z"
            },
            "scorecard": "FAI Precision 2020",
            "takeoff_time": "2020-08-01T08:10:00Z",
            "minutes_to_starting_point": 6,
            "finished_by_time": "2020-08-01T10:10:00Z",
            "air_speed": 70,
            "contestant_number": 1,
            "traccar_device_name": "Arild",
            "tracker_start_time": "0001-01-01T00:00:00Z",
            "wind_speed": 0,
            "wind_direction": 0
        },
        {
            "id": 25,
            "team": {
                "id": 25,
                "aeroplane": {
                    "id": 1,
                    "registration": "LN-YDB",
                    "colour": "",
                    "type": ""
                },
                "crew": {
                    "pilot": "pilot"
                },
                "nation": "Norway"
            },
            "gate_times": {
                "SP": "2020-08-01T07:21:00Z",
                "SC 1/1": "2020-08-01T07:22:55.476023Z",
                "TP1": "2020-08-01T07:28:28.103507Z",
                "SC 2/1": "2020-08-01T07:31:39.584205Z",
                "TP2": "2020-08-01T07:34:27.539939Z",
                "SC 3/1": "2020-08-01T07:36:21.565103Z",
                "SC 3/2": "2020-08-01T07:39:06.994246Z",
                "TP3": "2020-08-01T07:44:03.686033Z",
                "TP4": "2020-08-01T07:48:42.628452Z",
                "SC 5/1": "2020-08-01T07:52:33.921454Z",
                "TP5": "2020-08-01T07:56:40.310164Z",
                "SC 6/1": "2020-08-01T07:59:55.620283Z",
                "TP6": "2020-08-01T08:06:35.037497Z",
                "SC 7/1": "2020-08-01T08:09:29.583876Z",
                "SC 7/2": "2020-08-01T08:13:56.499983Z",
                "FP": "2020-08-01T08:18:15.314483Z"
            },
            "scorecard": "FAI Precision 2020",
            "takeoff_time": "2020-08-01T07:15:00Z",
            "minutes_to_starting_point": 6,
            "finished_by_time": "2020-08-01T09:15:00Z",
            "air_speed": 70,
            "contestant_number": 2,
            "traccar_device_name": "Bjørn",
            "tracker_start_time": "0001-01-01T00:00:00Z",
            "wind_speed": 0,
            "wind_direction": 0
        },
        {
            "id": 26,
            "team": {
                "id": 26,
                "aeroplane": {
                    "id": 1,
                    "registration": "LN-YDB",
                    "colour": "",
                    "type": ""
                },
                "crew": {
                    "pilot": "pilot"
                },
                "nation": "Norway"
            },
            "gate_times": {
                "SP": "2020-08-01T09:16:00Z",
                "SC 1/1": "2020-08-01T09:17:55.476023Z",
                "TP1": "2020-08-01T09:23:28.103507Z",
                "SC 2/1": "2020-08-01T09:26:39.584205Z",
                "TP2": "2020-08-01T09:29:27.539939Z",
                "SC 3/1": "2020-08-01T09:31:21.565103Z",
                "SC 3/2": "2020-08-01T09:34:06.994246Z",
                "TP3": "2020-08-01T09:39:03.686033Z",
                "TP4": "2020-08-01T09:43:42.628452Z",
                "SC 5/1": "2020-08-01T09:47:33.921454Z",
                "TP5": "2020-08-01T09:51:40.310164Z",
                "SC 6/1": "2020-08-01T09:54:55.620283Z",
                "TP6": "2020-08-01T10:01:35.037497Z",
                "SC 7/1": "2020-08-01T10:04:29.583876Z",
                "SC 7/2": "2020-08-01T10:08:56.499983Z",
                "FP": "2020-08-01T10:13:15.314483Z"
            },
            "scorecard": "FAI Precision 2020",
            "takeoff_time": "2020-08-01T09:10:00Z",
            "minutes_to_starting_point": 6,
            "finished_by_time": "2020-08-01T11:10:00Z",
            "air_speed": 70,
            "contestant_number": 3,
            "traccar_device_name": "Espen",
            "tracker_start_time": "0001-01-01T00:00:00Z",
            "wind_speed": 0,
            "wind_direction": 0
        },
        {
            "id": 27,
            "team": {
                "id": 27,
                "aeroplane": {
                    "id": 1,
                    "registration": "LN-YDB",
                    "colour": "",
                    "type": ""
                },
                "crew": {
                    "pilot": "pilot"
                },
                "nation": "Norway"
            },
            "gate_times": {
                "SP": "2020-08-01T08:11:00Z",
                "SC 1/1": "2020-08-01T08:12:47.777621Z",
                "TP1": "2020-08-01T08:17:58.229939Z",
                "SC 2/1": "2020-08-01T08:21:00.945257Z",
                "TP2": "2020-08-01T08:23:37.703942Z",
                "SC 3/1": "2020-08-01T08:25:24.127429Z",
                "SC 3/2": "2020-08-01T08:27:58.527963Z",
                "TP3": "2020-08-01T08:32:35.440298Z",
                "TP4": "2020-08-01T08:36:55.786556Z",
                "SC 5/1": "2020-08-01T08:40:35.660024Z",
                "TP5": "2020-08-01T08:44:25.622820Z",
                "SC 6/1": "2020-08-01T08:47:27.912264Z",
                "TP6": "2020-08-01T08:53:40.701664Z",
                "SC 7/1": "2020-08-01T08:56:27.611618Z",
                "SC 7/2": "2020-08-01T09:00:36.733318Z",
                "FP": "2020-08-01T09:04:38.293518Z"
            },
            "scorecard": "FAI Precision 2020",
            "takeoff_time": "2020-08-01T08:05:00Z",
            "minutes_to_starting_point": 6,
            "finished_by_time": "2020-08-01T10:05:00Z",
            "air_speed": 75,
            "contestant_number": 4,
            "traccar_device_name": "Frank-Olaf",
            "tracker_start_time": "0001-01-01T00:00:00Z",
            "wind_speed": 0,
            "wind_direction": 0
        },
        {
            "id": 28,
            "team": {
                "id": 28,
                "aeroplane": {
                    "id": 1,
                    "registration": "LN-YDB",
                    "colour": "",
                    "type": ""
                },
                "crew": {
                    "pilot": "pilot"
                },
                "nation": "Norway"
            },
            "gate_times": {
                "SP": "2020-08-01T07:56:00Z",
                "SC 1/1": "2020-08-01T07:57:35.097901Z",
                "TP1": "2020-08-01T08:02:09.026417Z",
                "SC 2/1": "2020-08-01T08:04:57.304639Z",
                "TP2": "2020-08-01T08:07:15.621126Z",
                "SC 3/1": "2020-08-01T08:08:49.524202Z",
                "SC 3/2": "2020-08-01T08:11:05.759967Z",
                "TP3": "2020-08-01T08:15:10.094380Z",
                "TP4": "2020-08-01T08:18:59.811666Z",
                "SC 5/1": "2020-08-01T08:22:20.876491Z",
                "TP5": "2020-08-01T08:25:43.784841Z",
                "SC 6/1": "2020-08-01T08:28:24.628468Z",
                "TP6": "2020-08-01T08:33:53.560291Z",
                "SC 7/1": "2020-08-01T08:36:27.892603Z",
                "SC 7/2": "2020-08-01T08:40:07.705867Z",
                "FP": "2020-08-01T08:43:40.847220Z"
            },
            "scorecard": "FAI Precision 2020",
            "takeoff_time": "2020-08-01T07:50:00Z",
            "minutes_to_starting_point": 6,
            "finished_by_time": "2020-08-01T09:50:00Z",
            "air_speed": 85,
            "contestant_number": 5,
            "traccar_device_name": "Hans-Inge",
            "tracker_start_time": "0001-01-01T00:00:00Z",
            "wind_speed": 0,
            "wind_direction": 0
        },
        {
            "id": 29,
            "team": {
                "id": 29,
                "aeroplane": {
                    "id": 1,
                    "registration": "LN-YDB",
                    "colour": "",
                    "type": ""
                },
                "crew": {
                    "pilot": "pilot"
                },
                "nation": "Norway"
            },
            "gate_times": {
                "SP": "2020-08-01T11:11:00Z",
                "SC 1/1": "2020-08-01T11:12:55.476023Z",
                "TP1": "2020-08-01T11:18:28.103507Z",
                "SC 2/1": "2020-08-01T11:21:39.584205Z",
                "TP2": "2020-08-01T11:24:27.539939Z",
                "SC 3/1": "2020-08-01T11:26:21.565103Z",
                "SC 3/2": "2020-08-01T11:29:06.994246Z",
                "TP3": "2020-08-01T11:34:03.686033Z",
                "TP4": "2020-08-01T11:38:42.628452Z",
                "SC 5/1": "2020-08-01T11:42:33.921454Z",
                "TP5": "2020-08-01T11:46:40.310164Z",
                "SC 6/1": "2020-08-01T11:49:55.620283Z",
                "TP6": "2020-08-01T11:56:35.037497Z",
                "SC 7/1": "2020-08-01T11:59:29.583876Z",
                "SC 7/2": "2020-08-01T12:03:56.499983Z",
                "FP": "2020-08-01T12:08:15.314483Z"
            },
            "scorecard": "FAI Precision 2020",
            "takeoff_time": "2020-08-01T11:05:00Z",
            "minutes_to_starting_point": 6,
            "finished_by_time": "2020-08-01T13:05:00Z",
            "air_speed": 70,
            "contestant_number": 6,
            "traccar_device_name": "Hedvig",
            "tracker_start_time": "0001-01-01T00:00:00Z",
            "wind_speed": 0,
            "wind_direction": 0
        },
        {
            "id": 30,
            "team": {
                "id": 30,
                "aeroplane": {
                    "id": 1,
                    "registration": "LN-YDB",
                    "colour": "",
                    "type": ""
                },
                "crew": {
                    "pilot": "pilot"
                },
                "nation": "Norway"
            },
            "gate_times": {
                "SP": "2020-08-01T11:01:00Z",
                "SC 1/1": "2020-08-01T11:02:47.777621Z",
                "TP1": "2020-08-01T11:07:58.229939Z",
                "SC 2/1": "2020-08-01T11:11:00.945257Z",
                "TP2": "2020-08-01T11:13:37.703942Z",
                "SC 3/1": "2020-08-01T11:15:24.127429Z",
                "SC 3/2": "2020-08-01T11:17:58.527963Z",
                "TP3": "2020-08-01T11:22:35.440298Z",
                "TP4": "2020-08-01T11:26:55.786556Z",
                "SC 5/1": "2020-08-01T11:30:35.660024Z",
                "TP5": "2020-08-01T11:34:25.622820Z",
                "SC 6/1": "2020-08-01T11:37:27.912264Z",
                "TP6": "2020-08-01T11:43:40.701664Z",
                "SC 7/1": "2020-08-01T11:46:27.611618Z",
                "SC 7/2": "2020-08-01T11:50:36.733318Z",
                "FP": "2020-08-01T11:54:38.293518Z"
            },
            "scorecard": "FAI Precision 2020",
            "takeoff_time": "2020-08-01T10:55:00Z",
            "minutes_to_starting_point": 6,
            "finished_by_time": "2020-08-01T12:55:00Z",
            "air_speed": 75,
            "contestant_number": 7,
            "traccar_device_name": "Helge",
            "tracker_start_time": "0001-01-01T00:00:00Z",
            "wind_speed": 0,
            "wind_direction": 0
        },
        {
            "id": 31,
            "team": {
                "id": 31,
                "aeroplane": {
                    "id": 1,
                    "registration": "LN-YDB",
                    "colour": "",
                    "type": ""
                },
                "crew": {
                    "pilot": "pilot"
                },
                "nation": "Norway"
            },
            "gate_times": {
                "SP": "2020-08-01T09:21:00Z",
                "SC 1/1": "2020-08-01T09:22:55.476023Z",
                "TP1": "2020-08-01T09:28:28.103507Z",
                "SC 2/1": "2020-08-01T09:31:39.584205Z",
                "TP2": "2020-08-01T09:34:27.539939Z",
                "SC 3/1": "2020-08-01T09:36:21.565103Z",
                "SC 3/2": "2020-08-01T09:39:06.994246Z",
                "TP3": "2020-08-01T09:44:03.686033Z",
                "TP4": "2020-08-01T09:48:42.628452Z",
                "SC 5/1": "2020-08-01T09:52:33.921454Z",
                "TP5": "2020-08-01T09:56:40.310164Z",
                "SC 6/1": "2020-08-01T09:59:55.620283Z",
                "TP6": "2020-08-01T10:06:35.037497Z",
                "SC 7/1": "2020-08-01T10:09:29.583876Z",
                "SC 7/2": "2020-08-01T10:13:56.499983Z",
                "FP": "2020-08-01T10:18:15.314483Z"
            },
            "scorecard": "FAI Precision 2020",
            "takeoff_time": "2020-08-01T09:15:00Z",
            "minutes_to_starting_point": 6,
            "finished_by_time": "2020-08-01T11:15:00Z",
            "air_speed": 70,
            "contestant_number": 8,
            "traccar_device_name": "Håkon",
            "tracker_start_time": "0001-01-01T00:00:00Z",
            "wind_speed": 0,
            "wind_direction": 0
        },
        {
            "id": 32,
            "team": {
                "id": 32,
                "aeroplane": {
                    "id": 1,
                    "registration": "LN-YDB",
                    "colour": "",
                    "type": ""
                },
                "crew": {
                    "pilot": "pilot"
                },
                "nation": "Norway"
            },
            "gate_times": {
                "SP": "2020-08-01T07:16:00Z",
                "SC 1/1": "2020-08-01T07:17:55.476023Z",
                "TP1": "2020-08-01T07:23:28.103507Z",
                "SC 2/1": "2020-08-01T07:26:39.584205Z",
                "TP2": "2020-08-01T07:29:27.539939Z",
                "SC 3/1": "2020-08-01T07:31:21.565103Z",
                "SC 3/2": "2020-08-01T07:34:06.994246Z",
                "TP3": "2020-08-01T07:39:03.686033Z",
                "TP4": "2020-08-01T07:43:42.628452Z",
                "SC 5/1": "2020-08-01T07:47:33.921454Z",
                "TP5": "2020-08-01T07:51:40.310164Z",
                "SC 6/1": "2020-08-01T07:54:55.620283Z",
                "TP6": "2020-08-01T08:01:35.037497Z",
                "SC 7/1": "2020-08-01T08:04:29.583876Z",
                "SC 7/2": "2020-08-01T08:08:56.499983Z",
                "FP": "2020-08-01T08:13:15.314483Z"
            },
            "scorecard": "FAI Precision 2020",
            "takeoff_time": "2020-08-01T07:10:00Z",
            "minutes_to_starting_point": 6,
            "finished_by_time": "2020-08-01T09:10:00Z",
            "air_speed": 70,
            "contestant_number": 9,
            "traccar_device_name": "Jorge",
            "tracker_start_time": "0001-01-01T00:00:00Z",
            "wind_speed": 0,
            "wind_direction": 0
        },
        {
            "id": 33,
            "team": {
                "id": 33,
                "aeroplane": {
                    "id": 1,
                    "registration": "LN-YDB",
                    "colour": "",
                    "type": ""
                },
                "crew": {
                    "pilot": "pilot"
                },
                "nation": "Norway"
            },
            "gate_times": {
                "SP": "2020-08-01T09:01:00Z",
                "SC 1/1": "2020-08-01T09:02:47.777621Z",
                "TP1": "2020-08-01T09:07:58.229939Z",
                "SC 2/1": "2020-08-01T09:11:00.945257Z",
                "TP2": "2020-08-01T09:13:37.703942Z",
                "SC 3/1": "2020-08-01T09:15:24.127429Z",
                "SC 3/2": "2020-08-01T09:17:58.527963Z",
                "TP3": "2020-08-01T09:22:35.440298Z",
                "TP4": "2020-08-01T09:26:55.786556Z",
                "SC 5/1": "2020-08-01T09:30:35.660024Z",
                "TP5": "2020-08-01T09:34:25.622820Z",
                "SC 6/1": "2020-08-01T09:37:27.912264Z",
                "TP6": "2020-08-01T09:43:40.701664Z",
                "SC 7/1": "2020-08-01T09:46:27.611618Z",
                "SC 7/2": "2020-08-01T09:50:36.733318Z",
                "FP": "2020-08-01T09:54:38.293518Z"
            },
            "scorecard": "FAI Precision 2020",
            "takeoff_time": "2020-08-01T08:55:00Z",
            "minutes_to_starting_point": 6,
            "finished_by_time": "2020-08-01T10:55:00Z",
            "air_speed": 75,
            "contestant_number": 10,
            "traccar_device_name": "Jørgen",
            "tracker_start_time": "0001-01-01T00:00:00Z",
            "wind_speed": 0,
            "wind_direction": 0
        },
        {
            "id": 34,
            "team": {
                "id": 34,
                "aeroplane": {
                    "id": 1,
                    "registration": "LN-YDB",
                    "colour": "",
                    "type": ""
                },
                "crew": {
                    "pilot": "pilot"
                },
                "nation": "Norway"
            },
            "gate_times": {
                "SP": "2020-08-01T07:11:00Z",
                "SC 1/1": "2020-08-01T07:12:55.476023Z",
                "TP1": "2020-08-01T07:18:28.103507Z",
                "SC 2/1": "2020-08-01T07:21:39.584205Z",
                "TP2": "2020-08-01T07:24:27.539939Z",
                "SC 3/1": "2020-08-01T07:26:21.565103Z",
                "SC 3/2": "2020-08-01T07:29:06.994246Z",
                "TP3": "2020-08-01T07:34:03.686033Z",
                "TP4": "2020-08-01T07:38:42.628452Z",
                "SC 5/1": "2020-08-01T07:42:33.921454Z",
                "TP5": "2020-08-01T07:46:40.310164Z",
                "SC 6/1": "2020-08-01T07:49:55.620283Z",
                "TP6": "2020-08-01T07:56:35.037497Z",
                "SC 7/1": "2020-08-01T07:59:29.583876Z",
                "SC 7/2": "2020-08-01T08:03:56.499983Z",
                "FP": "2020-08-01T08:08:15.314483Z"
            },
            "scorecard": "FAI Precision 2020",
            "takeoff_time": "2020-08-01T07:05:00Z",
            "minutes_to_starting_point": 6,
            "finished_by_time": "2020-08-01T09:05:00Z",
            "air_speed": 70,
            "contestant_number": 11,
            "traccar_device_name": "Kenneth",
            "tracker_start_time": "0001-01-01T00:00:00Z",
            "wind_speed": 0,
            "wind_direction": 0
        },
        {
            "id": 35,
            "team": {
                "id": 35,
                "aeroplane": {
                    "id": 1,
                    "registration": "LN-YDB",
                    "colour": "",
                    "type": ""
                },
                "crew": {
                    "pilot": "pilot"
                },
                "nation": "Norway"
            },
            "gate_times": {
                "SP": "2020-08-01T09:11:00Z",
                "SC 1/1": "2020-08-01T09:12:55.476023Z",
                "TP1": "2020-08-01T09:18:28.103507Z",
                "SC 2/1": "2020-08-01T09:21:39.584205Z",
                "TP2": "2020-08-01T09:24:27.539939Z",
                "SC 3/1": "2020-08-01T09:26:21.565103Z",
                "SC 3/2": "2020-08-01T09:29:06.994246Z",
                "TP3": "2020-08-01T09:34:03.686033Z",
                "TP4": "2020-08-01T09:38:42.628452Z",
                "SC 5/1": "2020-08-01T09:42:33.921454Z",
                "TP5": "2020-08-01T09:46:40.310164Z",
                "SC 6/1": "2020-08-01T09:49:55.620283Z",
                "TP6": "2020-08-01T09:56:35.037497Z",
                "SC 7/1": "2020-08-01T09:59:29.583876Z",
                "SC 7/2": "2020-08-01T10:03:56.499983Z",
                "FP": "2020-08-01T10:08:15.314483Z"
            },
            "scorecard": "FAI Precision 2020",
            "takeoff_time": "2020-08-01T09:05:00Z",
            "minutes_to_starting_point": 6,
            "finished_by_time": "2020-08-01T11:05:00Z",
            "air_speed": 70,
            "contestant_number": 12,
            "traccar_device_name": "Magnus",
            "tracker_start_time": "0001-01-01T00:00:00Z",
            "wind_speed": 0,
            "wind_direction": 0
        },
        {
            "id": 36,
            "team": {
                "id": 36,
                "aeroplane": {
                    "id": 1,
                    "registration": "LN-YDB",
                    "colour": "",
                    "type": ""
                },
                "crew": {
                    "pilot": "pilot"
                },
                "nation": "Norway"
            },
            "gate_times": {
                "SP": "2020-08-01T07:06:00Z",
                "SC 1/1": "2020-08-01T07:07:47.777621Z",
                "TP1": "2020-08-01T07:12:58.229939Z",
                "SC 2/1": "2020-08-01T07:16:00.945257Z",
                "TP2": "2020-08-01T07:18:37.703942Z",
                "SC 3/1": "2020-08-01T07:20:24.127429Z",
                "SC 3/2": "2020-08-01T07:22:58.527963Z",
                "TP3": "2020-08-01T07:27:35.440298Z",
                "TP4": "2020-08-01T07:31:55.786556Z",
                "SC 5/1": "2020-08-01T07:35:35.660024Z",
                "TP5": "2020-08-01T07:39:25.622820Z",
                "SC 6/1": "2020-08-01T07:42:27.912264Z",
                "TP6": "2020-08-01T07:48:40.701664Z",
                "SC 7/1": "2020-08-01T07:51:27.611618Z",
                "SC 7/2": "2020-08-01T07:55:36.733318Z",
                "FP": "2020-08-01T07:59:38.293518Z"
            },
            "scorecard": "FAI Precision 2020",
            "takeoff_time": "2020-08-01T07:00:00Z",
            "minutes_to_starting_point": 6,
            "finished_by_time": "2020-08-01T09:00:00Z",
            "air_speed": 75,
            "contestant_number": 13,
            "traccar_device_name": "Niklas",
            "tracker_start_time": "0001-01-01T00:00:00Z",
            "wind_speed": 0,
            "wind_direction": 0
        },
        {
            "id": 37,
            "team": {
                "id": 37,
                "aeroplane": {
                    "id": 1,
                    "registration": "LN-YDB",
                    "colour": "",
                    "type": ""
                },
                "crew": {
                    "pilot": "pilot"
                },
                "nation": "Norway"
            },
            "gate_times": {
                "SP": "2020-08-01T07:26:00Z",
                "SC 1/1": "2020-08-01T07:27:55.476023Z",
                "TP1": "2020-08-01T07:33:28.103507Z",
                "SC 2/1": "2020-08-01T07:36:39.584205Z",
                "TP2": "2020-08-01T07:39:27.539939Z",
                "SC 3/1": "2020-08-01T07:41:21.565103Z",
                "SC 3/2": "2020-08-01T07:44:06.994246Z",
                "TP3": "2020-08-01T07:49:03.686033Z",
                "TP4": "2020-08-01T07:53:42.628452Z",
                "SC 5/1": "2020-08-01T07:57:33.921454Z",
                "TP5": "2020-08-01T08:01:40.310164Z",
                "SC 6/1": "2020-08-01T08:04:55.620283Z",
                "TP6": "2020-08-01T08:11:35.037497Z",
                "SC 7/1": "2020-08-01T08:14:29.583876Z",
                "SC 7/2": "2020-08-01T08:18:56.499983Z",
                "FP": "2020-08-01T08:23:15.314483Z"
            },
            "scorecard": "FAI Precision 2020",
            "takeoff_time": "2020-08-01T07:20:00Z",
            "minutes_to_starting_point": 6,
            "finished_by_time": "2020-08-01T09:20:00Z",
            "air_speed": 70,
            "contestant_number": 14,
            "traccar_device_name": "Odin",
            "tracker_start_time": "0001-01-01T00:00:00Z",
            "wind_speed": 0,
            "wind_direction": 0
        },
        {
            "id": 38,
            "team": {
                "id": 38,
                "aeroplane": {
                    "id": 1,
                    "registration": "LN-YDB",
                    "colour": "",
                    "type": ""
                },
                "crew": {
                    "pilot": "pilot"
                },
                "nation": "Norway"
            },
            "gate_times": {
                "SP": "2020-08-01T11:06:00Z",
                "SC 1/1": "2020-08-01T11:07:55.476023Z",
                "TP1": "2020-08-01T11:13:28.103507Z",
                "SC 2/1": "2020-08-01T11:16:39.584205Z",
                "TP2": "2020-08-01T11:19:27.539939Z",
                "SC 3/1": "2020-08-01T11:21:21.565103Z",
                "SC 3/2": "2020-08-01T11:24:06.994246Z",
                "TP3": "2020-08-01T11:29:03.686033Z",
                "TP4": "2020-08-01T11:33:42.628452Z",
                "SC 5/1": "2020-08-01T11:37:33.921454Z",
                "TP5": "2020-08-01T11:41:40.310164Z",
                "SC 6/1": "2020-08-01T11:44:55.620283Z",
                "TP6": "2020-08-01T11:51:35.037497Z",
                "SC 7/1": "2020-08-01T11:54:29.583876Z",
                "SC 7/2": "2020-08-01T11:58:56.499983Z",
                "FP": "2020-08-01T12:03:15.314483Z"
            },
            "scorecard": "FAI Precision 2020",
            "takeoff_time": "2020-08-01T11:00:00Z",
            "minutes_to_starting_point": 6,
            "finished_by_time": "2020-08-01T13:00:00Z",
            "air_speed": 70,
            "contestant_number": 15,
            "traccar_device_name": "Ola",
            "tracker_start_time": "0001-01-01T00:00:00Z",
            "wind_speed": 0,
            "wind_direction": 0
        },
        {
            "id": 39,
            "team": {
                "id": 39,
                "aeroplane": {
                    "id": 1,
                    "registration": "LN-YDB",
                    "colour": "",
                    "type": ""
                },
                "crew": {
                    "pilot": "pilot"
                },
                "nation": "Norway"
            },
            "gate_times": {
                "SP": "2020-08-01T08:31:00Z",
                "SC 1/1": "2020-08-01T08:32:55.476023Z",
                "TP1": "2020-08-01T08:38:28.103507Z",
                "SC 2/1": "2020-08-01T08:41:39.584205Z",
                "TP2": "2020-08-01T08:44:27.539939Z",
                "SC 3/1": "2020-08-01T08:46:21.565103Z",
                "SC 3/2": "2020-08-01T08:49:06.994246Z",
                "TP3": "2020-08-01T08:54:03.686033Z",
                "TP4": "2020-08-01T08:58:42.628452Z",
                "SC 5/1": "2020-08-01T09:02:33.921454Z",
                "TP5": "2020-08-01T09:06:40.310164Z",
                "SC 6/1": "2020-08-01T09:09:55.620283Z",
                "TP6": "2020-08-01T09:16:35.037497Z",
                "SC 7/1": "2020-08-01T09:19:29.583876Z",
                "SC 7/2": "2020-08-01T09:23:56.499983Z",
                "FP": "2020-08-01T09:28:15.314483Z"
            },
            "scorecard": "FAI Precision 2020",
            "takeoff_time": "2020-08-01T08:25:00Z",
            "minutes_to_starting_point": 6,
            "finished_by_time": "2020-08-01T10:25:00Z",
            "air_speed": 70,
            "contestant_number": 16,
            "traccar_device_name": "Ole",
            "tracker_start_time": "0001-01-01T00:00:00Z",
            "wind_speed": 0,
            "wind_direction": 0
        },
        {
            "id": 40,
            "team": {
                "id": 40,
                "aeroplane": {
                    "id": 1,
                    "registration": "LN-YDB",
                    "colour": "",
                    "type": ""
                },
                "crew": {
                    "pilot": "pilot"
                },
                "nation": "Norway"
            },
            "gate_times": {
                "SP": "2020-08-01T08:01:00Z",
                "SC 1/1": "2020-08-01T08:02:41.041520Z",
                "TP1": "2020-08-01T08:07:32.090568Z",
                "SC 2/1": "2020-08-01T08:10:27.136178Z",
                "TP2": "2020-08-01T08:12:54.097445Z",
                "SC 3/1": "2020-08-01T08:14:33.869464Z",
                "SC 3/2": "2020-08-01T08:16:58.619964Z",
                "TP3": "2020-08-01T08:21:18.225278Z",
                "TP4": "2020-08-01T08:25:22.299894Z",
                "SC 5/1": "2020-08-01T08:28:52.181270Z",
                "TP5": "2020-08-01T08:32:27.771392Z",
                "SC 6/1": "2020-08-01T08:35:18.667746Z",
                "TP6": "2020-08-01T08:41:08.157808Z",
                "SC 7/1": "2020-08-01T08:43:48.385890Z",
                "SC 7/2": "2020-08-01T08:47:41.937483Z",
                "FP": "2020-08-01T08:51:28.400171Z"
            },
            "scorecard": "FAI Precision 2020",
            "takeoff_time": "2020-08-01T07:55:00Z",
            "minutes_to_starting_point": 6,
            "finished_by_time": "2020-08-01T09:55:00Z",
            "air_speed": 80,
            "contestant_number": 17,
            "traccar_device_name": "Steinar",
            "tracker_start_time": "0001-01-01T00:00:00Z",
            "wind_speed": 0,
            "wind_direction": 0
        },
        {
            "id": 41,
            "team": {
                "id": 41,
                "aeroplane": {
                    "id": 1,
                    "registration": "LN-YDB",
                    "colour": "",
                    "type": ""
                },
                "crew": {
                    "pilot": "pilot"
                },
                "nation": "Norway"
            },
            "gate_times": {
                "SP": "2020-08-01T11:16:00Z",
                "SC 1/1": "2020-08-01T11:17:55.476023Z",
                "TP1": "2020-08-01T11:23:28.103507Z",
                "SC 2/1": "2020-08-01T11:26:39.584205Z",
                "TP2": "2020-08-01T11:29:27.539939Z",
                "SC 3/1": "2020-08-01T11:31:21.565103Z",
                "SC 3/2": "2020-08-01T11:34:06.994246Z",
                "TP3": "2020-08-01T11:39:03.686033Z",
                "TP4": "2020-08-01T11:43:42.628452Z",
                "SC 5/1": "2020-08-01T11:47:33.921454Z",
                "TP5": "2020-08-01T11:51:40.310164Z",
                "SC 6/1": "2020-08-01T11:54:55.620283Z",
                "TP6": "2020-08-01T12:01:35.037497Z",
                "SC 7/1": "2020-08-01T12:04:29.583876Z",
                "SC 7/2": "2020-08-01T12:08:56.499983Z",
                "FP": "2020-08-01T12:13:15.314483Z"
            },
            "scorecard": "FAI Precision 2020",
            "takeoff_time": "2020-08-01T11:10:00Z",
            "minutes_to_starting_point": 6,
            "finished_by_time": "2020-08-01T13:10:00Z",
            "air_speed": 70,
            "contestant_number": 18,
            "traccar_device_name": "Stian",
            "tracker_start_time": "0001-01-01T00:00:00Z",
            "wind_speed": 0,
            "wind_direction": 0
        },
        {
            "id": 42,
            "team": {
                "id": 42,
                "aeroplane": {
                    "id": 1,
                    "registration": "LN-YDB",
                    "colour": "",
                    "type": ""
                },
                "crew": {
                    "pilot": "pilot"
                },
                "nation": "Norway"
            },
            "gate_times": {
                "SP": "2020-08-01T09:06:00Z",
                "SC 1/1": "2020-08-01T09:07:55.476023Z",
                "TP1": "2020-08-01T09:13:28.103507Z",
                "SC 2/1": "2020-08-01T09:16:39.584205Z",
                "TP2": "2020-08-01T09:19:27.539939Z",
                "SC 3/1": "2020-08-01T09:21:21.565103Z",
                "SC 3/2": "2020-08-01T09:24:06.994246Z",
                "TP3": "2020-08-01T09:29:03.686033Z",
                "TP4": "2020-08-01T09:33:42.628452Z",
                "SC 5/1": "2020-08-01T09:37:33.921454Z",
                "TP5": "2020-08-01T09:41:40.310164Z",
                "SC 6/1": "2020-08-01T09:44:55.620283Z",
                "TP6": "2020-08-01T09:51:35.037497Z",
                "SC 7/1": "2020-08-01T09:54:29.583876Z",
                "SC 7/2": "2020-08-01T09:58:56.499983Z",
                "FP": "2020-08-01T10:03:15.314483Z"
            },
            "scorecard": "FAI Precision 2020",
            "takeoff_time": "2020-08-01T09:00:00Z",
            "minutes_to_starting_point": 6,
            "finished_by_time": "2020-08-01T11:00:00Z",
            "air_speed": 70,
            "contestant_number": 19,
            "traccar_device_name": "Tim",
            "tracker_start_time": "0001-01-01T00:00:00Z",
            "wind_speed": 0,
            "wind_direction": 0
        },
        {
            "id": 43,
            "team": {
                "id": 43,
                "aeroplane": {
                    "id": 1,
                    "registration": "LN-YDB",
                    "colour": "",
                    "type": ""
                },
                "crew": {
                    "pilot": "pilot"
                },
                "nation": "Norway"
            },
            "gate_times": {
                "SP": "2020-08-01T11:21:00Z",
                "SC 1/1": "2020-08-01T11:22:55.476023Z",
                "TP1": "2020-08-01T11:28:28.103507Z",
                "SC 2/1": "2020-08-01T11:31:39.584205Z",
                "TP2": "2020-08-01T11:34:27.539939Z",
                "SC 3/1": "2020-08-01T11:36:21.565103Z",
                "SC 3/2": "2020-08-01T11:39:06.994246Z",
                "TP3": "2020-08-01T11:44:03.686033Z",
                "TP4": "2020-08-01T11:48:42.628452Z",
                "SC 5/1": "2020-08-01T11:52:33.921454Z",
                "TP5": "2020-08-01T11:56:40.310164Z",
                "SC 6/1": "2020-08-01T11:59:55.620283Z",
                "TP6": "2020-08-01T12:06:35.037497Z",
                "SC 7/1": "2020-08-01T12:09:29.583876Z",
                "SC 7/2": "2020-08-01T12:13:56.499983Z",
                "FP": "2020-08-01T12:18:15.314483Z"
            },
            "scorecard": "FAI Precision 2020",
            "takeoff_time": "2020-08-01T11:15:00Z",
            "minutes_to_starting_point": 6,
            "finished_by_time": "2020-08-01T13:15:00Z",
            "air_speed": 70,
            "contestant_number": 20,
            "traccar_device_name": "Tommy",
            "tracker_start_time": "0001-01-01T00:00:00Z",
            "wind_speed": 0,
            "wind_direction": 0
        },
        {
            "id": 44,
            "team": {
                "id": 44,
                "aeroplane": {
                    "id": 1,
                    "registration": "LN-YDB",
                    "colour": "",
                    "type": ""
                },
                "crew": {
                    "pilot": "pilot"
                },
                "nation": "Norway"
            },
            "gate_times": {
                "SP": "2020-08-01T10:46:00Z",
                "SC 1/1": "2020-08-01T10:47:55.476023Z",
                "TP1": "2020-08-01T10:53:28.103507Z",
                "SC 2/1": "2020-08-01T10:56:39.584205Z",
                "TP2": "2020-08-01T10:59:27.539939Z",
                "SC 3/1": "2020-08-01T11:01:21.565103Z",
                "SC 3/2": "2020-08-01T11:04:06.994246Z",
                "TP3": "2020-08-01T11:09:03.686033Z",
                "TP4": "2020-08-01T11:13:42.628452Z",
                "SC 5/1": "2020-08-01T11:17:33.921454Z",
                "TP5": "2020-08-01T11:21:40.310164Z",
                "SC 6/1": "2020-08-01T11:24:55.620283Z",
                "TP6": "2020-08-01T11:31:35.037497Z",
                "SC 7/1": "2020-08-01T11:34:29.583876Z",
                "SC 7/2": "2020-08-01T11:38:56.499983Z",
                "FP": "2020-08-01T11:43:15.314483Z"
            },
            "scorecard": "FAI Precision 2020",
            "takeoff_time": "2020-08-01T10:40:00Z",
            "minutes_to_starting_point": 6,
            "finished_by_time": "2020-08-01T12:40:00Z",
            "air_speed": 70,
            "contestant_number": 21,
            "traccar_device_name": "TorHelge",
            "tracker_start_time": "0001-01-01T00:00:00Z",
            "wind_speed": 0,
            "wind_direction": 0
        }
    ],
    "name": "NM contest",
    "calculator_type": 0,
    "start_time": "2020-08-01T06:00:00Z",
    "finish_time": "2020-08-01T16:00:00Z",
    "is_public": False,
}

expected_track = {
    "id": 10,
    "waypoints": [
        {
            "name": "SP",
            "latitude": 48.126794444445,
            "longitude": 17.0301777778,
            "elevation": 1000,
            "width": 1,
            "gate_line": [
                [
                    48.120434854845,
                    17.0221104171
                ],
                [
                    48.133154034045,
                    17.0382461375
                ]
            ],
            "gate_line_infinite": [
                [
                    47.865752399404855,
                    16.701281287358672
                ],
                [
                    48.386889111500174,
                    17.36242749989912
                ]
            ],
            "time_check": True,
            "gate_check": True,
            "end_curved": False,
            "type": "sp",
            "distance_next": 7314.404139654599,
            "bearing_next": 310.28526298769185,
            "is_procedure_turn": False
        },
        {
            "name": "SC1",
            "latitude": 48.1693027833,
            "longitude": 16.9549388833,
            "elevation": 1000,
            "width": 1,
            "gate_line": [
                [
                    48.1629431937,
                    16.9468648386
                ],
                [
                    48.1756623729,
                    16.9630139293
                ]
            ],
            "gate_line_infinite": [
                [
                    47.908260038041966,
                    16.625772352157625
                ],
                [
                    48.42939673518432,
                    17.28746643836033
                ]
            ],
            "time_check": True,
            "gate_check": True,
            "end_curved": False,
            "type": "secret",
            "distance_next": 5238.238726076472,
            "bearing_next": 310.25828540235466,
            "is_procedure_turn": False
        },
        {
            "name": "TP1",
            "latitude": 48.1997333333,
            "longitude": 16.90100275,
            "elevation": 1000,
            "width": 1,
            "gate_line": [
                [
                    48.1933719529,
                    16.8929270849
                ],
                [
                    48.2060947137,
                    16.909079418
                ]
            ],
            "gate_line_infinite": [
                [
                    47.93861708169982,
                    16.57177237735281
                ],
                [
                    48.45990052294847,
                    17.23359936427385
                ]
            ],
            "time_check": True,
            "gate_check": True,
            "end_curved": False,
            "type": "tp",
            "distance_next": 6264.027702034917,
            "bearing_next": 336.1952836367903,
            "is_procedure_turn": False
        },
        {
            "name": "SC2",
            "latitude": 48.25126945,
            "longitude": 16.86685555,
            "elevation": 1000,
            "width": 1,
            "gate_line": [
                [
                    48.2479042508,
                    16.8554067022
                ],
                [
                    48.2546346492,
                    16.8783051513
                ]
            ],
            "gate_line_infinite": [
                [
                    48.11243696763009,
                    16.39901257030988
                ],
                [
                    48.38819501063992,
                    17.337227472785255
                ]
            ],
            "time_check": True,
            "gate_check": True,
            "end_curved": False,
            "type": "secret",
            "distance_next": 10864.869542744425,
            "bearing_next": 336.1767930276281,
            "is_procedure_turn": False
        },
        {
            "name": "SC3",
            "latitude": 48.3406389,
            "longitude": 16.80748055,
            "elevation": 1000,
            "width": 1,
            "gate_line": [
                [
                    48.3372699863,
                    16.7960141142
                ],
                [
                    48.3440078137,
                    16.8189477437
                ]
            ],
            "gate_line_infinite": [
                [
                    48.20165165482421,
                    16.338924181553622
                ],
                [
                    48.47771404889829,
                    17.278580517561704
                ]
            ],
            "time_check": True,
            "gate_check": True,
            "end_curved": False,
            "type": "secret",
            "distance_next": 3075.156075147747,
            "bearing_next": 336.1304888003484,
            "is_procedure_turn": False
        },
        {
            "name": "TP2",
            "latitude": 48.3659277833,
            "longitude": 16.7906361333,
            "elevation": 1000,
            "width": 1,
            "gate_line": [
                [
                    48.3625548211,
                    16.7791667012
                ],
                [
                    48.3693007455,
                    16.8021063251
                ]
            ],
            "gate_line_infinite": [
                [
                    48.22677426518687,
                    16.32195994517801
                ],
                [
                    48.50316840394789,
                    17.261861908039553
                ]
            ],
            "time_check": False,
            "gate_check": True,
            "end_curved": False,
            "type": "tp",
            "distance_next": 1337.4699747585582,
            "bearing_next": 13.582514764871064,
            "is_procedure_turn": False
        },
        {
            "name": "SC4",
            "latitude": 48.37761945,
            "longitude": 16.7948888833,
            "elevation": 1000,
            "width": 1,
            "gate_line": [
                [
                    48.3795767204,
                    16.7826935335
                ],
                [
                    48.3756621796,
                    16.8070837642
                ]
            ],
            "gate_line_infinite": [
                [
                    48.456731345033006,
                    16.29443721664982
                ],
                [
                    48.296345204652766,
                    17.29376688857891
                ]
            ],
            "time_check": True,
            "gate_check": True,
            "end_curved": False,
            "type": "secret",
            "distance_next": 9667.807249212345,
            "bearing_next": 13.576194871338544,
            "is_procedure_turn": False
        },
        {
            "name": "SC5",
            "latitude": 48.462130555555,
            "longitude": 16.8256666667,
            "elevation": 1000,
            "width": 1,
            "gate_line": [
                [
                    48.464088334955,
                    16.8134512101
                ],
                [
                    48.460172776155,
                    16.8378816521
                ]
            ],
            "gate_line_infinite": [
                [
                    48.541260110975095,
                    16.324387407242895
                ],
                [
                    48.38083228158871,
                    17.325364569338944
                ]
            ],
            "time_check": True,
            "gate_check": True,
            "end_curved": False,
            "type": "secret",
            "distance_next": 8475.262860641078,
            "bearing_next": 13.605389909469125,
            "is_procedure_turn": False
        },
        {
            "name": "SC6",
            "latitude": 48.5362083333,
            "longitude": 16.8527444167,
            "elevation": 1000,
            "width": 1,
            "gate_line": [
                [
                    48.5381700461,
                    16.8405125327
                ],
                [
                    48.5342466205,
                    16.8649758268
                ]
            ],
            "gate_line_infinite": [
                [
                    48.615496465891646,
                    16.350787439802033
                ],
                [
                    48.45474633579481,
                    17.353110590317744
                ]
            ],
            "time_check": True,
            "gate_check": True,
            "end_curved": False,
            "type": "secret",
            "distance_next": 4434.249159396018,
            "bearing_next": 13.621615290808677,
            "is_procedure_turn": False
        },
        {
            "name": "TP3",
            "latitude": 48.5749638833,
            "longitude": 16.8669389167,
            "elevation": 1100,
            "width": 1,
            "gate_line": [
                [
                    48.5769272084,
                    16.8546982489
                ],
                [
                    48.5730005582,
                    16.8791791091
                ]
            ],
            "gate_line_infinite": [
                [
                    48.65431669251248,
                    16.36461977683933
                ],
                [
                    48.49343445353952,
                    17.367662629049097
                ]
            ],
            "time_check": True,
            "gate_check": True,
            "end_curved": False,
            "type": "tp",
            "distance_next": 10029.161255342526,
            "bearing_next": 264.95337238145424,
            "is_procedure_turn": True
        },
        {
            "name": "SC7",
            "latitude": 48.56695,
            "longitude": 16.73116945,
            "elevation": 1000,
            "width": 1,
            "gate_line": [
                [
                    48.5586496258,
                    16.732288261
                ],
                [
                    48.5752503742,
                    16.7300504553
                ]
            ],
            "gate_line_infinite": [
                [
                    48.22684983240657,
                    16.776708618502422
                ],
                [
                    48.9070319779852,
                    16.68501381805366
                ]
            ],
            "time_check": True,
            "gate_check": True,
            "end_curved": False,
            "type": "secret",
            "distance_next": 6995.628683718954,
            "bearing_next": 264.81699606197657,
            "is_procedure_turn": False
        },
        {
            "name": "SC8",
            "latitude": 48.5612278,
            "longitude": 16.63649725,
            "elevation": 1000,
            "width": 1,
            "gate_line": [
                [
                    48.5529290075,
                    16.6376424083
                ],
                [
                    48.5695265925,
                    16.6353519038
                ]
            ],
            "gate_line_infinite": [
                [
                    48.22119200975526,
                    16.683108956370514
                ],
                [
                    48.90124453336847,
                    16.58925481020325
                ]
            ],
            "time_check": True,
            "gate_check": True,
            "end_curved": False,
            "type": "secret",
            "distance_next": 13905.07163093863,
            "bearing_next": 264.7645680223683,
            "is_procedure_turn": False
        },
        {
            "name": "TP4",
            "latitude": 48.5496638333,
            "longitude": 16.4483777667,
            "elevation": 1300,
            "width": 1,
            "gate_line": [
                [
                    48.5413662074,
                    16.4495417949
                ],
                [
                    48.5579614592,
                    16.4472135476
                ]
            ],
            "gate_line_infinite": [
                [
                    48.20967552479861,
                    16.495757711186606
                ],
                [
                    48.889632450723695,
                    16.400357046463764
                ]
            ],
            "time_check": True,
            "gate_check": True,
            "end_curved": False,
            "type": "tp",
            "distance_next": 7271.7668939774885,
            "bearing_next": 175.77951463340003,
            "is_procedure_turn": False
        },
        {
            "name": "SC9",
            "latitude": 48.4844444667,
            "longitude": 16.4556388833,
            "elevation": 1000,
            "width": 1,
            "gate_line": [
                [
                    48.4850573619,
                    16.4681773891
                ],
                [
                    48.4838315715,
                    16.443100529
                ]
            ],
            "gate_line_infinite": [
                [
                    48.50841351393297,
                    16.96962257581543
                ],
                [
                    48.45819064236398,
                    15.942163739034772
                ]
            ],
            "time_check": True,
            "gate_check": True,
            "end_curved": False,
            "type": "secret",
            "distance_next": 4374.4490068336,
            "bearing_next": 175.99820478386073,
            "is_procedure_turn": False
        },
        {
            "name": "SC10",
            "latitude": 48.4452,
            "longitude": 16.4597777667,
            "elevation": 1000,
            "width": 1,
            "gate_line": [
                [
                    48.4457813396,
                    16.4723099945
                ],
                [
                    48.4446186604,
                    16.4472456823
                ]
            ],
            "gate_line_infinite": [
                [
                    48.46787711077414,
                    16.97349085764924
                ],
                [
                    48.42024001802492,
                    15.946546134597362
                ]
            ],
            "time_check": True,
            "gate_check": True,
            "end_curved": False,
            "type": "secret",
            "distance_next": 9069.622737599375,
            "bearing_next": 175.67752533264934,
            "is_procedure_turn": False
        },
        {
            "name": "TP5",
            "latitude": 48.3638666667,
            "longitude": 16.4690305667,
            "elevation": 1100,
            "width": 1,
            "gate_line": [
                [
                    48.3644942471,
                    16.4815377138
                ],
                [
                    48.3632390863,
                    16.4565235737
                ]
            ],
            "gate_line_infinite": [
                [
                    48.38844253106983,
                    16.981733783861557
                ],
                [
                    48.337016290162985,
                    15.956844583300533
                ]
            ],
            "time_check": True,
            "gate_check": True,
            "end_curved": False,
            "type": "tp",
            "distance_next": 3887.7757299213763,
            "bearing_next": 67.12069565775101,
            "is_procedure_turn": True
        },
        {
            "name": "SC11",
            "latitude": 48.37745,
            "longitude": 16.5175277667,
            "elevation": 1000,
            "width": 1,
            "gate_line": [
                [
                    48.3851287403,
                    16.5126532678
                ],
                [
                    48.3697712597,
                    16.5224015305
                ]
            ],
            "gate_line_infinite": [
                [
                    48.69189688123228,
                    16.316576974467306
                ],
                [
                    48.06265767485532,
                    16.716010801990937
                ]
            ],
            "time_check": True,
            "gate_check": True,
            "end_curved": False,
            "type": "secret",
            "distance_next": 10085.335285784395,
            "bearing_next": 67.15690070431299,
            "is_procedure_turn": False
        },
        {
            "name": "TP6",
            "latitude": 48.4125916667,
            "longitude": 16.6434555667,
            "elevation": 1100,
            "width": 1,
            "gate_line": [
                [
                    48.4202740835,
                    16.6385908584
                ],
                [
                    48.4049092499,
                    16.6483195401
                ]
            ],
            "gate_line_infinite": [
                [
                    48.72718990858058,
                    16.442906274616874
                ],
                [
                    48.097649417466926,
                    16.84153783336341
                ]
            ],
            "time_check": True,
            "gate_check": True,
            "end_curved": False,
            "type": "tp",
            "distance_next": 9738.016260143093,
            "bearing_next": 166.24719776134498,
            "is_procedure_turn": True
        },
        {
            "name": "SC12",
            "latitude": 48.3275222167,
            "longitude": 16.6747694667,
            "elevation": 1000,
            "width": 1,
            "gate_line": [
                [
                    48.3295016748,
                    16.6869447223
                ],
                [
                    48.3255427586,
                    16.6625946837
                ]
            ],
            "gate_line_infinite": [
                [
                    48.40754653128093,
                    17.174404022982447
                ],
                [
                    48.24534222909321,
                    16.176720993570292
                ]
            ],
            "time_check": True,
            "gate_check": True,
            "end_curved": False,
            "type": "secret",
            "distance_next": 7508.87999856106,
            "bearing_next": 166.27360404895148,
            "is_procedure_turn": False
        },
        {
            "name": "SC13",
            "latitude": 48.26191945,
            "longitude": 16.6988388667,
            "elevation": 1000,
            "width": 1,
            "gate_line": [
                [
                    48.2638955613,
                    16.7109997161
                ],
                [
                    48.2599433387,
                    16.6866784874
                ]
            ],
            "gate_line_infinite": [
                [
                    48.34180891170048,
                    17.19787913667887
                ],
                [
                    48.17987884424033,
                    16.201376483423
                ]
            ],
            "time_check": True,
            "gate_check": True,
            "end_curved": False,
            "type": "secret",
            "distance_next": 1835.569168690759,
            "bearing_next": 166.2703826435377,
            "is_procedure_turn": False
        },
        {
            "name": "TP7",
            "latitude": 48.2458833333,
            "longitude": 16.7047222167,
            "elevation": 1000,
            "width": 1,
            "gate_line": [
                [
                    48.2478608593,
                    16.716878734
                ],
                [
                    48.2439058073,
                    16.6925661694
                ]
            ],
            "gate_line_infinite": [
                [
                    48.32583145770522,
                    17.203584840753884
                ],
                [
                    48.16378545988559,
                    16.207437157498358
                ]
            ],
            "time_check": False,
            "gate_check": True,
            "end_curved": False,
            "type": "tp",
            "distance_next": 5805.843891053953,
            "bearing_next": 136.69887262627014,
            "is_procedure_turn": False
        },
        {
            "name": "SC14",
            "latitude": 48.2078722167,
            "longitude": 16.7584555,
            "elevation": 1000,
            "width": 1,
            "gate_line": [
                [
                    48.2135853675,
                    16.7675592276
                ],
                [
                    48.2021590659,
                    16.7493527879
                ]
            ],
            "gate_line_infinite": [
                [
                    48.441350725668094,
                    17.13315287773819
                ],
                [
                    47.97318796066255,
                    16.38716673322129
                ]
            ],
            "time_check": True,
            "gate_check": True,
            "end_curved": False,
            "type": "secret",
            "distance_next": 8351.980670787441,
            "bearing_next": 136.69604176237306,
            "is_procedure_turn": False
        },
        {
            "name": "FP",
            "latitude": 48.1531861167,
            "longitude": 16.835675,
            "elevation": 1000,
            "width": 1,
            "gate_line": [
                [
                    48.1588986418,
                    16.8447699033
                ],
                [
                    48.1474735916,
                    16.8265811091
                ]
            ],
            "gate_line_infinite": [
                [
                    48.386640039803254,
                    17.210005751143996
                ],
                [
                    47.91852852654491,
                    16.464742649545027
                ]
            ],
            "time_check": True,
            "gate_check": True,
            "end_curved": False,
            "type": "fp",
            "distance_next": -1,
            "bearing_next": -1,
            "is_procedure_turn": True
        }
    ],
    "starting_line": {
        "name": "SP",
        "latitude": 48.126794444445,
        "longitude": 17.0301777778,
        "elevation": 1000,
        "width": 1,
        "gate_line": [
            [
                48.120434854845,
                17.0221104171
            ],
            [
                48.133154034045,
                17.0382461375
            ]
        ],
        "gate_line_infinite": [
            [
                47.865752399404855,
                16.701281287358672
            ],
            [
                48.386889111500174,
                17.36242749989912
            ]
        ],
        "time_check": True,
        "gate_check": True,
        "end_curved": False,
        "type": "sp",
        "distance_next": 7314.404139654599,
        "bearing_next": 310.28526298769185,
        "is_procedure_turn": False
    },
    "landing_gate": {
        "name": "LDG",
        "latitude": 48.0995277778,
        "longitude": 16.9350833333,
        "elevation": 594,
        "width": 0.25,
        "gate_line": [
            [
                48.1005694445,
                16.9377849406
            ],
            [
                48.0984861111,
                16.9323817808
            ]
        ],
        "gate_line_infinite": [
            [
                48.26630066460093,
                17.371164006886076
            ],
            [
                47.93111584654592,
                16.501836554800818
            ]
        ],
        "time_check": True,
        "gate_check": True,
        "end_curved": False,
        "type": "ldg",
        "distance_next": -1,
        "bearing_next": -1,
        "is_procedure_turn": False
    },
    "takeoff_gate": {
        "name": "T/O",
        "latitude": 48.0995277778,
        "longitude": 16.9350833333,
        "elevation": 594,
        "width": 0.25,
        "gate_line": [
            [
                48.1005694445,
                16.9377849406
            ],
            [
                48.0984861111,
                16.9323817808
            ]
        ],
        "gate_line_infinite": [
            [
                48.26630066460093,
                17.371164006886076
            ],
            [
                47.93111584654592,
                16.501836554800818
            ]
        ],
        "time_check": True,
        "gate_check": True,
        "end_curved": False,
        "type": "to",
        "distance_next": -1,
        "bearing_next": -1,
        "is_procedure_turn": False
    },
    "name": "2017 WPFC Route 1 Blue"
}

with open("display/tests/demo contests/2017_WPFC/Route-1-Blue.gpx", "r") as f:
    track_string = base64.b64encode(f.read().encode('utf-8')).decode('utf-8')

data["track_file"] = track_string



class TestImportSerialiser(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create(username="test")
        permission = Permission.objects.get(codename="add_navigationtask")
        self.user.user_permissions.add(permission)
        self.contest = Contest.objects.create(name="test")
        get_default_scorecard()

    def test_import_serialiser(self):
        request = Mock()
        request.user = self.user
        serialiser = ExternalNavigationTaskNestedSerialiser(data=data,
                                                            context={"request": request, "contest": self.contest})
        valid = serialiser.is_valid()
        print(serialiser.errors)

        self.assertTrue(valid)
        serialiser.save()


class TestImportFCNavigationTask(APITestCase):
    def setUp(self):
        self.user = User.objects.create(username="test")
        permission = Permission.objects.get(codename="add_navigationtask")
        self.user.user_permissions.add(permission)
        self.client.force_login(user=self.user)
        self.contest = Contest.objects.create(name="test")
        get_default_scorecard()

    def test_import(self):
        res = self.client.post(
            "/api/v1/contests/{}/importnavigationtask/".format(self.contest.pk), data, format="json")
        self.assertEqual(200, res.status_code, "Failed to POST importnavigationtask")
        navigation_task_id = res.json()["id"]
        print(res.json())
        task = self.client.get("/api/v1/contests/{}/navigationtasks/{}/".format(self.contest.pk, navigation_task_id))
        self.assertEqual(200, task.status_code, "Failed to GET navigationtask")
        track_id = task.json()["track"]
        task = self.client.get("/api/v1/tracks/{}/".format(track_id))
        self.assertEqual(200, task.status_code, "Failed to GET navigationtask")
        track = task.json()
        self.assertEqual(len(expected_track["waypoints"]), len(track["waypoints"]))
        for index, waypoint in enumerate(track["waypoints"]):
            self.assertDictEqual(expected_track["waypoints"][index], waypoint)
            self.assertListEqual(expected_track["waypoints"][index]["gate_line"], waypoint["gate_line"])
            self.assertListEqual(expected_track["waypoints"][index]["gate_line_infinite"], waypoint["gate_line_infinite"])
