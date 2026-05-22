"""Banner Capability Plugin.

Represents wide advertising or product banner capability.
"""
from __future__ import annotations

from typing import Any
from brand_gen.materials._registry import MaterialCapability, register

class BannerCapability(MaterialCapability):
    """Capability for banner asset generation."""

    @property
    def material_type(self) -> str:
        return "banner"

    @property
    def default_model(self) -> str:
        return "recraft-v4"

    @property
    def default_aspect_ratio(self) -> str:
        return "16:9"

    @property
    def default_render_backend(self) -> str:
        return "html-preferred-for-exact-copy"

    @property
    def prompt_profile(self) -> dict[str, Any]:
        return {
            "material_type": "banner",
            "batch": "product_interface",
            "job_to_be_done": "Create a wide brand/product banner that supports external page or campaign copy without becoming a full hero page mockup.",
            "generation_mode": "image",
            "default_aspect_ratio": "16:9",
            "default_model": "recraft-v4",
            "default_render_backend": "html-preferred-for-exact-copy",
            "exact_text_policy": {
                "mode": "deterministic_required_for_exact_visible_copy",
                "deterministic_required_for_exact_copy": True,
                "guidance": "If exact visible copy, numbers, quotes, event details, command text, or UI labels matter, use html/svg/composite/typographic overlay; do not trust native image text."
            },
            "best_aesthetic_capsules": [
                "calm-product-wireframe-editorial",
                "soft-dimensional-product-object",
                "structural-neo-brutalist-blueprint",
                "terminal-cli-proof"
            ],
            "allowed_reference_roles": [
                "composition",
                "application",
                "product_truth",
                "motif"
            ],
            "prompt_skeleton": "Compose a wide banner art plate with one product-grounded visual premise, strong crop, and safe negative space for external copy. Do not include nav, CTA, full webpage chrome, or native exact headline text.",
            "negative_prompt_failure_bans": [
                "full landing page mockup",
                "native headline/CTA text",
                "fake product screenshots",
                "overcrowded hero layout",
                "generic stock SaaS gradients"
            ],
            "review_focus": [
                "wide-crop usability",
                "external-copy safe space",
                "single product premise",
                "brand palette control",
                "no fake page chrome"
            ],
            "review_rubric_key": "universal",
            "review_rubric_mapping": "universal_axes"
        }

    def build_prompts(self, context: dict[str, Any]) -> dict[str, Any]:
        return {}

    def validate_artifact(self, artifact_path: str, context: dict[str, Any]) -> list[str]:
        return []

# Register the capability
register(BannerCapability())
