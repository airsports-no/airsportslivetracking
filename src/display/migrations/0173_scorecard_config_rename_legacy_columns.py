from django.db import migrations

# Same 26 fields as migration 0172's SCORECARD_CONFIG_FIELDS, plus included_fields (which
# moves to a hand-written property rather than a ConfigField, but is renamed out of the way
# the same way - see Scorecard.included_fields in models/scorecard_and_gate_score.py).
RENAMED_FIELDS = [
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
    Migration C of Phase 2 of the scorecard-system review roadmap. Django doesn't allow a
    model field and a same-named property to coexist, so the moved columns have to be renamed
    out of the way in the same deploy that adds the config-backed @property/ConfigField
    accessors on Scorecard (see models/scorecard_and_gate_score.py) - there's no soft
    dual-write window with this approach. Renaming rather than dropping keeps a
    rollback/verification snapshot: legacy_* columns still hold the pre-migration values, and
    the GateScore table is left as-is (nothing renamed on it - see that model's docstring),
    both slated for real removal in a later, separate cleanup migration once this has been
    live for a while.

    The two confirmed-dead fields (below_minimum_altitude_penalty,
    below_minimum_altitude_maximum_penalty) are dropped outright here rather than renamed -
    they were never migrated into config by 0172, and have zero read sites anywhere.
    """

    dependencies = [
        ("display", "0172_scorecard_populate_config"),
    ]

    operations = [
        migrations.RemoveField(model_name="scorecard", name="below_minimum_altitude_penalty"),
        migrations.RemoveField(model_name="scorecard", name="below_minimum_altitude_maximum_penalty"),
    ] + [
        migrations.RenameField(model_name="scorecard", old_name=field, new_name=f"legacy_{field}")
        for field in RENAMED_FIELDS
    ]
