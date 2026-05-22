"""Logo Capability Plugin.

Represents logo identity exploration asset capability.
"""
from __future__ import annotations

from typing import Any
from brand_gen.materials._registry import MaterialCapability, register

class LogoCapability(MaterialCapability):
    """Capability for logo asset generation."""

    @property
    def material_type(self) -> str:
        return "logo"

    @property
    def default_model(self) -> str:
        return "recraft-v4"

    @property
    def default_aspect_ratio(self) -> str:
        return "1:1"

    @property
    def default_render_backend(self) -> str:
        return "vector/composite-preferred-for-final-assets"

    @property
    def prompt_profile(self) -> dict[str, Any]:
        return {
            "material_type": "logo",
            "batch": "brand_system",
            "job_to_be_done": "Explore logo directions with strict geometry and review caveats; do not imply final approval automatically.",
            "generation_mode": "image",
            "default_aspect_ratio": "1:1",
            "default_model": "recraft-v4",
            "default_render_backend": "vector/composite-preferred-for-final-assets",
            "exact_text_policy": {
                "mode": "textless_or_reviewed_vector",
                "deterministic_required_for_exact_copy": True,
                "guidance": "Prefer textless/vector identity exploration. Wordmarks/lockups require deterministic vector/composite handling and human review."
            },
            "best_aesthetic_capsules": [
                "brand-system-vector-kit",
                "friendly-line-flat-wayfinding",
                "heritage-bold-minimal-packaging",
                "screenprinted-proof-poster",
                "warm-editorial-system-illustration"
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
register(LogoCapability())
