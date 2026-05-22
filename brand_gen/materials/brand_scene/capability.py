"""Brand Scene Capability Plugin.

Represents still image illustrated brand world/scene asset capability.
"""
from __future__ import annotations

from typing import Any
from brand_gen.materials._registry import MaterialCapability, register

class BrandSceneCapability(MaterialCapability):
    """Capability for brand scene/illustrated brand world asset generation."""

    @property
    def material_type(self) -> str:
        return "brand_scene"

    @property
    def default_model(self) -> str:
        return "gpt-image-2"

    @property
    def default_aspect_ratio(self) -> str:
        return "16:9"

    @property
    def default_render_backend(self) -> str:
        return "native"

    @property
    def prompt_profile(self) -> dict[str, Any]:
        return {
            "material_type": "illustrated-brand-world",
            "batch": "editorial_content",
            "job_to_be_done": "Create an illustrated brand world that implies the product/work process, not just mood.",
            "generation_mode": "image",
            "default_aspect_ratio": "16:9",
            "default_model": "gpt-image-2",
            "default_render_backend": "native",
            "exact_text_policy": {
                "mode": "deterministic_required_for_exact_visible_copy",
                "deterministic_required_for_exact_copy": True,
                "guidance": "If exact visible copy, numbers, quotes, event details, command text, or UI labels matter, use html/svg/composite/typographic overlay; do not trust native image text."
            },
            "best_aesthetic_capsules": [
                "friendly-line-flat-wayfinding",
                "tactile-human-collage",
                "pastoral-storybook-animation",
                "archival-civic-documentary",
                "warm-editorial-system-illustration"
            ],
            "allowed_reference_roles": [
                "composition",
                "application",
                "product_truth",
                "motif"
            ],
            "prompt_skeleton": "Use an editorial information hierarchy: one headline/quote/data/process payload, one supporting visual device, clear margins, and brand mark secondary. Exact text belongs in HTML/SVG/composite.",
            "negative_prompt_failure_bans": [
                "invented quotes/data/event details",
                "gibberish body text",
                "overcrowded type",
                "fake charts",
                "logo-dominant layout",
                "decorative filler icons"
            ],
            "review_focus": [
                "information hierarchy",
                "truthfulness of copy/data",
                "thumbnail readability",
                "brand restraint",
                "exact-text strategy"
            ],
            "review_rubric_key": "illustrated-brand-world",
            "review_rubric_mapping": "material_overlay"
        }

    def build_prompts(self, context: dict[str, Any]) -> dict[str, Any]:
        return {}

    def validate_artifact(self, artifact_path: str, context: dict[str, Any]) -> list[str]:
        return []

# Register the capability
register(BrandSceneCapability())
