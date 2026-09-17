import datetime

from django.db.models import F

from display.models import (
    ActualGateTime,
    AdministrativePenalty,
    GateCumulativeScore,
    ScoreLogEntry,
    TrackAnnotation,
)
from display.models.scoring_models import ANOMALY
from display.utilities.gate_definitions import (
    FINISHPOINT,
    INTERMEDIARY_FINISHPOINT,
    INTERMEDIARY_STARTINGPOINT,
    STARTINGPOINT,
)


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

    @classmethod
    def remove_score_log_entry(cls, entry: ScoreLogEntry) -> None:
        """
        Deletes a single ScoreLogEntry and reverses its effect on the contestant's score,
        gate-cumulative-score records, and (if it was the contestant's last recorded gate)
        ContestantTrack's own last-gate/state fields. Shared by the classic
        contestant_remove_score_item view and ContestantViewSet.remove_score_log_entry (REST) -
        the gate-ordering/cumulative-score bookkeping below is fiddly enough that it should only
        be maintained in one place.
        """
        from websocket_channels import WebsocketFacade

        contestant = entry.contestant
        contestant.contestanttrack.update_score(contestant.contestanttrack.score - entry.points)

        # Note: TrackAnnotation has on_delete=models.CASCADE, but we explicitly delete to be certain and push updates.
        annotation = TrackAnnotation.objects.filter(score_log_entry=entry).first()
        gate_type = annotation.gate_type if annotation else None
        TrackAnnotation.objects.filter(score_log_entry=entry).delete()

        if entry.gate:
            # We only delete the actual gate time and cumulative score if this is the only entry for this gate
            if not ScoreLogEntry.objects.filter(contestant=contestant, gate=entry.gate).exclude(pk=entry.pk).exists():
                ActualGateTime.objects.filter(contestant=contestant, gate=entry.gate).delete()
                GateCumulativeScore.objects.filter(contestant=contestant, gate=entry.gate).delete()

                # Update ContestantTrack if it was the last gate
                ct = contestant.contestanttrack
                if ct.last_gate == entry.gate:
                    previous_entry = (
                        ScoreLogEntry.objects.filter(contestant=contestant).exclude(pk=entry.pk).order_by("-time").first()
                    )
                    if previous_entry:
                        ct.last_gate = previous_entry.gate
                        if previous_entry.planned and previous_entry.actual:
                            ct.last_gate_time_offset = (previous_entry.actual - previous_entry.planned).total_seconds()
                        else:
                            ct.last_gate_time_offset = 0
                    else:
                        ct.last_gate = ""
                        ct.last_gate_time_offset = 0

                    # Revert start/finish point flags if applicable
                    if gate_type in [FINISHPOINT, INTERMEDIARY_FINISHPOINT]:
                        ct.passed_finish_gate = False
                        ct.current_state = "Flying"
                    elif gate_type in [STARTINGPOINT, INTERMEDIARY_STARTINGPOINT]:
                        ct.passed_starting_gate = False
                        ct.current_state = "Waiting..."

                    ct.save()
            else:
                # Otherwise just update the cumulative score
                GateCumulativeScore.objects.filter(contestant=contestant, gate=entry.gate).update(
                    points=F("points") - entry.points
                )

            # Update subsequent GateCumulativeScore records if they are intended to be cumulative
            route = contestant.navigation_task.route
            ordered_gate_names = (
                [g.name for g in route.takeoff_gates]
                + [g.name for g in route.waypoints if not getattr(g, "on_curved_segment", False)]
                + [g.name for g in route.landing_gates]
            )
            try:
                gate_index = ordered_gate_names.index(entry.gate)
                subsequent_gates = ordered_gate_names[gate_index + 1 :]
                if subsequent_gates:
                    GateCumulativeScore.objects.filter(contestant=contestant, gate__in=subsequent_gates).update(
                        points=F("points") - entry.points
                    )
            except ValueError:
                # Gate name not in the ordered list (e.g. custom/anomaly gate)
                pass

        entry.delete()

        # Increment score_version to invalidate score_data ETags without affecting track ETags
        type(contestant).objects.filter(pk=contestant.pk).update(score_version=F("score_version") + 1)

        # Push the updated data so that it is reflected on the contest track
        wf = WebsocketFacade()
        wf.transmit_score_log_entry(contestant)
        wf.transmit_annotations(contestant)
        wf.transmit_basic_information(contestant)
        wf.transmit_gate_score_entry(contestant)
