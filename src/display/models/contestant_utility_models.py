from django.db import models

from display.fields.my_pickled_object_field import MyPickledObjectField


class ContestantUploadedTrack(models.Model):
    """
    Store a gps track that has been manually uploaded through the API or GUI. They can only be one of these for a
    contestant, and if this is present it will be preferred over anything received through traccar.
    """

    contestant = models.OneToOneField("Contestant", on_delete=models.CASCADE)
    track = MyPickledObjectField(default=list, help_text="List of traccar position reports (Dict)")


class ContestantReceivedPosition(models.Model):
    """
    Represents a position received from traccar. Includes timestamps that can be used to calculate processing
    statistics.
    """

    contestant = models.ForeignKey("Contestant", on_delete=models.CASCADE)

    time = models.DateTimeField()
    latitude = models.FloatField()
    longitude = models.FloatField()
    altitude = models.FloatField(default=0)
    speed = models.FloatField(default=0)
    course = models.FloatField(default=0)

    battery_level = models.FloatField(default=0)
    position_id = models.IntegerField(default=0)
    device_id = models.TextField(default="unknown")
    progress = models.FloatField(default=0)

    interpolated = models.BooleanField(default=False)
    processor_received_time = models.DateTimeField(blank=True, null=True)
    calculator_received_time = models.DateTimeField(blank=True, null=True)
    websocket_transmitted_time = models.DateTimeField(blank=True, null=True)
    server_time = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("time",)
        indexes = [models.Index(fields=["contestant", "time"], name="contestant_time_index")]

    def to_traccar(self, device_id: str, index: int) -> dict:
        return {
            "deviceId": device_id,
            "id": index,
            "latitude": float(self.latitude),
            "longitude": float(self.longitude),
            "altitude": self.latitude,
            "attributes": {"batteryLevel": self.battery_level},
            "speed": self.speed,
            "course": self.course,
            "device_time": self.time,
        }
