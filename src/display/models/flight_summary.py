from django.conf import settings
from django.db import models


class FlightSummary(models.Model):
    """
    An AI-written debrief of one contestant's scored flight, generated from its score log (see
    display.services.flight_summaries). It is only written once per version of the scores: the row is keyed on the
    contestant's track_version and score_version (and the prompt's version), so asking again returns this one for free
    until a restart or an administrative change bumps them.
    """

    STATUS_PENDING = "pending"
    STATUS_DONE = "done"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = ((STATUS_PENDING, "Pending"), (STATUS_DONE, "Done"), (STATUS_FAILED, "Failed"))

    contestant = models.ForeignKey("Contestant", on_delete=models.CASCADE, related_name="flight_summaries")
    track_version = models.IntegerField()
    score_version = models.IntegerField()
    prompt_version = models.IntegerField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    # The whole summary as plain text, and as the website shows it: a headline and sections of emoji, title and text
    text = models.TextField(default="", blank=True)
    headline = models.CharField(max_length=500, default="", blank=True)
    sections = models.JSONField(default=list, blank=True)
    # The numbers the text was written from (display.services.flight_analysis): legs, wind, weather, the field
    analysis = models.JSONField(default=dict, blank=True)
    error = models.CharField(max_length=500, default="", blank=True)
    model = models.CharField(max_length=100, default="", blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    # When the generation that wrote (or is writing) this row was asked for: the daily quota counts these
    requested_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("contestant", "track_version", "score_version", "prompt_version")
        indexes = [models.Index(fields=["requested_by", "requested_at"], name="flight_summary_quota_idx")]

    def __str__(self):
        return f"Flight summary for {self.contestant} ({self.status})"
