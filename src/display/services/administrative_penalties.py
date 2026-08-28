import datetime

from django.db.models import F

from display.models import AdministrativePenalty, GateCumulativeScore, ScoreLogEntry, TrackAnnotation
from display.models.scoring_models import ANOMALY


class AdministrativePenaltyService:
    @classmethod
    def apply_contestant_penalty(
        cls,
        *,
        contestant,
        points: float,
        reason: str,
        gate: str = "ADMIN",
        category: str = AdministrativePenalty.CATEGORY_QUARANTINE,
        time: datetime.datetime | None = None,
        annotation: bool = True,
        annotation_type: str = ANOMALY,
        actor=None,
    ) -> ScoreLogEntry:
        if time is None:
            time = datetime.datetime.now(datetime.timezone.utc)
        if time.tzinfo is None:
            time = time.replace(tzinfo=datetime.timezone.utc)

        gate_score, _ = GateCumulativeScore.objects.get_or_create(gate=gate, contestant=contestant)
        gate_score.points += points
        gate_score.save(update_fields=["points"])

        entry = ScoreLogEntry.create_and_push(
            contestant=contestant,
            time=time,
            gate=gate,
            type=annotation_type,
            message=reason,
            points=points,
            planned=None,
            actual=None,
            offset_string="",
            string=f"{gate}: {float(points)} points {reason}",
            times_string="",
        )

        AdministrativePenalty.objects.create(
            score_log_entry=entry,
            contestant=contestant,
            actor=actor,
            category=category,
            reason=reason,
        )

        if annotation:
            location = contestant.navigation_task.route.get_location()
            latitude = location[0] if location else 0.0
            longitude = location[1] if location else 0.0
            TrackAnnotation.create_and_push(
                contestant=contestant,
                latitude=latitude,
                longitude=longitude,
                message=entry.string,
                type=annotation_type,
                gate=gate,
                gate_type="tp",
                time=time,
                score_log_entry=entry,
            )

        contestant.contestanttrack.increment_score(points)
        type(contestant).objects.filter(pk=contestant.pk).update(score_version=F("score_version") + 1)

        return entry
