from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


def default_points_table() -> list[int]:
    """Points for a first, second, third… place when a series scores with a points table."""
    return [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]


class Series(models.Model):
    """
    A series ranks the teams of several contests (its legs) together, for organisers who run a cup or championship over
    contests held at different places. Nothing is stored about the ranking: the standings are worked out from the results
    of the legs whenever they are asked for (display/services/series_standings.py). The contests stay as they are.
    """

    PLACEMENTS = "placements"
    POINTS_TABLE = "points_table"
    SCORING_METHODS = (
        (PLACEMENTS, "Sum of placements, lowest total wins"),
        (POINTS_TABLE, "Points for each placement from a table, highest total wins"),
    )
    PILOT = "pilot"
    CREW = "crew"
    ENTRANT_IDENTITIES = (
        (PILOT, "The pilot, whoever the navigator or the aeroplane is"),
        (CREW, "The crew: the same pilot and navigator"),
    )

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")
    is_public = models.BooleanField(
        default=False,
        help_text="A public series is visible to everybody and can only contain public contests. A private series is only visible to the people who manage it.",
    )
    scoring_method = models.CharField(max_length=20, choices=SCORING_METHODS, default=PLACEMENTS)
    entrant_identity = models.CharField(
        max_length=10,
        choices=ENTRANT_IDENTITIES,
        default=PILOT,
        help_text="Who is ranked: results of different teams in different contests are added up for the same entrant.",
    )
    best_results_counted = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Only the best this many legs count towards the total. Empty: all legs count.",
    )
    points_table = models.JSONField(
        default=default_points_table,
        blank=True,
        help_text="Points for first, second, third… place. Used when the scoring method is a points table; later places get nothing.",
    )
    contests = models.ManyToManyField("Contest", through="SeriesContest", related_name="series")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_series"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)
        verbose_name_plural = "series"

    def clean(self):
        table = self.points_table
        if not isinstance(table, list) or not all(isinstance(item, (int, float)) and item >= 0 for item in table):
            raise ValidationError("The points table is a list of numbers that are not negative.")
        if self.scoring_method == self.POINTS_TABLE and not table:
            raise ValidationError("A series scored with a points table needs a points table.")

    def __str__(self):
        return self.name


class SeriesContest(models.Model):
    """A contest that is a leg of a series."""

    series = models.ForeignKey(Series, on_delete=models.CASCADE)
    contest = models.ForeignKey("Contest", on_delete=models.CASCADE)
    leg_number = models.PositiveSmallIntegerField(
        default=0,
        help_text="Orders the legs in the standings, lowest first. Legs with the same number are ordered by date.",
    )
    weight = models.FloatField(default=1, help_text="The placement points of the leg are multiplied by this.")
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("leg_number", "contest__start_time")
        constraints = [models.UniqueConstraint(fields=["series", "contest"], name="unique_series_contest")]

    def __str__(self):
        return f"{self.contest} in {self.series}"
