import datetime
import os
from unittest.mock import MagicMock, patch

import requests
from django.test import TestCase, override_settings

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import (
    ActualGateTime,
    Aeroplane,
    Contest,
    Contestant,
    ContestantTrack,
    Crew,
    NavigationTask,
    Person,
    Team,
)
from display.services import flight_weather
from display.services.flight_analysis import analyse_flight
from display.utilities.route_building_utilities import create_precision_route_from_gpx
from display.utilities.tracking_definitions import TRACKING_PILOT
from utilities.mock_utilities import TraccarMock

UTC = datetime.timezone.utc


def model_location(start, hours, elevation=0.0, low_wind=(10, 270), level_wind=(20, 270), level_height=400.0):
    """An Open-Meteo answer with the same weather every hour: one wind at 80 m and another at 975 hPa."""
    times = [(start + datetime.timedelta(hours=hour)).strftime("%Y-%m-%dT%H:%M") for hour in range(hours)]

    def column(value):
        return [value] * hours

    hourly = {"time": times}
    for variable in flight_weather._hourly_variables():
        hourly[variable] = column(None)
    hourly.update(
        {
            "wind_speed_80m": column(low_wind[0]),
            "wind_direction_80m": column(low_wind[1]),
            "wind_speed_975hPa": column(level_wind[0]),
            "wind_direction_975hPa": column(level_wind[1]),
            "geopotential_height_975hPa": column(elevation + level_height),
            "cloud_cover_975hPa": column(80),
            "weather_code": column(45),
            "visibility": column(1200.0),
            "cloud_cover": column(90),
        }
    )
    return {"elevation": elevation, "hourly": hourly}


class FlightWeatherTest(TestCase):
    def setUp(self):
        self.start = datetime.datetime(2026, 9, 12, 10, tzinfo=UTC)

    def test_the_wind_is_interpolated_to_the_height_above_the_ground(self):
        # 1250 ft is 381 m: between 80 m (10 kt) and 400 m (20 kt), close to the upper one
        location = model_location(self.start, 4, elevation=200.0)
        east, north = flight_weather.wind_components_at(location, self.start + datetime.timedelta(minutes=30), 1250)
        speed, direction = flight_weather.to_speed_and_direction(east, north)
        self.assertEqual(direction, 270)
        self.assertAlmostEqual(speed, 10 + 10 * (381 - 80) / (400 - 80), delta=0.2)

    def test_the_wind_is_interpolated_between_the_hours(self):
        location = model_location(self.start, 2)
        location["hourly"]["wind_speed_975hPa"] = [10, 30]
        location["hourly"]["wind_speed_80m"] = [10, 30]
        east, north = flight_weather.wind_components_at(location, self.start + datetime.timedelta(minutes=15), 1250)
        self.assertAlmostEqual(flight_weather.to_speed_and_direction(east, north)[0], 15, delta=0.1)

    def test_no_wind_outside_the_hours_fetched(self):
        location = model_location(self.start, 2)
        self.assertIsNone(flight_weather.wind_components_at(location, self.start + datetime.timedelta(hours=5), 1250))

    def test_wind_directions_go_back_and_forth(self):
        for direction in (0, 45, 90, 180, 270, 359):
            east, north = flight_weather._wind_profile(
                {"elevation": 0, "hourly": {"wind_speed_10m": [12], "wind_direction_10m": [direction]}}, 0
            )[0][1:]
            self.assertEqual(flight_weather.to_speed_and_direction(east, north), (12, direction))

    def test_conditions_name_the_weather_and_estimate_the_cloud_base(self):
        conditions = flight_weather.conditions_at(model_location(self.start, 2, elevation=100.0), self.start)
        self.assertEqual(conditions["weather"], "fog")
        self.assertEqual(conditions["visibility_km"], 1.2)
        self.assertEqual(conditions["cloud_base_ft_above_ground"], 1310)

    @override_settings(OPEN_METEO_API_KEY="")
    def test_the_free_api_is_used_without_a_key_and_failures_give_none(self):
        with patch("display.services.flight_weather.requests.get", side_effect=requests.ConnectionError) as get:
            self.assertIsNone(flight_weather.fetch_weather(60, 11, self.start, self.start))
        self.assertEqual(get.call_args.args[0], flight_weather.FREE_URL)
        self.assertEqual(get.call_args.kwargs["params"]["models"], "icon_seamless")
        self.assertNotIn("apikey", get.call_args.kwargs["params"])

    @override_settings(OPEN_METEO_API_KEY="paid")
    def test_the_paid_api_is_used_with_a_key(self):
        response = MagicMock()
        response.json.return_value = model_location(self.start, 2)
        with patch("display.services.flight_weather.requests.get", return_value=response) as get:
            self.assertIsNotNone(flight_weather.fetch_weather(60, 11, self.start, self.start))
        self.assertEqual(get.call_args.args[0], flight_weather.CUSTOMER_URL)
        self.assertEqual(get.call_args.kwargs["params"]["apikey"], "paid")


@override_settings(FLIGHT_SUMMARY_WIND_HEIGHT_AGL_FT=1250)
class FlightAnalysisTest(TestCase):
    def setUp(self):
        for target in ("display.models.contestant.get_traccar_instance", "display.signals.get_traccar_instance"):
            patcher = patch(target, return_value=TraccarMock)
            patcher.start()
            self.addCleanup(patcher.stop)
        with open(
            os.path.join(os.path.dirname(__file__), "demo_contests", "2017_WPFC", "Route-1-Blue.gpx"), "r"
        ) as file:
            route = create_precision_route_from_gpx(file, True)
        start = datetime.datetime(2026, 9, 12, 10, tzinfo=UTC)
        contest = Contest.objects.create(name="Windy Cup", start_time=start, finish_time=start, is_public=True)
        task = NavigationTask.create(
            name="Windy day",
            original_scorecard=get_default_scorecard(),
            start_time=start,
            finish_time=start + datetime.timedelta(hours=8),
            route=route,
            contest=contest,
            is_public=True,
        )
        self.contestants = []
        for number in (1, 2):
            crew = Crew.objects.create(
                member1=Person.objects.create(first_name="P", last_name=str(number), email=f"p{number}@example.com")
            )
            team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration=f"LN-W{number}"))
            contestant = Contestant.objects.create(
                team=team,
                navigation_task=task,
                tracking_device=TRACKING_PILOT,
                contestant_number=number,
                tracker_start_time=start,
                takeoff_time=start + datetime.timedelta(minutes=30),
                finished_by_time=start + datetime.timedelta(hours=4),
                air_speed=90,
                wind_speed=0,
                wind_direction=0,
            )
            ContestantTrack.objects.update_or_create(
                contestant=contestant, defaults={"calculator_started": True, "calculator_finished": True}
            )
            # Every crew 20 s later at each gate than the one before
            for index, (gate, time) in enumerate(contestant.gate_times.items()):
                ActualGateTime.objects.create(
                    contestant=contestant, gate=gate, time=time + datetime.timedelta(seconds=20 * index * number)
                )
            self.contestants.append(contestant)
        self.weather = model_location(start, 12)

    def analyse(self, weather):
        with patch("display.services.flight_weather.fetch_weather", return_value=weather):
            return analyse_flight(Contestant.objects.get(pk=self.contestants[0].pk))

    def test_a_headwind_the_plan_did_not_have_makes_the_leg_later_and_a_tailwind_earlier(self):
        analysis = self.analyse(self.weather)
        self.assertEqual(analysis["planned_wind"], {"speed_kt": 0, "direction": 0})
        self.assertEqual(analysis["weather_source"], flight_weather.SOURCE)
        legs = [leg for leg in analysis["legs"] if abs(leg["actual_headwind_kt"]) > 5]
        self.assertTrue(legs)
        for leg in legs:
            self.assertEqual(leg["actual_wind"]["direction"], 270)
            self.assertEqual(leg["planned_headwind_kt"], 0)
            self.assertEqual(leg["wind_effect_seconds"] > 0, leg["actual_headwind_kt"] > 0, leg)

    def test_legs_carry_the_planned_and_actual_times(self):
        leg = self.analyse(self.weather)["legs"][1]
        self.assertEqual(leg["actual_seconds"] - leg["planned_seconds"], 20)
        self.assertEqual(leg["offset_at_end_seconds"], 40)

    def test_the_weather_is_described_at_the_start_middle_and_finish(self):
        weather = self.analyse(self.weather)["weather"]
        self.assertEqual([point["when"] for point in weather], ["start", "middle", "finish"])
        self.assertEqual(weather[0]["weather"], "fog")

    def test_without_weather_the_legs_are_still_there(self):
        analysis = self.analyse(None)
        self.assertIsNone(analysis["weather_source"])
        self.assertEqual(analysis["weather"], [])
        self.assertTrue(analysis["legs"])
        self.assertTrue(all(leg["wind_effect_seconds"] is None for leg in analysis["legs"]))

    def test_the_field_and_highlights(self):
        analysis = self.analyse(self.weather)
        gates = list(self.contestants[0].gate_times)
        # The other crew was 40 s later at each gate than the one before
        self.assertEqual(analysis["field_at_gates"][gates[2]]["median_offset_seconds"], 80)
        self.assertEqual(analysis["highlights"]["longest_run_of_gates_without_penalty"], len(analysis["legs"]) + 1)
        self.assertEqual([crew["crew"] for crew in analysis["crews"]], ["P 1", "P 2"])
        self.assertTrue(analysis["crews"][0]["you"])
        self.assertEqual(analysis["field_at_gates"][gates[2]]["your_rank_by_precision"], 1)

    def test_other_crews_of_a_task_that_is_not_public_are_not_named(self):
        NavigationTask.objects.filter(pk=self.contestants[0].navigation_task_id).update(is_public=False)
        crews = self.analyse(self.weather)["crews"]
        self.assertEqual([crew["crew"] for crew in crews], ["P 1", "Crew #2"])
