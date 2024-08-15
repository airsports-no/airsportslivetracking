"""
The results service system is quite disconnected from the navigation task. The tasks and task tests defined in this 
module are generic elements used to describe any specific test that should be scored, e.g. a landing, an observation 
test, et cetera. The score is connected directly to the teams that have signed up to the contest.
"""

from typing import Optional

from django.db import models


class Task(models.Model):
    """
    Models a generic task for which we want to store scores. This is used by the results service and is not part of
    the contest->navigation_task hierarchy.
    """

    DESCENDING = "desc"
    ASCENDING = "asc"
    SORTING_DIRECTION = ((DESCENDING, "Highest score is best"), (ASCENDING, "Lowest score is best"))
    summary_score_sorting_direction = models.CharField(
        default=ASCENDING,
        choices=SORTING_DIRECTION,
        help_text="Whether the lowest (ascending) or highest (ascending) score is the best result",
        max_length=50,
    )
    weight = models.FloatField(default=1)
    name = models.CharField(max_length=100)
    heading = models.CharField(max_length=100)
    contest = models.ForeignKey("Contest", on_delete=models.CASCADE)
    index = models.IntegerField(
        help_text="The index of the task when displayed as columns in a table. Indexes are sorted in ascending order to determine column order",
        default=0,
    )
    autosum_scores = models.BooleanField(
        default=True,
        help_text="If true, the server sum all tests into TaskSummary when any test is updated",
    )

    class Meta:
        unique_together = ("name", "contest")
        ordering = ("index",)


class TaskTest(models.Model):
    """
    Models and individual test (e.g. landing one, landing two, or landing three that is part of a task. It includes
    the configuration for how the score is displayed for the test. When creating a navigation task a special
    corresponding TaskTest is created that is linked to the navigation task. While the scores of TaskTests usually are
    manually entered through the results table GUI or the API, the scores of this special TaskTest are updated
    automatically whenever a scoring event occurs in the navigation task calculator.
    """

    DESCENDING = "desc"
    ASCENDING = "asc"
    SORTING_DIRECTION = ((DESCENDING, "Highest score is best"), (ASCENDING, "Lowest score is best"))
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    navigation_task = models.OneToOneField("NavigationTask", on_delete=models.SET_NULL, blank=True, null=True)
    weight = models.FloatField(default=1)
    name = models.CharField(max_length=100)
    heading = models.CharField(max_length=100)
    sorting = models.CharField(
        default=ASCENDING,
        choices=SORTING_DIRECTION,
        help_text="Whether the lowest (ascending) or highest (ascending) score is the best result",
        max_length=50,
    )
    index = models.IntegerField(
        help_text="The index of the task when displayed as columns in a table. Indexes are sorted in ascending order to determine column order",
        default=0,
    )

    class Meta:
        unique_together = ("name", "task")
        ordering = ("index",)

    @property
    def navigation_task_link(self) -> Optional[str]:
        if self.navigation_task:
            return self.navigation_task.tracking_link
        return None


class TaskSummary(models.Model):
    """
    Summary score for all tests inside a task for a team. This is potentially automatically updated whenever a test
    score changes for a team.
    """

    team = models.ForeignKey("Team", on_delete=models.PROTECT)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    points = models.FloatField()

    class Meta:
        unique_together = ("team", "task")

    def update_sum(self):
        if self.task.autosum_scores:
            tests = TeamTestScore.objects.filter(team=self.team, task_test__task=self.task)
            if tests.exists():
                total = sum([test.points * test.task_test.weight for test in tests])
                self.points = total
            else:
                self.points = 0
            self.save()


class ContestSummary(models.Model):
    """
    Summary score for the entire contest for a team. This is potentially automatically updated whenever the TaskSummary
    score changes for a team.
    """

    team = models.ForeignKey("Team", on_delete=models.PROTECT)
    contest = models.ForeignKey("Contest", on_delete=models.CASCADE)
    points = models.FloatField()

    class Meta:
        unique_together = ("team", "contest")

    def update_sum(self):
        if self.contest.autosum_scores:
            tasks = TaskSummary.objects.filter(team=self.team, task__contest=self.contest)
            if tasks.exists():
                total = sum([task.points * task.task.weight for task in tasks])
                self.points = total
            else:
                self.points = 0
            self.save()


class TeamTestScore(models.Model):
    """
    Represents the score a team received for a test. Note that this is different from a navigation task where a score
    is directly connected to a contestant.
    """

    team = models.ForeignKey("Team", on_delete=models.PROTECT)
    task_test = models.ForeignKey(TaskTest, on_delete=models.CASCADE)
    points = models.FloatField()

    class Meta:
        unique_together = ("team", "task_test")
