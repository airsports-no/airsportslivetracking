from django.db import migrations

# Same field list migration 0173 renamed to legacy_* - reused here to drop them for real.
LEGACY_FIELDS = [
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
    "included_fields",
]


class Migration(migrations.Migration):
    """
    Migration C of Phase 2e of the scorecard-system review roadmap. Migration 0173 renamed
    these 27 columns to legacy_* rather than dropping them outright, specifically to keep a
    rollback/verification snapshot while every consumer got reworked onto
    Scorecard.config (see PR that added this migration, and the roadmap doc, for the full
    history). That window has closed - every remaining consumer was reworked in a prior PR
    (models/scorecard_and_gate_score.py, signals.py, serialisers.py, forms.py, admin.py,
    views.py, all 11 default_scorecards/*.py seed files) to stop reading/writing these
    columns entirely. Dropping them for real here.
    """

    dependencies = [
        ("display", "0173_scorecard_config_rename_legacy_columns"),
    ]

    operations = [migrations.RemoveField(model_name="scorecard", name=f"legacy_{field}") for field in LEGACY_FIELDS]
