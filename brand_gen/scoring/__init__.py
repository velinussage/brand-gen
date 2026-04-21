"""brand-gen scoring subsystem.

v1 (this iteration) ships:
- rubric_registry: universal axes + material overlays + disqualifiers (inline Python dict)
- (M2) signatures + program: DSPy scorer
- (M2) config: LM configuration with caching adapter
- (M3) dataset: disagreement logging + fcntl-safe append + sha256 partition
- (M3) calibration: weighted Cohen's kappa + raw agreement %

v2 adds GEPA optimization, full calibration stats, CI gates, user self-kappa protocol.
See docs/plans/2026-04-20-dspy-gepa-scoring-plan-v3.md.
"""
from .rubric_registry import (
    RUBRIC_VERSION,
    UNIVERSAL_AXES,
    MATERIAL_OVERLAYS,
    axes_for,
    disqualifier_for,
    material_rubric_key,
    to_markdown,
    to_json_dict,
)

__all__ = [
    "RUBRIC_VERSION",
    "UNIVERSAL_AXES",
    "MATERIAL_OVERLAYS",
    "axes_for",
    "disqualifier_for",
    "material_rubric_key",
    "to_markdown",
    "to_json_dict",
]
