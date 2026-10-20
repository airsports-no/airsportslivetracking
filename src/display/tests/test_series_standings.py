"""
The standings of a series: the calculation on its own (compute_standings), then the loading of the results of real
contests (series_standings), where the pilot is the same person in different teams.
"""

import datetime

from django.test import SimpleTestCase, TestCase

from display.models import Aeroplane, Club, Contest, ContestSummary, ContestTeam, Crew, Person, Series, SeriesContest, Team
from display.services.series_standings import (
    ABSENT,
    NO_RESULT,
    RANKED,
    LegResults,
    compute_standings,
    place_entrants,
    series_standings,
)


def leg(contest_id, scores, registered=(), highest_wins=False, weight=1.0):
    return LegResults(
        contest_id=contest_id,
        name=f"Leg {contest_id}",
        weight=weight,
        highest_wins=highest_wins,
        scores=scores,
        registered=set(registered),
    )


def totals(standings):
    return {row["entrant"]: row["total"] for row in standings["rows"]}


def ranks(standings):
    return {row["entrant"]: row["rank"] for row in standings["rows"]}


def three_legs():
    return [
        leg(1, {"a": 10, "b": 20, "c": 30}),  # lowest wins: a, b, c
        leg(2, {"b": 100, "a": 50}, registered=["c"], highest_wins=True),  # highest wins: b, a; c flew nothing
        leg(3, {"a": 5}),  # only a took part
    ]


class TestPlaceEntrants(SimpleTestCase):
    def test_lowest_wins(self):
        self.assertEqual(place_entrants({"a": 30, "b": 10, "c": 20}, highest_wins=False), {"b": 1, "c": 2, "a": 3})

    def test_highest_wins(self):
        self.assertEqual(place_entrants({"a": 30, "b": 10, "c": 20}, highest_wins=True), {"a": 1, "c": 2, "b": 3})

    def test_ties_share_a_place_and_the_next_is_skipped(self):
        self.assertEqual(place_entrants({"a": 10, "b": 10, "c": 20, "d": 30}, False), {"a": 1, "b": 1, "c": 3, "d": 4})

    def test_scores_that_differ_by_rounding_noise_are_tied(self):
        self.assertEqual(place_entrants({"a": 0.1 + 0.2, "b": 0.3}, False), {"a": 1, "b": 1})


class TestSumOfPlacements(SimpleTestCase):
    def test_placements_are_added_and_the_lowest_total_wins(self):
        standings = compute_standings(three_legs())
        self.assertEqual(totals(standings), {"a": 1 + 2 + 1, "b": 2 + 1 + 2, "c": 3 + 4 + 2})
        self.assertEqual([row["entrant"] for row in standings["rows"]], ["a", "b", "c"])
        self.assertEqual([row["rank"] for row in standings["rows"]], [1, 2, 3])

    def test_a_missing_result_is_the_number_of_entrants_in_the_leg_plus_one(self):
        standings = compute_standings(three_legs())
        cells = {row["entrant"]: row["legs"] for row in standings["rows"]}
        # Leg 2: a, b and c were registered, so three entrants: c scores 4
        self.assertEqual((cells["c"][1]["status"], cells["c"][1]["points"]), (NO_RESULT, 4))
        # Leg 3: only a was in it, so one entrant: anybody who was not gets 2
        self.assertEqual((cells["b"][2]["status"], cells["b"][2]["points"]), (ABSENT, 2))
        self.assertEqual((cells["a"][2]["status"], cells["a"][2]["placement"]), (RANKED, 1))

    def test_the_weight_of_a_leg_multiplies_its_points_also_the_penalty(self):
        legs = three_legs()
        legs[2].weight = 2
        standings = compute_standings(legs)
        self.assertEqual(totals(standings), {"a": 1 + 2 + 2, "b": 2 + 1 + 4, "c": 3 + 4 + 4})

    def test_legs_are_ranked_by_their_own_sort_direction(self):
        # The same scores, lowest wins in one leg and highest wins in the other: the placements are opposite
        standings = compute_standings([leg(1, {"a": 1, "b": 2}), leg(2, {"a": 1, "b": 2}, highest_wins=True)])
        self.assertEqual(totals(standings), {"a": 3, "b": 3})
        self.assertEqual(set(ranks(standings).values()), {1})

    def test_nothing_without_legs(self):
        self.assertEqual(compute_standings([]), {"legs": [], "rows": []})


class TestBestResultsCounted(SimpleTestCase):
    def test_only_the_best_legs_add_to_the_total(self):
        standings = compute_standings(three_legs(), best_results_counted=2)
        self.assertEqual(totals(standings), {"a": 1 + 1, "b": 1 + 2, "c": 2 + 3})
        a = next(row for row in standings["rows"] if row["entrant"] == "a")
        self.assertEqual([cell["counted"] for cell in a["legs"]], [True, False, True])

    def test_counting_more_legs_than_there_are_counts_them_all(self):
        self.assertEqual(totals(compute_standings(three_legs(), best_results_counted=5)), totals(compute_standings(three_legs())))


class TestPointsTable(SimpleTestCase):
    def test_places_give_points_and_the_highest_total_wins(self):
        standings = compute_standings(three_legs(), "points_table", points_table=[10, 6, 3])
        self.assertEqual(totals(standings), {"a": 10 + 6 + 10, "b": 6 + 10 + 0, "c": 3 + 0 + 0})
        self.assertEqual([row["entrant"] for row in standings["rows"]], ["a", "b", "c"])

    def test_places_beyond_the_table_and_missing_results_give_nothing(self):
        standings = compute_standings([leg(1, {"a": 1, "b": 2, "c": 3, "d": 4})], "points_table", points_table=[5, 3])
        self.assertEqual(totals(standings), {"a": 5, "b": 3, "c": 0, "d": 0})

    def test_tied_entrants_get_the_points_of_the_higher_place(self):
        standings = compute_standings([leg(1, {"a": 1, "b": 1, "c": 2})], "points_table", points_table=[10, 6, 3])
        self.assertEqual(totals(standings), {"a": 10, "b": 10, "c": 3})

    def test_the_weight_multiplies_the_points(self):
        standings = compute_standings([leg(1, {"a": 1, "b": 2}, weight=2)], "points_table", points_table=[10, 6])
        self.assertEqual(totals(standings), {"a": 20, "b": 12})

    def test_best_legs_are_the_ones_with_most_points(self):
        legs = [leg(1, {"a": 1, "b": 2}), leg(2, {"b": 1, "a": 2}), leg(3, {"a": 1, "b": 2})]
        standings = compute_standings(legs, "points_table", best_results_counted=2, points_table=[10, 6])
        self.assertEqual(totals(standings), {"a": 20, "b": 16})


class TestTieBreaks(SimpleTestCase):
    def setUp(self):
        # Every entrant ends on four: x has a first and a third, y two seconds, z a third and a first
        self.legs = [leg(1, {"x": 1, "z": 2, "y": 3}), leg(2, {"y": 1, "z": 2, "x": 3})]
        self.legs = [
            leg(1, {"x": 1, "y": 2, "z": 3}),
            leg(2, {"z": 1, "y": 2, "x": 3}),
        ]

    def test_equal_totals_are_separated_by_countback(self):
        standings = compute_standings(self.legs)
        self.assertEqual(totals(standings), {"x": 4, "y": 4, "z": 4})
        self.assertEqual(ranks(standings)["y"], 3, "y has no first place")

    def test_entrants_level_on_everything_share_a_rank(self):
        standings = compute_standings(self.legs)
        self.assertEqual((ranks(standings)["x"], ranks(standings)["z"]), (1, 1))


def make_person(name, email):
    return Person.objects.create(first_name=name, last_name="Pilot", email=email)


def make_team(pilot, navigator=None, registration="LN-AAA", club=None):
    crew, _ = Crew.objects.get_or_create(member1=pilot, member2=navigator)
    aeroplane, _ = Aeroplane.objects.get_or_create(registration=registration)
    return Team.objects.create(crew=crew, aeroplane=aeroplane, club=club)


def make_contest(name, direction=Contest.ASCENDING):
    now = datetime.datetime.now(datetime.timezone.utc)
    return Contest.objects.create(
        name=name,
        start_time=now,
        finish_time=now + datetime.timedelta(days=1),
        location="60, 11",
        summary_score_sorting_direction=direction,
    )


def score(contest, team, points):
    ContestTeam.objects.get_or_create(contest=contest, team=team)
    ContestSummary.objects.create(contest=contest, team=team, points=points)


class TestSeriesStandingsFromResults(TestCase):
    def setUp(self):
        self.series = Series.objects.create(name="Cup")
        self.anna = make_person("Anna", "anna@example.com")
        self.bjorn = make_person("Bjorn", "bjorn@example.com")
        self.carl = make_person("Carl", "carl@example.com")
        self.leg1 = make_contest("Leg 1")
        self.leg2 = make_contest("Leg 2")
        for number, contest in enumerate((self.leg1, self.leg2), start=1):
            SeriesContest.objects.create(series=self.series, contest=contest, leg_number=number)

    def rows(self):
        standings = series_standings(self.series)
        return {row["entrant"]["name"]: row for row in standings["rows"]}, standings

    def test_a_pilot_in_different_aeroplanes_and_with_different_navigators_is_one_entrant(self):
        score(self.leg1, make_team(self.anna, self.bjorn, "LN-AAA"), 10)
        score(self.leg1, make_team(self.carl, None, "LN-CCC"), 20)
        score(self.leg2, make_team(self.anna, self.carl, "LN-BBB"), 30)  # another aeroplane, another navigator
        score(self.leg2, make_team(self.carl, None, "LN-CCC"), 40)
        rows, standings = self.rows()
        self.assertEqual(set(rows), {"Anna Pilot", "Carl Pilot"}, "the navigators are not ranked")
        self.assertEqual((rows["Anna Pilot"]["total"], rows["Carl Pilot"]["total"]), (2, 4))
        self.assertEqual([row["entrant"]["name"] for row in standings["rows"]], ["Anna Pilot", "Carl Pilot"])

    def test_with_crews_the_same_pilot_with_another_navigator_is_another_entrant(self):
        self.series.entrant_identity = Series.CREW
        self.series.save()
        score(self.leg1, make_team(self.anna, self.bjorn, "LN-AAA"), 10)
        score(self.leg2, make_team(self.bjorn, self.anna, "LN-BBB"), 30)  # the same two people, the other way round
        score(self.leg2, make_team(self.anna, self.carl, "LN-CCC"), 5)
        rows, _ = self.rows()
        self.assertEqual(set(rows), {"Anna Pilot and Bjorn Pilot", "Anna Pilot and Carl Pilot"})
        self.assertEqual(rows["Anna Pilot and Bjorn Pilot"]["total"], 1 + 2, "both legs, as the same crew")

    def test_each_leg_is_ranked_by_the_sort_direction_of_its_contest(self):
        self.leg2.summary_score_sorting_direction = Contest.DESCENDING
        self.leg2.save()
        score(self.leg1, make_team(self.anna), 10)
        score(self.leg1, make_team(self.bjorn, registration="LN-BBB"), 20)
        score(self.leg2, make_team(self.anna), 10)
        score(self.leg2, make_team(self.bjorn, registration="LN-BBB"), 20)
        rows, _ = self.rows()
        self.assertEqual((rows["Anna Pilot"]["total"], rows["Bjorn Pilot"]["total"]), (3, 3))

    def test_a_registered_pilot_without_a_result_gets_the_penalty(self):
        score(self.leg1, make_team(self.anna), 10)
        ContestTeam.objects.create(contest=self.leg1, team=make_team(self.bjorn, registration="LN-BBB"))
        score(self.leg2, make_team(self.anna), 10)
        rows, _ = self.rows()
        self.assertEqual([cell["status"] for cell in rows["Bjorn Pilot"]["legs"]], [NO_RESULT, ABSENT])
        # Leg 1 has two entrants (Anna and Bjorn), so 2 + 1; in leg 2 only Anna is in it, so 1 + 1
        self.assertEqual(rows["Bjorn Pilot"]["total"], 3 + 2)

    def test_the_standings_name_the_entrants_and_the_latest_club(self):
        club = Club.objects.create(name="Kjeller Flyklubb")
        score(self.leg1, make_team(self.anna, club=None), 10)
        score(self.leg2, make_team(self.anna, club=club), 10)
        rows, standings = self.rows()
        self.assertEqual(rows["Anna Pilot"]["entrant"]["club"], "Kjeller Flyklubb")
        self.assertEqual(standings["name"], "Cup")
        self.assertEqual([leg["name"] for leg in standings["legs"]], ["Leg 1", "Leg 2"])

    def test_legs_follow_their_leg_number(self):
        SeriesContest.objects.filter(contest=self.leg1).update(leg_number=9)
        _, standings = self.rows()
        self.assertEqual([leg["name"] for leg in standings["legs"]], ["Leg 2", "Leg 1"])

    def test_a_series_without_legs_has_no_standings(self):
        empty = Series.objects.create(name="Empty")
        self.assertEqual(series_standings(empty)["rows"], [])
