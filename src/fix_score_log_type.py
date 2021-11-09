from display.models import ScoreLogEntry, ANOMALY

ScoreLogEntry.objects.filter(points__gt=0).update(type=ANOMALY)