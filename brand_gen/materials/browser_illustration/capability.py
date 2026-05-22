"""Browser Illustration Capability Plugin.

Represents browser/product-window illustration generative exploration.
"""
from __future__ import annotations

from typing import Any
from brand_gen.materials._registry import MaterialCapability, register

class BrowserIllustrationCapability(MaterialCapability):
    """Capability for browser illustration asset generation."""

    @property
    def material_type(self) -> str:
        return "browser_illustration"

    @property
    def default_model(self) -> str:
        return "recraft-v4"

    @property
    def default_aspect_ratio(self) -> str:
        return "16:9"

    @property
    def prompt_profile(self) -> dict[str, Any]:
        return {
            "material_type": "browser-illustration",
            "batch": "product_interface",
            "job_to_be_done": "Create a browser/product-window illustration where one real workflow or UI proof remains authoritative.",
            "generation_mode": "image",
            "default_aspect_ratio": "16:9",
            "default_model": "recraft-v4",
            "default_render_backend": "native",
            "exact_text_policy": {
                "mode": "deterministic_required_for_exact_visible_copy",
                "deterministic_required_for_exact_copy": True,
                "guidance": "If exact visible copy, numbers, quotes, event details, command text, or UI labels matter, use html/svg/composite/typographic overlay; do not trust native image text."
            },
            "best_aesthetic_capsules": [
                "structural-neo-brutalist-blueprint",
                "friendly-line-flat-wayfinding",
                "soft-dimensional-product-object",
                "calm-product-wireframe-editorial",
                "terminal-cli-proof"
            ],
            "allowed_reference_roles": [
                "product_truth",
                "composition",
                "application",
                "motif"
            ],
            "prompt_skeleton": "Anchor the image on one real product/interface proof, frame it with brand color/mark hierarchy, and use references for crop/application only. Do not redesign the product or invent UI labels.",
            "negative_prompt_failure_bans": [
                "invented dashboard chrome",
                "redrawn product UI",
                "fake nav/buttons",
                "tiny unreadable screenshots",
                "hacker neon unless requested",
                "product truth subordinate to decoration"
            ],
            "review_focus": [
                "real product truth preservation",
                "interface legibility",
                "brand/product balance",
                "reference-role discipline",
                "invented UI risk"
            ],
            "review_rubric_key": "universal",
            "review_rubric_mapping": "universal_axes"
        }

    def build_prompts(self, context: dict[str, Any]) -> dict[str, Any]:
        return {}

    def validate_artifact(self, artifact_path: str, context: dict[str, Any]) -> list[str]:
        return []

# Register the capability
register(BrowserIllustrationCapability())
