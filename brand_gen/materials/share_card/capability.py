"""Share Card Capability Plugin.

Represents the HTML/CSS/JS rendering capability for campaign share cards.
"""
from __future__ import annotations

from typing import Any
from brand_gen.materials._registry import MaterialCapability, register

class ShareCardCapability(MaterialCapability):
    """Capability for HTML/CSS/JS rendered share cards."""

    @property
    def material_type(self) -> str:
        return "share_card"

    @property
    def default_model(self) -> str:
        return "html:chromium"

    @property
    def default_aspect_ratio(self) -> str:
        return "2:1"

    @property
    def default_render_backend(self) -> str:
        return "html"

    @property
    def prompt_profile(self) -> dict[str, Any]:
        return {
            "material_type": "share_card",
            "batch": "core_proof_social",
            "job_to_be_done": "Create a high-signal share card with deterministic copy handling.",
            "generation_mode": "image",
            "default_aspect_ratio": "2:1",
            "default_model": "html:chromium",
            "default_render_backend": "html",
            "exact_text_policy": {
                "mode": "deterministic_required_for_exact_visible_copy",
                "deterministic_required_for_exact_copy": True,
                "guidance": "Always render using HTML/CSS/JS to guarantee exact text, brand colors, and layouts."
            },
            "best_aesthetic_capsules": [
                "screenprinted-proof-poster",
                "calm-product-wireframe-editorial",
                "editorial-content-card",
                "terminal-cli-proof"
            ],
            "allowed_reference_roles": [
                "composition",
                "application",
                "product_truth",
                "motif"
            ],
            "prompt_skeleton": "HTML/CSS rendering layout spec.",
            "negative_prompt_failure_bans": [
                "generic AI orb/node diagram",
                "DAO/governance theater unless requested",
                "gibberish or pseudo-text"
            ],
            "review_focus": [
                "text legibility",
                "brand recognition",
                "design restraint"
            ],
            "review_rubric_key": "universal",
            "review_rubric_mapping": "universal_axes"
        }

    def build_prompts(self, context: dict[str, Any]) -> dict[str, Any]:
        return {}

    def validate_artifact(self, artifact_path: str, context: dict[str, Any]) -> list[str]:
        return []

# Register the capability
register(ShareCardCapability())
