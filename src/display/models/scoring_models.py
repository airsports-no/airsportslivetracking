from django.db import models

from display.utilities.gate_definitions import TURNPOINT, GATE_TYPES

ANOMALY = "anomaly"
INFORMATION = "information"
DEBUG = "debug"
ANNOTATION_TYPES = [(ANOMALY, "Anomaly"), (INFORMATION, "Information"), (DEBUG, "Debug")]


class ScoreLogEntry(models.Model):
    time = models.DateTimeField()
    contestant = models.ForeignKey("Contestant", on_delete=models.CASCADE)
    gate = models.CharField(max_length=30, default="")
    message = models.TextField(default="")
    string = models.TextField(default="")
    points = models.FloatField()
    planned = models.DateTimeField(blank=True, null=True)
    actual = models.DateTimeField(blank=True, null=True)
    offset_string = models.CharField(max_length=200, default="")
    times_string = models.CharField(max_length=200, default="")
    type = models.CharField(max_length=30, choices=ANNOTATION_TYPES, default=INFORMATION)

    class Meta:
        ordering = ("time", "pk")

    @classmethod
    def push(cls, entry):
        from websocket_channels import WebsocketFacade

        ws = WebsocketFacade()
        ws.transmit_score_log_entry(entry.contestant)
        return entry

    @classmethod
    def update(cls, pk: int, **kwargs):
        cls.objects.filter(pk=pk).update(**kwargs)

    @classmethod
    def create_and_push(cls, **kwargs) -> "ScoreLogEntry":
        entry = cls.objects.create(**kwargs)
        cls.push(entry)
        return entry


class TrackAnnotation(models.Model):
    time = models.DateTimeField()
    contestant = models.ForeignKey("Contestant", on_delete=models.CASCADE)
    score_log_entry = models.ForeignKey(ScoreLogEntry, on_delete=models.CASCADE)
    latitude = models.FloatField()
    longitude = models.FloatField()
    message = models.TextField()
    gate = models.CharField(max_length=30, blank=True, default="")
    gate_type = models.CharField(max_length=30, blank=True, default=TURNPOINT, choices=GATE_TYPES)
    type = models.CharField(max_length=30, choices=ANNOTATION_TYPES)

    class Meta:
        ordering = ("time",)

    @classmethod
    def update(cls, pk, **kwargs):
        cls.objects.filter(pk=pk).update(**kwargs)

    @classmethod
    def push(cls, annotation):
        from websocket_channels import WebsocketFacade

        ws = WebsocketFacade()
        ws.transmit_annotations(annotation.contestant)

    @classmethod
    def create_and_push(cls, **kwargs) -> "TrackAnnotation":
        annotation = cls.objects.create(**kwargs)
        cls.push(annotation)
        return annotation


class GateCumulativeScore(models.Model):
    contestant = models.ForeignKey("Contestant", on_delete=models.CASCADE)
    gate = models.CharField(max_length=30)
    points = models.FloatField(default=0)

    class Meta:
        unique_together = ("contestant", "gate")


class ActualGateTime(models.Model):
    contestant = models.ForeignKey("Contestant", on_delete=models.CASCADE)
    gate = models.CharField(max_length=30)
    time = models.DateTimeField()

    class Meta:
        unique_together = ("contestant", "gate")
