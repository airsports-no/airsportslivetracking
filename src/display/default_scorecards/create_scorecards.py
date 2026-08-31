from display.default_scorecards import (
    default_scorecard_airsport_challenge,
    default_scorecard_airsports,
    default_scorecard_fai_air_rally_2020,
    default_scorecard_fai_anr_2017,
    default_scorecard_fai_anr_2022,
    default_scorecard_fai_precision_2020,
    default_scorecard_fai_precision_2020_without_procedure_turn,
    default_scorecard_landing,
    default_scorecard_nlf_precision_2020,
    default_scorecard_nordic_asr,
    default_scorecard_poker_run,
)
from display.models import Scorecard


def _seed_cima_runtime_defaults():
    # A bulk queryset .update() (the previous implementation here) skips pre_save/post_save
    # entirely - besides bypassing bump_gate_scorecard_cache_version (display/signals.py), it
    # relies on every key being a real column, which stopped being true once Phase 2 of the
    # scorecard-system review roadmap moved these fields into Scorecard.config (see
    # ConfigField in models/scorecard_and_gate_score.py): QuerySet.update() resolves each
    # kwarg via a raw model._meta.get_field() lookup with no property/descriptor
    # special-casing at all, so it would raise FieldDoesNotExist for every one of these.
    # Per-instance setattr + save() routes through the ConfigField property setters (so it
    # still works) and fires the normal signals (so it no longer silently skips them either).
    for card in Scorecard.objects.filter(shortcut_name="FAI Precision"):
        card.compulsory_timing_tolerance_seconds = 10
        card.maximum_task_duration_minutes = None
        card.maximum_task_duration_penalty = 100
        card.fuel_deadline_penalty = 100
        card.anr_route_to_sp_penalty = 200
        card.anr_route_from_fp_penalty = 200
        card.duration_normalization_policy = ""
        card.duration_residual_fuel_required = False
        card.circle_radius_min_m = 200
        card.circle_radius_max_m = 750
        card.save()


def create_scorecards():
    default_scorecard_fai_precision_2020.get_default_scorecard()
    default_scorecard_fai_precision_2020_without_procedure_turn.get_default_scorecard()
    default_scorecard_fai_air_rally_2020.get_default_scorecard()
    default_scorecard_fai_anr_2017.get_default_scorecard()
    default_scorecard_fai_anr_2022.get_default_scorecard()
    default_scorecard_nlf_precision_2020.get_default_scorecard()
    default_scorecard_poker_run.get_default_scorecard()
    default_scorecard_landing.get_default_scorecard()
    default_scorecard_airsports.get_default_scorecard()
    default_scorecard_airsport_challenge.get_default_scorecard()
    default_scorecard_nordic_asr.get_default_scorecard()
    _seed_cima_runtime_defaults()
