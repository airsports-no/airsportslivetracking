import logging

from django.db import migrations, transaction

logger = logging.getLogger(__name__)

# The 26 scoring-parameter fields moving from real columns into Scorecard.config (see the
# Phase 2 scorecard-system roadmap doc, saved outside the repo, for the full field inventory
# that justified this list). below_minimum_altitude_penalty and
# below_minimum_altitude_maximum_penalty are deliberately excluded - confirmed fully dead
# (their own help_text said "not applied automatically", and no read site exists anywhere in
# the codebase), so they are dropped rather than migrated.
SCORECARD_CONFIG_FIELDS = [
    "backtracking_penalty",
    "backtracking_bearing_difference",
    "backtracking_grace_time_seconds",
    "backtracking_maximum_penalty",
    "prohibited_zone_penalty",
    "prohibited_zone_grace_time",
    "prohibited_zone_maximum",
    "penalty_zone_grace_time",
    "penalty_zone_penalty_per_second",
    "penalty_zone_maximum",
    "corridor_grace_time",
    "corridor_outside_penalty",
    "corridor_maximum_penalty",
    "corridor_maximum_penalty_is_per_leg",
    "anr_route_to_sp_penalty",
    "anr_route_from_fp_penalty",
    "compulsory_timing_tolerance_seconds",
    "maximum_task_duration_minutes",
    "maximum_task_duration_penalty",
    "fuel_deadline_penalty",
    "duration_normalization_policy",
    "duration_residual_fuel_required",
    "circle_radius_min_m",
    "circle_radius_max_m",
    "speed_keeping_tolerance_kt",
    "speed_keeping_penalty_per_kt",
]

# GateScore.bad_course_crossing_penalty is dropped for the same reason - zero read sites.
GATE_SCORE_FIELDS = [
    "extended_gate_width",
    "bad_crossing_extended_gate_penalty",
    "graceperiod_before",
    "graceperiod_after",
    "maximum_penalty",
    "penalty_per_second",
    "missed_penalty",
    "missed_procedure_turn_penalty",
    "backtracking_after_steep_gate_grace_period_seconds",
    "backtracking_before_gate_grace_period_nm",
    "backtracking_after_gate_grace_period_nm",
]


def populate_config(apps, schema_editor):
    Scorecard = apps.get_model("display", "Scorecard")

    succeeded = 0
    failed = []
    for scorecard in Scorecard.objects.all().iterator():
        try:
            # Wrapped in its own savepoint: RunPython runs inside the overall migration
            # transaction, and on backends that abort the whole transaction on the first
            # error (e.g. PostgreSQL), an unwrapped failure would make every subsequent
            # iteration fail too - not because that scorecard has a problem, but because the
            # connection is stuck in an aborted-transaction state. A per-row savepoint keeps
            # one bad row's rollback isolated from the rest of the backfill.
            with transaction.atomic():
                config = {field: getattr(scorecard, field) for field in SCORECARD_CONFIG_FIELDS}
                config["included_fields"] = scorecard.included_fields
                gates = {}
                for gate in scorecard.gatescore_set.all():
                    gate_config = {field: getattr(gate, field) for field in GATE_SCORE_FIELDS}
                    gate_config["included_fields"] = gate.included_fields
                    gates[gate.gate_type] = gate_config
                config["gates"] = gates
                scorecard.config = config
                scorecard.save(update_fields=["config"])
            succeeded += 1
        except Exception:
            failed.append(scorecard.pk)
            logger.exception("Failed to populate config for Scorecard pk=%s", scorecard.pk)

    logger.info(
        "Scorecard config backfill: %d succeeded, %d failed%s",
        succeeded,
        len(failed),
        f" (pks: {failed})" if failed else "",
    )
    if failed:
        raise RuntimeError(
            f"Scorecard config backfill failed for {len(failed)} scorecard(s): {failed}. "
            "See logs above for individual tracebacks."
        )


def clear_config(apps, schema_editor):
    Scorecard = apps.get_model("display", "Scorecard")
    Scorecard.objects.update(config={})


class Migration(migrations.Migration):
    """
    Migration B of Phase 2 of the scorecard-system review roadmap: populate the new
    Scorecard.config JSON blob (added, empty, in 0171) from the current relational columns
    plus each scorecard's GateScore rows. The old columns and the GateScore table are left
    completely untouched here - both are only renamed/stop-being-written-to in migration 0173,
    once this has copied everything over and this migration's failure mode (raise, don't
    silently swallow per-row errors) has had a chance to catch any surprises first.
    """

    dependencies = [
        ("display", "0171_scorecard_add_config_field"),
    ]

    operations = [
        migrations.RunPython(populate_config, clear_config),
    ]
