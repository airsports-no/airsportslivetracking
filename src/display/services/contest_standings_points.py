"""
The overall result of a contest made from standings points: FAI Sporting Code Section 10 Annex 9 (Air Sport Race), 6.7.7,
gives as an example (for local rules to decide) that each task gives points for the place in it, 25 / 20 / 16 / … for
first, second, third place and so on, and that these points are added up instead of the raw task scores.

The ranking is the one of the series (display/services/series_standings.py): every task is a "leg" that is ranked by its
own best-is direction, ties share a place and the next place is skipped (1, 2, 2, 4), the table gives points per place
(nothing beyond the end of it), a team without a result in a task gets nothing for it, and equal totals are separated
by countback (more first places, then second places, and so on).

The totals are written into `ContestSummary.points` (ContestSummary.update_sum), so everything that reads the overall
result keeps working. The place and the points of each team in each task are only needed to show the table, and are
worked out when the results are read (`standings_points_details`).
"""

import logging
from typing import Optional

from django.db import transaction

from display.models import Contest, ContestSummary, Task, TaskSummary
from display.models.contest import default_standings_points_table
from display.services.series_standings import RANKED, LegResults, compute_standings

logger = logging.getLogger(__name__)


def uses_standings_points(contest: Contest) -> bool:
    return contest.overall_result_method == Contest.STANDINGS_POINTS


def points_table_of(contest: Contest) -> list[float]:
    table = contest.standings_points_table
    return table if isinstance(table, list) else default_standings_points_table()


def task_legs(contest: Contest, exclude_task_id: Optional[int] = None) -> tuple[list[LegResults], set[int]]:
    """The tasks of the contest as legs of scores per team, and the teams that have an overall result row."""
    registered = set(ContestSummary.objects.filter(contest=contest).values_list("team_id", flat=True))
    scores: dict[int, dict[int, float]] = {}
    task_summaries = TaskSummary.objects.filter(task__contest=contest).exclude(task_id=exclude_task_id)
    for team_id, task_id, points in task_summaries.values_list("team_id", "task_id", "points"):
        scores.setdefault(task_id, {})[team_id] = points
    legs = [
        LegResults(
            contest_id=task.pk,
            name=task.name,
            weight=1.0,
            # Every task is ranked by its own direction: highest wins for a quality scored navigation task
            highest_wins=task.summary_score_sorting_direction == Task.DESCENDING,
            scores=scores.get(task.pk, {}),
            registered=registered - set(scores.get(task.pk, {})),
        )
        for task in Task.objects.filter(contest=contest).exclude(pk=exclude_task_id).order_by("index", "pk")
    ]
    return legs, registered


def compute_standings_points(legs: list[LegResults], points_table: list[float]) -> dict:
    """
    The standings points of the teams of [legs]: {"totals": {team: points}, "ranks": {team: rank},
    "tasks": {task id: {team: {"place": place, "points": points}}}}. Pure: nothing is read from the database.
    """
    standings = compute_standings(legs, "points_table", points_table=points_table)
    totals: dict = {}
    ranks: dict = {}
    tasks: dict = {leg.contest_id: {} for leg in legs}
    for row in standings["rows"]:
        totals[row["entrant"]] = row["total"]
        ranks[row["entrant"]] = row["rank"]
        for cell in row["legs"]:
            if cell["status"] == RANKED:
                tasks[cell["contest_id"]][row["entrant"]] = {"place": cell["placement"], "points": cell["points"]}
    return {"totals": totals, "ranks": ranks, "tasks": tasks}


def standings_points_details(contest: Contest) -> Optional[dict]:
    """What the results table needs to show standings points, None for a contest that sums the task scores."""
    if not uses_standings_points(contest):
        return None
    legs, _ = task_legs(contest)
    computed = compute_standings_points(legs, points_table_of(contest))
    return {
        "points_table": points_table_of(contest),
        "ranks": {str(team_id): rank for team_id, rank in computed["ranks"].items()},
        "tasks": {
            str(task_id): {str(team_id): cell for team_id, cell in teams.items()}
            for task_id, teams in computed["tasks"].items()
        },
    }


def recompute_contest_summaries(contest: Contest, exclude_task_id: Optional[int] = None) -> bool:
    """
    Write the standings points into the overall result of every team of [contest]. A change of one team's score changes
    the places of the others, so all teams are written. Does nothing (False) unless the contest sums its scores
    automatically with standings points. Teams that have task results get an overall result if they had none.
    """
    if not (contest.autosum_scores and uses_standings_points(contest)):
        return False
    legs, _ = task_legs(contest, exclude_task_id)
    totals = compute_standings_points(legs, points_table_of(contest))["totals"]
    existing = {summary.team_id: summary for summary in ContestSummary.objects.filter(contest=contest)}
    changed_teams = []
    for team_id, total in totals.items():
        summary = existing.get(team_id)
        if summary is None:
            ContestSummary.objects.get_or_create(contest=contest, team_id=team_id, defaults={"points": total})
            changed_teams.append(team_id)
        elif summary.points != total:
            # No save(): the signals would each send all the results; one is sent below
            ContestSummary.objects.filter(pk=summary.pk).update(points=total)
            changed_teams.append(team_id)
    if changed_teams:
        announce_results(contest)
    return True


def announce_results(contest: Contest) -> None:
    """Send all the results of the contest once the transaction is committed."""
    from websocket_channels import WebsocketFacade

    def send_update():
        try:
            ws = WebsocketFacade()
            ws.transmit_contest_results(None, contest)
        except Exception:
            logger.exception("Could not send the results of contest %s after recomputing standings points", contest.pk)

    transaction.on_commit(send_update)
