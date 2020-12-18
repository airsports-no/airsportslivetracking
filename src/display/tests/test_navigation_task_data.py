import base64
import json
from pprint import pprint
from unittest.mock import Mock

from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TransactionTestCase
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APITestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Contest, NavigationTask, Team, Crew
from display.serialisers import ExternalNavigationTaskNestedSerialiser

data = {
    "calculator_type": 0,
    "contestant_set": [
        {
            "air_speed": 75,
            "contestant_number": 0,
            "finished_by_time": "2020-08-01T10:00:00Z",
            "gate_times": {
                "FP": "2020-08-01T08:59:38.293518Z",
                "SC 1/1": "2020-08-01T08:07:47.777621Z",
                "SC 2/1": "2020-08-01T08:16:00.945257Z",
                "SC 3/1": "2020-08-01T08:20:24.127429Z",
                "SC 3/2": "2020-08-01T08:22:58.527963Z",
                "SC 5/1": "2020-08-01T08:35:35.660024Z",
                "SC 6/1": "2020-08-01T08:42:27.912264Z",
                "SC 7/1": "2020-08-01T08:51:27.611618Z",
                "SC 7/2": "2020-08-01T08:55:36.733318Z",
                "SP": "2020-08-01T08:06:00Z",
                "TP1": "2020-08-01T08:12:58.229939Z",
                "TP2": "2020-08-01T08:18:37.703942Z",
                "TP3": "2020-08-01T08:27:35.440298Z",
                "TP4": "2020-08-01T08:31:55.786556Z",
                "TP5": "2020-08-01T08:39:25.622820Z",
                "TP6": "2020-08-01T08:48:40.701664Z"
            },
            "minutes_to_starting_point": 6,
            "scorecard": "FAI Precision 2020",
            "takeoff_time": "2020-08-01T08:00:00Z",
            "team": {
                "aeroplane": {
                    "registration": "LN-YDB",
                },
                "crew": {
                    "member1": {
                        "first_name": "first_name",
                        "last_name": "last_name"
                    }
                },
                "country": "NO"
            },
            "traccar_device_name": "Anders",
            "tracker_start_time": "0001-01-01T00:00:00Z",
            "wind_direction": 0,
            "wind_speed": 0
        },
        {
            "air_speed": 70,
            "contestant_number": 1,
            "finished_by_time": "2020-08-01T10:10:00Z",
            "gate_times": {
                "FP": "2020-08-01T09:13:15.314483Z",
                "SC 1/1": "2020-08-01T08:17:55.476023Z",
                "SC 2/1": "2020-08-01T08:26:39.584205Z",
                "SC 3/1": "2020-08-01T08:31:21.565103Z",
                "SC 3/2": "2020-08-01T08:34:06.994246Z",
                "SC 5/1": "2020-08-01T08:47:33.921454Z",
                "SC 6/1": "2020-08-01T08:54:55.620283Z",
                "SC 7/1": "2020-08-01T09:04:29.583876Z",
                "SC 7/2": "2020-08-01T09:08:56.499983Z",
                "SP": "2020-08-01T08:16:00Z",
                "TP1": "2020-08-01T08:23:28.103507Z",
                "TP2": "2020-08-01T08:29:27.539939Z",
                "TP3": "2020-08-01T08:39:03.686033Z",
                "TP4": "2020-08-01T08:43:42.628452Z",
                "TP5": "2020-08-01T08:51:40.310164Z",
                "TP6": "2020-08-01T09:01:35.037497Z"
            },
            "minutes_to_starting_point": 6,
            "scorecard": "FAI Precision 2020",
            "takeoff_time": "2020-08-01T08:10:00Z",
            "team": {
                "aeroplane": {
                    "registration": "LN-YDB2",
                },
                "crew": {
                    "member1": {
                        "first_name": "first_name",
                        "last_name": "last_name"
                    }
                },
                "country": "SE"
            },
            "traccar_device_name": "tracker_1",
            "tracker_start_time": "2020-08-01T08:00:00Z",
            "wind_direction": 0,
            "wind_speed": 0
        },
    ],
    "finish_time": "2020-08-01T16:00:00Z",
    "is_public": False,
    "name": "NM contest",
    "start_time": "2020-08-01T06:00:00Z"
}

expected_route = {
    'id': 1,
    'landing_gate': {'bearing_from_previous': -1.0,
                     'bearing_next': -1.0,
                     'distance_next': -1.0,
                     'distance_previous': -1.0,
                     'elevation': 594.0,
                     'end_curved': False,
                     'gate_check': True,
                     'gate_line': [[48.1005694445, 16.9377849406],
                                   [48.0984861111, 16.9323817808]],
                     'is_procedure_turn': False,
                     'latitude': 48.0995277778,
                     'longitude': 16.9350833333,
                     'name': 'LDG',
                     'time_check': True,
                     'type': 'ldg',
                     'width': 0.25},
    'name': 'NM contest',
    'takeoff_gate': {'bearing_from_previous': -1.0,
                     'bearing_next': -1.0,
                     'distance_next': -1.0,
                     'distance_previous': -1.0,
                     'elevation': 594.0,
                     'end_curved': False,
                     'gate_check': True,
                     'gate_line': [[48.1005694445, 16.9377849406],
                                   [48.0984861111, 16.9323817808]],
                     'is_procedure_turn': False,
                     'latitude': 48.0995277778,
                     'longitude': 16.9350833333,
                     'name': 'T/O',
                     'time_check': True,
                     'type': 'to',
                     'width': 0.25},
    'waypoints': [{'bearing_from_previous': -1.0,
                   'bearing_next': 310.28526298769185,
                   'distance_next': 7314.404139654599,
                   'distance_previous': -1.0,
                   'elevation': 1000.0,
                   'end_curved': False,
                   'gate_check': True,
                   'gate_line': [[48.120434854845, 17.0221104171],
                                 [48.133154034045, 17.0382461375]],
                   'is_procedure_turn': False,
                   'latitude': 48.126794444445,
                   'longitude': 17.0301777778,
                   'name': 'SP',
                   'time_check': True,
                   'type': 'sp',
                   'width': 1.0},
                  {'bearing_from_previous': 310.28526298769185,
                   'bearing_next': 310.25828540235466,
                   'distance_next': 5238.238726076472,
                   'distance_previous': 7314.404139654193,
                   'elevation': 1000.0,
                   'end_curved': False,
                   'gate_check': True,
                   'gate_line': [[48.1629431937, 16.9468648386],
                                 [48.1756623729, 16.9630139293]],
                   'is_procedure_turn': False,
                   'latitude': 48.1693027833,
                   'longitude': 16.9549388833,
                   'name': 'SC1',
                   'time_check': True,
                   'type': 'secret',
                   'width': 1.0},
                  {'bearing_from_previous': 310.25828540235466,
                   'bearing_next': 336.1952836367903,
                   'distance_next': 6264.027702034917,
                   'distance_previous': 5238.238726076483,
                   'elevation': 1000.0,
                   'end_curved': False,
                   'gate_check': True,
                   'gate_line': [[48.1933719529, 16.8929270849],
                                 [48.2060947137, 16.909079418]],
                   'is_procedure_turn': False,
                   'latitude': 48.1997333333,
                   'longitude': 16.90100275,
                   'name': 'TP1',
                   'time_check': True,
                   'type': 'tp',
                   'width': 1.0},
                  {'bearing_from_previous': 336.1952836367903,
                   'bearing_next': 336.1767930276281,
                   'distance_next': 10864.869542744425,
                   'distance_previous': 6264.027702034517,
                   'elevation': 1000.0,
                   'end_curved': False,
                   'gate_check': True,
                   'gate_line': [[48.2479042508, 16.8554067022],
                                 [48.2546346492, 16.8783051513]],
                   'is_procedure_turn': False,
                   'latitude': 48.25126945,
                   'longitude': 16.86685555,
                   'name': 'SC2',
                   'time_check': True,
                   'type': 'secret',
                   'width': 1.0},
                  {'bearing_from_previous': 336.1767930276281,
                   'bearing_next': 336.1304888003484,
                   'distance_next': 3075.156075147747,
                   'distance_previous': 10864.869542744595,
                   'elevation': 1000.0,
                   'end_curved': False,
                   'gate_check': True,
                   'gate_line': [[48.3372699863, 16.7960141142],
                                 [48.3440078137, 16.8189477437]],
                   'is_procedure_turn': False,
                   'latitude': 48.3406389,
                   'longitude': 16.80748055,
                   'name': 'SC3',
                   'time_check': True,
                   'type': 'secret',
                   'width': 1.0},
                  {'bearing_from_previous': 336.1304888003484,
                   'bearing_next': 13.582514764871064,
                   'distance_next': 1337.4699747585582,
                   'distance_previous': 3075.1560751475763,
                   'elevation': 1000.0,
                   'end_curved': False,
                   'gate_check': True,
                   'gate_line': [[48.3625548211, 16.7791667012],
                                 [48.3693007455, 16.8021063251]],
                   'is_procedure_turn': False,
                   'latitude': 48.3659277833,
                   'longitude': 16.7906361333,
                   'name': 'TP2',
                   'time_check': True,
                   'type': 'tp',
                   'width': 1.0},
                  {'bearing_from_previous': 13.582514764871064,
                   'bearing_next': 13.576194871338544,
                   'distance_next': 9667.807249212345,
                   'distance_previous': 1337.469974758639,
                   'elevation': 1000.0,
                   'end_curved': False,
                   'gate_check': True,
                   'gate_line': [[48.3795767204, 16.7826935335],
                                 [48.3756621796, 16.8070837642]],
                   'is_procedure_turn': False,
                   'latitude': 48.37761945,
                   'longitude': 16.7948888833,
                   'name': 'SC4',
                   'time_check': True,
                   'type': 'secret',
                   'width': 1.0},
                  {'bearing_from_previous': 13.576194871338544,
                   'bearing_next': 13.605389909469125,
                   'distance_next': 8475.262860641078,
                   'distance_previous': 9667.807249212688,
                   'elevation': 1000.0,
                   'end_curved': False,
                   'gate_check': True,
                   'gate_line': [[48.464088334955, 16.8134512101],
                                 [48.460172776155, 16.8378816521]],
                   'is_procedure_turn': False,
                   'latitude': 48.462130555555,
                   'longitude': 16.8256666667,
                   'name': 'SC5',
                   'time_check': True,
                   'type': 'secret',
                   'width': 1.0},
                  {'bearing_from_previous': 13.605389909469125,
                   'bearing_next': 13.621615290808677,
                   'distance_next': 4434.249159396018,
                   'distance_previous': 8475.262860640783,
                   'elevation': 1000.0,
                   'end_curved': False,
                   'gate_check': True,
                   'gate_line': [[48.5381700461, 16.8405125327],
                                 [48.5342466205, 16.8649758268]],
                   'is_procedure_turn': False,
                   'latitude': 48.5362083333,
                   'longitude': 16.8527444167,
                   'name': 'SC6',
                   'time_check': True,
                   'type': 'secret',
                   'width': 1.0},
                  {'bearing_from_previous': 13.621615290808677,
                   'bearing_next': 264.95337238145424,
                   'distance_next': 10029.161255342526,
                   'distance_previous': 4434.249159395626,
                   'elevation': 1100.0,
                   'end_curved': False,
                   'gate_check': True,
                   'gate_line': [[48.5769272084, 16.8546982489],
                                 [48.5730005582, 16.8791791091]],
                   'is_procedure_turn': True,
                   'latitude': 48.5749638833,
                   'longitude': 16.8669389167,
                   'name': 'TP3',
                   'time_check': True,
                   'type': 'tp',
                   'width': 1.0},
                  {'bearing_from_previous': 264.95337238145424,
                   'bearing_next': 264.81699606197657,
                   'distance_next': 6995.628683718954,
                   'distance_previous': 10029.161255342491,
                   'elevation': 1000.0,
                   'end_curved': False,
                   'gate_check': True,
                   'gate_line': [[48.5586496258, 16.732288261],
                                 [48.5752503742, 16.7300504553]],
                   'is_procedure_turn': False,
                   'latitude': 48.56695,
                   'longitude': 16.73116945,
                   'name': 'SC7',
                   'time_check': True,
                   'type': 'secret',
                   'width': 1.0},
                  {'bearing_from_previous': 264.81699606197657,
                   'bearing_next': 264.7645680223683,
                   'distance_next': 13905.07163093863,
                   'distance_previous': 6995.6286837189855,
                   'elevation': 1000.0,
                   'end_curved': False,
                   'gate_check': True,
                   'gate_line': [[48.5529290075, 16.6376424083],
                                 [48.5695265925, 16.6353519038]],
                   'is_procedure_turn': False,
                   'latitude': 48.5612278,
                   'longitude': 16.63649725,
                   'name': 'SC8',
                   'time_check': True,
                   'type': 'secret',
                   'width': 1.0},
                  {'bearing_from_previous': 264.7645680223683,
                   'bearing_next': 175.77951463340003,
                   'distance_next': 7271.7668939774885,
                   'distance_previous': 13905.071630938663,
                   'elevation': 1300.0,
                   'end_curved': False,
                   'gate_check': True,
                   'gate_line': [[48.5413662074, 16.4495417949],
                                 [48.5579614592, 16.4472135476]],
                   'is_procedure_turn': False,
                   'latitude': 48.5496638333,
                   'longitude': 16.4483777667,
                   'name': 'TP4',
                   'time_check': True,
                   'type': 'tp',
                   'width': 1.0},
                  {'bearing_from_previous': 175.77951463340003,
                   'bearing_next': 175.99820478386073,
                   'distance_next': 4374.4490068336,
                   'distance_previous': 7271.76689397741,
                   'elevation': 1000.0,
                   'end_curved': False,
                   'gate_check': True,
                   'gate_line': [[48.4850573619, 16.4681773891],
                                 [48.4838315715, 16.443100529]],
                   'is_procedure_turn': False,
                   'latitude': 48.4844444667,
                   'longitude': 16.4556388833,
                   'name': 'SC9',
                   'time_check': True,
                   'type': 'secret',
                   'width': 1.0},
                  {'bearing_from_previous': 175.99820478386073,
                   'bearing_next': 175.67752533264934,
                   'distance_next': 9069.622737599375,
                   'distance_previous': 4374.449006833489,
                   'elevation': 1000.0,
                   'end_curved': False,
                   'gate_check': True,
                   'gate_line': [[48.4457813396, 16.4723099945],
                                 [48.4446186604, 16.4472456823]],
                   'is_procedure_turn': False,
                   'latitude': 48.4452,
                   'longitude': 16.4597777667,
                   'name': 'SC10',
                   'time_check': True,
                   'type': 'secret',
                   'width': 1.0},
                  {'bearing_from_previous': 175.67752533264934,
                   'bearing_next': 67.12069565775101,
                   'distance_next': 3887.7757299213763,
                   'distance_previous': 9069.622737599726,
                   'elevation': 1100.0,
                   'end_curved': False,
                   'gate_check': True,
                   'gate_line': [[48.3644942471, 16.4815377138],
                                 [48.3632390863, 16.4565235737]],
                   'is_procedure_turn': True,
                   'latitude': 48.3638666667,
                   'longitude': 16.4690305667,
                   'name': 'TP5',
                   'time_check': True,
                   'type': 'tp',
                   'width': 1.0},
                  {'bearing_from_previous': 67.12069565775101,
                   'bearing_next': 67.15690070431299,
                   'distance_next': 10085.335285784395,
                   'distance_previous': 3887.775729921401,
                   'elevation': 1000.0,
                   'end_curved': False,
                   'gate_check': True,
                   'gate_line': [[48.3851287403, 16.5126532678],
                                 [48.3697712597, 16.5224015305]],
                   'is_procedure_turn': False,
                   'latitude': 48.37745,
                   'longitude': 16.5175277667,
                   'name': 'SC11',
                   'time_check': True,
                   'type': 'secret',
                   'width': 1.0},
                  {'bearing_from_previous': 67.15690070431299,
                   'bearing_next': 166.24719776134498,
                   'distance_next': 9738.016260143093,
                   'distance_previous': 10085.335285784377,
                   'elevation': 1100.0,
                   'end_curved': False,
                   'gate_check': True,
                   'gate_line': [[48.4202740835, 16.6385908584],
                                 [48.4049092499, 16.6483195401]],
                   'is_procedure_turn': True,
                   'latitude': 48.4125916667,
                   'longitude': 16.6434555667,
                   'name': 'TP6',
                   'time_check': True,
                   'type': 'tp',
                   'width': 1.0},
                  {'bearing_from_previous': 166.24719776134498,
                   'bearing_next': 166.27360404895148,
                   'distance_next': 7508.87999856106,
                   'distance_previous': 9738.016260143333,
                   'elevation': 1000.0,
                   'end_curved': False,
                   'gate_check': True,
                   'gate_line': [[48.3295016748, 16.6869447223],
                                 [48.3255427586, 16.6625946837]],
                   'is_procedure_turn': False,
                   'latitude': 48.3275222167,
                   'longitude': 16.6747694667,
                   'name': 'SC12',
                   'time_check': True,
                   'type': 'secret',
                   'width': 1.0},
                  {'bearing_from_previous': 166.27360404895148,
                   'bearing_next': 166.2703826435377,
                   'distance_next': 1835.569168690759,
                   'distance_previous': 7508.879998560919,
                   'elevation': 1000.0,
                   'end_curved': False,
                   'gate_check': True,
                   'gate_line': [[48.2638955613, 16.7109997161],
                                 [48.2599433387, 16.6866784874]],
                   'is_procedure_turn': False,
                   'latitude': 48.26191945,
                   'longitude': 16.6988388667,
                   'name': 'SC13',
                   'time_check': True,
                   'type': 'secret',
                   'width': 1.0},
                  {'bearing_from_previous': 166.2703826435377,
                   'bearing_next': 136.69887262627014,
                   'distance_next': 5805.843891053953,
                   'distance_previous': 1835.5691686903765,
                   'elevation': 1000.0,
                   'end_curved': False,
                   'gate_check': True,
                   'gate_line': [[48.2478608593, 16.716878734],
                                 [48.2439058073, 16.6925661694]],
                   'is_procedure_turn': False,
                   'latitude': 48.2458833333,
                   'longitude': 16.7047222167,
                   'name': 'TP7',
                   'time_check': True,
                   'type': 'tp',
                   'width': 1.0},
                  {'bearing_from_previous': 136.69887262627014,
                   'bearing_next': 136.69604176237306,
                   'distance_next': 8351.980670787441,
                   'distance_previous': 5805.84389105399,
                   'elevation': 1000.0,
                   'end_curved': False,
                   'gate_check': True,
                   'gate_line': [[48.2135853675, 16.7675592276],
                                 [48.2021590659, 16.7493527879]],
                   'is_procedure_turn': False,
                   'latitude': 48.2078722167,
                   'longitude': 16.7584555,
                   'name': 'SC14',
                   'time_check': True,
                   'type': 'secret',
                   'width': 1.0},
                  {'bearing_from_previous': 136.69604176237306,
                   'bearing_next': -1.0,
                   'distance_next': -1.0,
                   'distance_previous': 8351.980670787527,
                   'elevation': 1000.0,
                   'end_curved': False,
                   'gate_check': True,
                   'gate_line': [[48.1588986418, 16.8447699033],
                                 [48.1474735916, 16.8265811091]],
                   'is_procedure_turn': True,
                   'latitude': 48.1531861167,
                   'longitude': 16.835675,
                   'name': 'FP',
                   'time_check': True,
                   'type': 'fp',
                   'width': 1.0}]}

with open("display/tests/demo_contests/2017_WPFC/Route-1-Blue.gpx", "r") as f:
    route_string = base64.b64encode(f.read().encode('utf-8')).decode('utf-8')

data["route_file"] = route_string


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
        permission = Permission.objects.get(codename="change_contest")
        self.user.user_permissions.add(permission)
        self.client.force_login(user=self.user)
        self.contest = Contest.objects.create(name="test")
        assign_perm("display.change_contest", self.user, self.contest)
        assign_perm("display.view_contest", self.user, self.contest)
        get_default_scorecard()

    def test_import(self):
        print(json.dumps(data, sort_keys=True, indent=2))
        res = self.client.post(
            "/api/v1/contests/{}/importnavigationtask/".format(self.contest.pk), data, format="json")
        print(res.content)
        self.assertEqual(status.HTTP_201_CREATED, res.status_code, "Failed to POST importnavigationtask")
        navigation_task_id = res.json()["id"]
        print(res.json())
        task = self.client.get("/api/v1/contests/{}/navigationtasks/{}/".format(self.contest.pk, navigation_task_id))
        self.assertEqual(status.HTTP_200_OK, task.status_code, "Failed to GET navigationtask")
        self.assertEqual(len(data["contestant_set"]), len(task.json()["contestant_set"]))
        teams = Team.objects.all()
        crew = Crew.objects.all()
        self.assertEqual(1, len(crew))
        self.assertEqual(2, len(teams))
        crew = crew.first()
        for team in teams:
            self.assertEqual(crew, team.crew)
            print(team.country)
            self.assertTrue(team.aeroplane.registration in ("LN-YDB", "LN-YDB2"))
            if team.aeroplane.registration == "LN-YDB2":
                self.assertEqual("SE", team.country.code)
            else:
                self.assertEqual("NO", team.country.code)
        for index, contestant in enumerate(task.json()["contestant_set"]):
            self.assertDictEqual(data["contestant_set"][index]["gate_times"], contestant["gate_times"])
        route = task.json()["route"]
        self.assertEqual(len(expected_route["waypoints"]), len(route["waypoints"]))
        for index, waypoint in enumerate(route["waypoints"]):
            self.assertDictEqual(expected_route["waypoints"][index], waypoint)
            self.assertListEqual(expected_route["waypoints"][index]["gate_line"], waypoint["gate_line"])

    def test_doc_example(self):
        with open('../documentation/importnavigationtask.json', 'r') as i:
            data = json.load(i)
        res = self.client.post(
            "/api/v1/contests/{}/importnavigationtask/".format(self.contest.pk), data, format="json")
        self.assertEqual(status.HTTP_201_CREATED, res.status_code, "Failed to POST importnavigationtask")
