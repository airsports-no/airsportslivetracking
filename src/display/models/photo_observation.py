from django.db import models


class PhotoObservation(models.Model):
    """
    A crew's registration of an observation photo, made from the app at the moment they spot the target.
    The position and time are the crew's own; the remaining fields are the result of scoring it with
    display.calculators.photo_observation_calculator (the equivalent of the line drawn across the track on a
    paper map).
    """

    contestant = models.ForeignKey("Contestant", on_delete=models.CASCADE, related_name="photo_observations")
    photo = models.ForeignKey("Photo", on_delete=models.SET_NULL, null=True, blank=True, related_name="observations")
    # The photo's name is kept separately so the registration survives the photo being regenerated
    photo_name = models.CharField(max_length=200)
    time = models.DateTimeField()
    latitude = models.FloatField()
    longitude = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    # Scoring result
    scored = models.BooleanField(default=False)
    status = models.CharField(max_length=40, default="", blank=True)
    error_m = models.FloatField(null=True, blank=True)
    error_mm = models.FloatField(null=True, blank=True)
    score_fraction = models.FloatField(default=0.0)
    # Change to the contestant's score caused by this observation (negative is a deduction on descending scorecards)
    points = models.FloatField(default=0.0)
    metres_per_mm = models.FloatField(null=True, blank=True)
    # Where the crew's position and the photo target end up when projected onto the track
    projected_latitude = models.FloatField(null=True, blank=True)
    projected_longitude = models.FloatField(null=True, blank=True)
    photo_projected_latitude = models.FloatField(null=True, blank=True)
    photo_projected_longitude = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ("time",)
        constraints = [
            models.UniqueConstraint(fields=["contestant", "photo"], name="unique_photo_observation_per_photo")
        ]

    def __str__(self):
        return f"{self.contestant_id}: {self.photo_name} @ {self.time}"
