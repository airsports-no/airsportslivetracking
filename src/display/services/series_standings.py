"""
The standings of a series (display/models/series.py), worked out from the results of its legs.

`compute_standings` is a pure function of the legs' results, so the rules can be tested without a database; `series_standings`
loads the results of a series and uses it. Each leg is ranked by its own sort direction, so legs scored in different ways
(a lowest-wins precision task and a highest-wins one) can be added up: it is the placements that are added.

The rules:
- Within a leg the entrants with a result are ranked by their score; entrants with the same score share a place and the
  next place is skipped (1, 2, 2, 4).
- Scored with placements, an entrant's points for a leg are the place times the weight of the leg. An entrant with no
  result in the leg, because they were registered without scoring or were not in the leg at all, gets the number of
  entrants in the leg plus one. Lowest total wins.
- Scored with a points table, the place gives the points in the table (nothing beyond the end of it) and a missing result
  gives nothing. Highest total wins.
- With "best N results counted" only the N best legs of an entrant add to the total; the others are shown but left out.
- Equal totals are separated by countback (the entrant with more first places wins, then second places, and so on) and
  entrants who are level on all of that share a rank.
"""

from dataclasses import dataclass, field
from typing import Hashable, Optional

from display.models import ContestSummary, ContestTeam, Series, SeriesContest

# A score is the same as another to this many decimals; the results are floats that were summed
SCORE_PRECISION = 6

RANKED = "ranked"
NO_RESULT = "no_result"
ABSENT = "absent"


@dataclass
class LegResults:
    """What happened in one leg: the score of each entrant that has one, and everybody that was registered."""

    contest_id: int
    name: str
    weight: float
    highest_wins: bool
    scores: dict[Hashable, float]
    registered: set[Hashable] = field(default_factory=set)

    @property
    def entrants(self) -> set[Hashable]:
        return set(self.scores) | set(self.registered)


def place_entrants(scores: dict[Hashable, float], highest_wins: bool) -> dict[Hashable, int]:
    """Competition ranking of the entrants by score: 1, 2, 2, 4."""
    ordered = sorted(scores.items(), key=lambda item: round(item[1], SCORE_PRECISION), reverse=highest_wins)
    places: dict[Hashable, int] = {}
    previous = None
    place = 0
    for index, (entrant, score) in enumerate(ordered, start=1):
        value = round(score, SCORE_PRECISION)
        if value != previous:
            place = index
            previous = value
        places[entrant] = place
    return places


def _leg_points(
    leg: LegResults,
    place: Optional[int],
    scoring_method: str,
    points_table: list[float],
) -> float:
    if scoring_method == Series.POINTS_TABLE:
        if place is None:
            return 0.0
        return float(points_table[place - 1] if place <= len(points_table) else 0) * leg.weight
    if place is None:
        place = len(leg.entrants) + 1
    return float(place) * leg.weight


def compute_standings(
    legs: list[LegResults],
    scoring_method: str = Series.PLACEMENTS,
    best_results_counted: Optional[int] = None,
    points_table: Optional[list[float]] = None,
) -> dict:
    """
    The standings of the entrants of [legs]: {"legs": [...], "rows": [...]}, best first. Entrants are the keys of the
    scores and registrations; everybody that appears in some leg is ranked, with a penalty for each leg they are not in.
    """
    points_table = points_table or []
    lower_is_better = scoring_method != Series.POINTS_TABLE
    places_per_leg = [place_entrants(leg.scores, leg.highest_wins) for leg in legs]
    entrants = set().union(*(leg.entrants for leg in legs)) if legs else set()

    rows = []
    for entrant in entrants:
        cells = []
        for leg, places in zip(legs, places_per_leg):
            place = places.get(entrant)
            if place is not None:
                status = RANKED
            elif entrant in leg.registered:
                status = NO_RESULT
            else:
                status = ABSENT
            cells.append(
                {
                    "contest_id": leg.contest_id,
                    "status": status,
                    "placement": place,
                    "score": leg.scores.get(entrant),
                    "points": _leg_points(leg, place, scoring_method, points_table),
                    "counted": True,
                }
            )
        if best_results_counted is not None and best_results_counted < len(cells):
            by_quality = sorted(range(len(cells)), key=lambda i: (cells[i]["points"], i) if lower_is_better else (-cells[i]["points"], i))
            for index in by_quality[best_results_counted:]:
                cells[index]["counted"] = False
        counted = [cell for cell in cells if cell["counted"]]
        placements = [cell["placement"] for cell in counted if cell["placement"] is not None]
        rows.append(
            {
                "entrant": entrant,
                "legs": cells,
                "total": sum(cell["points"] for cell in counted),
                "_placements": placements,
            }
        )

    deepest = max((place for row in rows for place in row["_placements"]), default=0)

    def sort_key(row):
        countback = [-row["_placements"].count(place) for place in range(1, deepest + 1)]
        total = round(row["total"], SCORE_PRECISION)
        return (total if lower_is_better else -total, countback)

    rows.sort(key=lambda row: (sort_key(row), str(row["entrant"])))
    previous_key = None
    rank = 0
    for index, row in enumerate(rows, start=1):
        key = sort_key(row)
        if key != previous_key:
            rank = index
            previous_key = key
        row["rank"] = rank
        del row["_placements"]
    return {
        "legs": [{"contest_id": leg.contest_id, "name": leg.name, "weight": leg.weight} for leg in legs],
        "rows": rows,
    }


def entrant_key(series: Series, crew) -> tuple:
    """Who is ranked for a crew: the pilot, or the exact crew (the same people, whichever of them is the pilot)."""
    if series.entrant_identity == Series.CREW:
        return tuple(sorted({crew.member1_id, crew.member2_id} - {None}))
    return (crew.member1_id,)


def _display(series: Series, team, previous: Optional[dict]) -> dict:
    crew = team.crew
    people = [crew.member1] + ([crew.member2] if series.entrant_identity == Series.CREW and crew.member2 else [])
    # The same two people in another order is the same crew, so the name must not depend on which leg was read last
    people.sort(key=lambda person: person.pk)
    return {
        "name": " and ".join(f"{person.first_name} {person.last_name}".strip() for person in people),
        "country": str(crew.member1.country or ""),
        # The latest club the entrant flew for
        "club": team.club.name if team.club else (previous or {}).get("club", ""),
    }


def load_legs(series: Series) -> tuple[list[LegResults], dict]:
    """The results of the legs of [series], and how to show each entrant."""
    legs: list[LegResults] = []
    display: dict[tuple, dict] = {}
    for link in SeriesContest.objects.filter(series=series).select_related("contest"):
        contest = link.contest
        highest_wins = contest.summary_score_sorting_direction == contest.DESCENDING
        scores: dict[tuple, float] = {}
        registered: set[tuple] = set()
        for contest_team in ContestTeam.objects.filter(contest=contest).select_related(
            "team__crew__member1", "team__crew__member2", "team__club"
        ):
            key = entrant_key(series, contest_team.team.crew)
            registered.add(key)
            display[key] = _display(series, contest_team.team, display.get(key))
        for summary in ContestSummary.objects.filter(contest=contest).select_related(
            "team__crew__member1", "team__crew__member2", "team__club"
        ):
            key = entrant_key(series, summary.team.crew)
            # An entrant can only have one result in a leg; should data say otherwise the better one counts
            if key not in scores or (summary.points > scores[key] if highest_wins else summary.points < scores[key]):
                scores[key] = summary.points
            registered.add(key)
            display.setdefault(key, _display(series, summary.team, None))
        legs.append(
            LegResults(
                contest_id=contest.pk,
                name=contest.name,
                weight=link.weight,
                highest_wins=highest_wins,
                scores=scores,
                registered=registered - set(scores),
            )
        )
    return legs, display


def series_standings(series: Series) -> dict:
    """The standings of [series] with the entrants named, ready for the API."""
    legs, display = load_legs(series)
    standings = compute_standings(legs, series.scoring_method, series.best_results_counted, series.points_table)
    for row in standings["rows"]:
        key = row.pop("entrant")
        row["entrant"] = {"key": "-".join(str(part) for part in key), **display.get(key, {"name": "", "country": "", "club": ""})}
    standings.update(
        {
            "id": series.pk,
            "name": series.name,
            "scoring_method": series.scoring_method,
            "entrant_identity": series.entrant_identity,
            "best_results_counted": series.best_results_counted,
        }
    )
    return standings
