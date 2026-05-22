"""Video Shot Capability Plugin.

Represents motion/video campaign shot capability.
"""
from __future__ import annotations

from typing import Any
from brand_gen.materials._registry import MaterialCapability, register

class VideoShotCapability(MaterialCapability):
    """Capability for video/motion shot asset generation."""

    @property
    def material_type(self) -> str:
        return "video_shot"

    @property
    def default_model(self) -> str:
        return "minimax"

    @property
    def default_aspect_ratio(self) -> str:
        return "16:9"

    @property
    def generation_mode(self) -> str:
        return "video"

    @property
    def default_render_backend(self) -> str:
        return "native-video-with-external-text-overlay"

    @property
    def prompt_profile(self) -> dict[str, Any]:
        return {
            "material_type": "video_shot",
            "batch": "motion_video",
            "job_to_be_done": "Create a feature animation whose opening beat is a product/workflow/capability state, not a logo card; use one motion idea, a readable transformation, and a confident branded final hold.",
            "generation_mode": "video",
            "default_aspect_ratio": "16:9",
            "default_model": "minimax",
            "default_render_backend": "native-video-with-external-text-overlay",
            "exact_text_policy": {
                "mode": "external_caption_or_final_hold_text",
                "deterministic_required_for_exact_copy": True,
                "guidance": "Keep exact titles/captions outside the video model or on deterministic overlays; native video text should be minimal/non-critical."
            },
            "best_aesthetic_capsules": [
                "kinetic-brand-motion-system",
                "kinetic-typography-campaign",
                "animated-infographic-data-story",
                "controlled-retro-computing-interface",
                "terminal-cli-proof"
            ],
            "allowed_reference_roles": [
                "motion",
                "composition",
                "application",
                "product_truth"
            ],
            "prompt_skeleton": "Use a three-beat motion contract: (1) start on the product/workflow/capability artifact or source still, (2) transform, route, or reveal the value, and (3) settle into a branded final hold with the logo only as a small provenance mark when needed. Name the reveal mechanic, camera/framing, duration, and final product/workflow state. Avoid stock intro effects and do not use a logo-first opener.",
            "negative_prompt_failure_bans": [
                "particle explosions",
                "logo distortion/melting",
                "random camera spins",
                "too many transitions",
                "unreadable motion text",
                "stock intro template look",
                "logo-first opener or centered mark reveal unless the material type is logo-animation",
                "oversized logo as the motion driver"
            ],
            "review_focus": [
                "single motion idea",
                "pacing and final hold",
                "product/workflow value before brand mark",
                "text/caption strategy",
                "effect restraint",
                "logo appears only as final provenance when needed"
            ],
            "review_rubric_key": "universal",
            "review_rubric_mapping": "universal_axes"
        }

    def build_prompts(self, context: dict[str, Any]) -> dict[str, Any]:
        return {}

    def validate_artifact(self, artifact_path: str, context: dict[str, Any]) -> list[str]:
        return []

# Register the capability
register(VideoShotCapability())
