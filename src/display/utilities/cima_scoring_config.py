"""
Typed, read-time adapter over the newer CIMA-subtype scoring fields on Scorecard (Phase 1 of the
scorecard-system review roadmap - see the roadmap doc for full context, saved outside the repo).

These ~12 fields (fuel_deadline_penalty, circle_radius_min_m/max_m, etc.) are real Scorecard
columns, but were being read via getattr(scorecard, "field_name", default) or default at every
call site - stringly-typed, and the `or default` idiom silently replaces a legitimately
configured falsy value (0, False, "") with the default, since none of these columns are actually
nullable (Django backfills a real default on every existing row when such a column is added, so
the getattr fallback was always dead code - only the `or` collapse was live). Concretely:
fuel_deadline_penalty=0 (an organizer disabling the penalty) silently became 100 at scoring time.

CimaScoringConfig.from_scorecard() replaces every such call site with a single, correctly-typed
read: no more falsy-collapse bug, one canonical field name instead of a hand-typed string at each
site, and (per the roadmap) the same object is meant to eventually be the single source both the
scoring path (calculators) and the display path (task_information.py) read from - closing the
"same field, 4 possible sources, no documented precedence" gap identified as pain point #2.
task_information.py itself is NOT switched over in this phase: it currently prefers
NavigationTask.task_config over the scorecard column for several of these fields (a documented,
evidenced divergence from what the calculators actually score with - see the roadmap), and
deciding whether task_config should ever win for scoring, or whether its involvement here is
itself the bug to remove, is a product decision this phase deliberately doesn't make.

No storage change: this is a read-time adapter over the existing Scorecard columns, not a new
column or a migration. Scorecard/GateScore's dozens of other fields (backtracking, corridor,
gate-timing, ...) are unaffected - most of those are already read as plain typed attributes
(self.scorecard.corridor_grace_time etc.), not through this stringly-typed pattern, so they're
out of scope for this phase.

Also deliberately left alone: TaskCompiler._calculate_source_signature (task_compiler.py)
builds a cache-invalidation tuple from the same field names via getattr(scorecard, "field",
None) - but it isn't the buggy pattern (no `or default` collapse, None is used correctly as a
sentinel), and scorecard can genuinely be None there (a NavigationTask without one yet), which
CimaScoringConfig.from_scorecard() doesn't guard against. Different subsystem (route-compilation
caching, not scoring), not exhibiting the bug this phase targets.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from display.models import Scorecard


@dataclass(frozen=True)
class CimaScoringConfig:
    compulsory_timing_tolerance_seconds: int = 10
    maximum_task_duration_minutes: Optional[int] = None
    maximum_task_duration_penalty: float = 100
    fuel_deadline_penalty: float = 100
    duration_normalization_policy: str = ""
    duration_residual_fuel_required: bool = False
    circle_radius_min_m: float = 200
    circle_radius_max_m: float = 750
    speed_keeping_tolerance_kt: float = 5
    speed_keeping_penalty_per_kt: float = 1
    anr_route_to_sp_penalty: float = 200
    anr_route_from_fp_penalty: float = 200

    @classmethod
    def from_scorecard(cls, scorecard: "Scorecard") -> "CimaScoringConfig":
        return cls(
            compulsory_timing_tolerance_seconds=scorecard.compulsory_timing_tolerance_seconds,
            maximum_task_duration_minutes=scorecard.maximum_task_duration_minutes,
            maximum_task_duration_penalty=scorecard.maximum_task_duration_penalty,
            fuel_deadline_penalty=scorecard.fuel_deadline_penalty,
            duration_normalization_policy=scorecard.duration_normalization_policy,
            duration_residual_fuel_required=scorecard.duration_residual_fuel_required,
            circle_radius_min_m=scorecard.circle_radius_min_m,
            circle_radius_max_m=scorecard.circle_radius_max_m,
            speed_keeping_tolerance_kt=scorecard.speed_keeping_tolerance_kt,
            speed_keeping_penalty_per_kt=scorecard.speed_keeping_penalty_per_kt,
            anr_route_to_sp_penalty=scorecard.anr_route_to_sp_penalty,
            anr_route_from_fp_penalty=scorecard.anr_route_from_fp_penalty,
        )
