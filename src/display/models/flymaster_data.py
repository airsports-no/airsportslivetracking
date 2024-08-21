from django.db import models


class FlymasterData(models.Model):
    identifier = models.TextField()
    timestamp = models.DateTimeField()
    data = models.TextField()
