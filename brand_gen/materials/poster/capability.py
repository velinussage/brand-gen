"""Poster Capability Plugin.

Represents still image physical or digital poster asset capability.
"""
from __future__ import annotations

from typing import Any
from brand_gen.materials._registry import MaterialCapability, register

class PosterCapability(MaterialCapability):
    """Capability for poster asset generation."""

    @property
    def material_type(self) -> str:
        return "poster"

    @property
    def default_model(self) -> str:
        return "recraft-v4"

    @property
    def default_aspect_ratio(self) -> str:
        return "4:5"

    @property
    def prompt_profile(self) -> dict[str, Any]:
        return {
            "material_type": "poster",
            "batch": "brand_system",
            "job_to_be_done": "Create a poster that extends the brand identity system with deployable, consistent geometry.",
            "generation_mode": "image",
            "default_aspect_ratio": "4:5",
            "default_model": "recraft-v4",
            "default_render_backend": "native",
            "exact_text_policy": {
                "mode": "native_text_minimal",
                "deterministic_required_for_exact_copy": False,
                "guidance": "Native generation may include abstract marks or non-critical labels only; use deterministic rendering if copy becomes part of the acceptance criteria."
            },
            "best_aesthetic_capsules": [
                "heritage-bold-minimal-packaging",
                "screenprinted-proof-poster",
                "kinetic-typography-campaign",
                "tactile-human-collage",
                "brand-system-vector-kit"
            ],
            "allowed_reference_roles": [
                "motif",
                "application",
                "composition"
            ],
            "prompt_skeleton": "Use a specimen/system layout: one geometry rule, repeated variants, consistent stroke/fill, approved palette, and clear deployability. Generated marks are explorations until reviewed.",
            "negative_prompt_failure_bans": [
                "random unrelated symbols",
                "glossy app-icon bevels",
                "fake final trademark claim",
                "inconsistent stroke weights",
                "mascot dump",
                "gradient blob identity"
            ],
            "review_focus": [
                "geometry consistency",
                "deployability",
                "brand-system coherence",
                "identity approval caveat",
                "motif overproduction risk"
            ],
            "review_rubric_key": "universal",
            "review_rubric_mapping": "universal_axes"
        }

    def build_prompts(self, context: dict[str, Any]) -> dict[str, Any]:
        return {}

    def validate_artifact(self, artifact_path: str, context: dict[str, Any]) -> list[str]:
        return []

# Register the capability
register(PosterCapability())
