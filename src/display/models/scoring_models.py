from django.db import models

from display.utilities.gate_definitions import TURNPOINT, GATE_TYPES

ANOMALY = "anomaly"
INFORMATION = "information"
DEBUG = "debug"
ANNOTATION_TYPES = [(ANOMALY, "Anomaly"), (INFORMATION, "Information"), (DEBUG, "Debug")]


class ScoreLogEntry(models.Model):
    """
    Represents the details around the score awarded when passing a gate.
    """
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
        """
        Transmit the score log entry to the front end
        :param entry:
        :return:
        """
        from websocket_channels import WebsocketFacade

        ws = WebsocketFacade()
        ws.transmit_score_log_entry(entry.contestant)
        return entry

    @classmethod
    def update(cls, pk: int, **kwargs):
        """
        Updates an existing score log entry with new data. This is to support continuously updating scores for instance
        when flying outside the corridor.
        """
        cls.objects.filter(pk=pk).update(**kwargs)

    @classmethod
    def create_and_push(cls, **kwargs) -> "ScoreLogEntry":
        entry = cls.objects.create(**kwargs)
        cls.push(entry)
        return entry

    @classmethod
    def get_idempotency_fields(cls, **kwargs) -> dict:
        return {
            "contestant": kwargs["contestant"],
            "time": kwargs["time"],
            "gate": kwargs["gate"],
            "message": kwargs["message"],
            "points": kwargs["points"],
            "planned": kwargs.get("planned"),
            "actual": kwargs.get("actual"),
            "type": kwargs.get("type", INFORMATION),
        }

    @classmethod
    def get_or_create_and_push(cls, **kwargs) -> tuple["ScoreLogEntry", bool]:
        lookup = cls.get_idempotency_fields(**kwargs)
        defaults = {
            "string": kwargs.get("string", ""),
            "offset_string": kwargs.get("offset_string", ""),
            "times_string": kwargs.get("times_string", ""),
        }
        entry, created = cls.objects.get_or_create(**lookup, defaults=defaults)
        if not created:
            dirty_fields = []
            for field, value in defaults.items():
                if getattr(entry, field) != value:
                    setattr(entry, field, value)
                    dirty_fields.append(field)
            if dirty_fields:
                entry.save(update_fields=dirty_fields)
        cls.push(entry)
        return entry, created


class AdministrativePenalty(models.Model):
    CATEGORY_QUARANTINE = "quarantine"
    CATEGORY_FUEL = "fuel"
    CATEGORY_INSTRUCTIONS = "instructions"
    CATEGORY_OBSERVATION = "observation"
    CATEGORY_MAP = "map"
    CATEGORY_CHOICES = (
        (CATEGORY_QUARANTINE, "Quarantine"),
        (CATEGORY_FUEL, "Fuel check"),
        (CATEGORY_INSTRUCTIONS, "Task instructions"),
        (CATEGORY_OBSERVATION, "Observation evidence"),
        (CATEGORY_MAP, "Map placement"),
    )

    score_log_entry = models.OneToOneField(ScoreLogEntry, on_delete=models.CASCADE)
    contestant = models.ForeignKey("Contestant", on_delete=models.CASCADE)
    actor = models.ForeignKey("MyUser", on_delete=models.SET_NULL, null=True, blank=True)
    category = models.CharField(max_length=40, choices=CATEGORY_CHOICES)
    reason = models.TextField(default="")
    created_at = models.DateTimeField(auto_now_add=True)


class TrackAnnotation(models.Model):
    """
    Holds a data point that should  be displayed on the tracking map for the user. Goes hand-in-hand with ScoreLogEntry,
    but where the former appears in the score details list, these entities are displayed at specific positions on the
    map where the event occurred.
    """
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
        """
        Transmit the annotation to the front end
        """
        from websocket_channels import WebsocketFacade

        ws = WebsocketFacade()
        ws.transmit_annotations(annotation.contestant)

    @classmethod
    def create_and_push(cls, **kwargs) -> "TrackAnnotation":
        annotation = cls.objects.create(**kwargs)
        cls.push(annotation)
        return annotation


class GateCumulativeScore(models.Model):
    """
    Holds the cumulative score accrued up until passing the gate.
    """
    contestant = models.ForeignKey("Contestant", on_delete=models.CASCADE)
    gate = models.CharField(max_length=30)
    points = models.FloatField(default=0)

    class Meta:
        unique_together = ("contestant", "gate")


class ActualGateTime(models.Model):
    """
    The actual passing time for a specific date for a contestant.
    """
    contestant = models.ForeignKey("Contestant", on_delete=models.CASCADE)
    gate = models.CharField(max_length=30)
    time = models.DateTimeField()

    class Meta:
        unique_together = ("contestant", "gate")
