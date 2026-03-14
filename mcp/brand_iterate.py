#!/usr/bin/env python3
"""
Brand iteration wrapper for image and motion materials.

Usage:
  brand_iterate.py bootstrap                                Scan existing files into manifest
  brand_iterate.py generate -p "prompt" [opts]             Generate + auto-version + manifest
  brand_iterate.py feedback VERSION --score N [opts]        Record feedback for a version
  brand_iterate.py show [VERSION]                           Show manifest or version detail
  brand_iterate.py compare V1 V2 [V3...]                    Generate HTML comparison board
  brand_iterate.py evolve                                   Analyze prompt patterns from feedback
  brand_iterate.py inspire [CATEGORY]                       Browse / list inspiration references
  brand_iterate.py extract-brand [opts]                     Extract a brand profile from a codebase/site
  brand_iterate.py build-identity [opts]                    Build brand-identity.json and brand-identity.md from a profile
  brand_iterate.py describe-brand [opts]                    Generate reusable brand description prompts
  brand_iterate.py show-identity [opts]                     Show a readable or JSON summary of stored brand identity
  brand_iterate.py show-blackboard [opts]                   Show the shared brand state / blackboard used by the specialist loop
  brand_iterate.py show-workflow-lineage --workflow-id ID   Show decisions, assets, and artifact paths for a workflow
  brand_iterate.py route-request [opts]                     Route a request to the right specialist path before planning or generation
  brand_iterate.py resolve-prompt [opts]                    Show the effective prompt after applying brand guardrails
  brand_iterate.py review-prompt [opts]                     Review + refine a prompt before generation
  brand_iterate.py validate-identity [opts]                 Check whether stored brand memory is complete enough for generation
  brand_iterate.py parse-design-memory [opts]               Parse an existing .design-memory folder into structured brand-gen memory
  brand_iterate.py extract-css-variables [opts]             Extract CSS custom properties from .design-memory, CSS, HTML, or markdown
  brand_iterate.py diff-design-memory [opts]                Compare two .design-memory folders to inspect drift
  brand_iterate.py shotlist [opts]                          Create a product screenshot shot list
  brand_iterate.py capture-product [opts]                   Capture product screenshots with agent-browser
  brand_iterate.py explore-brand [opts]                     Suggest exploratory concept directions, source packs, and prompt seeds
  brand_iterate.py plan-set [opts]                          Establish a coherent material set from translated inspiration + brand truth
  brand_iterate.py validate-brand-fit [opts]                Check whether a material plan or set is clearly branded and product-fit
  brand_iterate.py validate-set [opts]                      Validate set-level coherence, product-fit, and brand-anchor coverage
  brand_iterate.py generate-set [opts]                      Generate only the explicit generateable members of a saved set manifest
  brand_iterate.py ideate-copy [opts]                       Generate headline, slogan, and CTA candidates for branded materials
  brand_iterate.py ideate-messaging [opts]                  Generate messaging angles from brand context and iteration notes
  brand_iterate.py update-messaging [opts]                  Persist approved messaging into the session brand identity
  brand_iterate.py promote-messaging [opts]                 Promote session messaging back to the saved brand identity
  brand_iterate.py show-iteration-memory [opts]             Show the evolving scratchpad of negative examples and copy notes
  brand_iterate.py update-iteration-memory [opts]           Record positive/negative examples or brand/copy notes explicitly
  brand_iterate.py review-brand [opts]                      Build a structured critique/refine packet for a generated or composed artifact
  brand_iterate.py example-sources [opts]                   List or search curated brand example sources
  brand_iterate.py collect-examples [opts]                  Capture curated brand example references into folders
  brand_iterate.py social-specs [FORMAT]                    Show current X / LinkedIn / OG card + feed guidance

Manifest: <BRAND_DIR>/manifest.json
Output:   <BRAND_DIR>/

Environment:
  BRAND_DIR        Override output directory directly
  LOGO_DIR         Legacy compatibility output directory
  SCREENSHOTS_DIR  Base directory; default output becomes $SCREENSHOTS_DIR/brand-materials
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import hashlib
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.append(str(SCRIPTS_DIR))

from load_inspiration_doctrine import (  # type: ignore
    load_component_hints,
    load_principles,
    load_tokens,
    merge_inspiration_doctrine,
)

ENV_CANDIDATES = [REPO_ROOT / ".env", Path.home() / ".claude" / ".env"]
GENERATE_PY = SCRIPT_DIR / "generate.py"
EXTRACT_BRAND_PY = REPO_ROOT / "scripts" / "extract_brand_profile.py"
DESCRIBE_BRAND_PY = REPO_ROOT / "scripts" / "describe_brand_profile.py"
BUILD_IDENTITY_PY = REPO_ROOT / "scripts" / "build_brand_identity.py"
DESIGN_MEMORY_LITE_PY = REPO_ROOT / "scripts" / "design_memory_lite.py"
PRODUCT_SCREENS_PY = REPO_ROOT / "scripts" / "product_screens.py"
EXPLORE_BRAND_PY = REPO_ROOT / "scripts" / "explore_brand_concepts.py"
BUILD_REVIEW_PACKET_PY = REPO_ROOT / "scripts" / "build_brand_review_packet.py"
BRAND_EXAMPLES_PY = REPO_ROOT / "scripts" / "collect_brand_examples.py"
MODELS = json.loads((SCRIPT_DIR / "models.json").read_text())
REFERENCE_ROLE_PACKS_PATH = REPO_ROOT / "data" / "reference_role_packs.json"
PROMPT_REVIEW_RULES_PATH = REPO_ROOT / "data" / "prompt_review_rules.json"
WORKFLOW_ROUTER_RULES_PATH = REPO_ROOT / "data" / "workflow_router_rules.json"

SUPPORTED_IMAGE_EXTS = {".png", ".webp", ".svg", ".jpg", ".jpeg", ".gif", ".bmp"}
SUPPORTED_VIDEO_EXTS = {".mp4", ".mov", ".webm", ".m4v"}
SUPPORTED_MEDIA_EXTS = SUPPORTED_IMAGE_EXTS | SUPPORTED_VIDEO_EXTS

MATERIAL_CONFIG = {
    "logo": {"generation_mode": "image", "default_model": "recraft-v4", "default_aspect_ratio": "1:1"},
    "wordmark": {"generation_mode": "image", "default_model": "ideogram", "default_aspect_ratio": "16:9"},
    "lockup": {"generation_mode": "image", "default_model": "recraft-v4", "default_aspect_ratio": "16:9"},
    "icon": {"generation_mode": "image", "default_model": "recraft-v4", "default_aspect_ratio": "1:1"},
    "banner": {"generation_mode": "image", "default_model": "recraft-v4", "default_aspect_ratio": "16:9"},
    "product-banner": {"generation_mode": "image", "default_model": "recraft-v4", "default_aspect_ratio": "16:9"},
    "landing-hero": {"generation_mode": "image", "default_model": "recraft-v4", "default_aspect_ratio": "16:9"},
    "hero-banner": {"generation_mode": "image", "default_model": "recraft-v4", "default_aspect_ratio": "16:9"},
    "social": {"generation_mode": "image", "default_model": "recraft-v4", "default_aspect_ratio": "1:1"},
    "campaign-poster": {"generation_mode": "image", "default_model": "recraft-v4", "default_aspect_ratio": "4:5"},
    "x-card": {"generation_mode": "image", "default_model": "recraft-v4", "default_aspect_ratio": "2:1"},
    "x-feed": {"generation_mode": "image", "default_model": "recraft-v4", "default_aspect_ratio": "16:9"},
    "x-feed-square": {"generation_mode": "image", "default_model": "recraft-v4", "default_aspect_ratio": "1:1"},
    "x-feed-portrait": {"generation_mode": "image", "default_model": "recraft-v4", "default_aspect_ratio": "4:5"},
    "linkedin-card": {"generation_mode": "image", "default_model": "recraft-v4", "default_aspect_ratio": "1.91:1"},
    "linkedin-feed": {"generation_mode": "image", "default_model": "recraft-v4", "default_aspect_ratio": "1.91:1"},
    "linkedin-feed-square": {"generation_mode": "image", "default_model": "recraft-v4", "default_aspect_ratio": "1:1"},
    "linkedin-feed-portrait": {"generation_mode": "image", "default_model": "recraft-v4", "default_aspect_ratio": "1:1.91"},
    "og-card": {"generation_mode": "image", "default_model": "recraft-v4", "default_aspect_ratio": "1.91:1"},
    "poster": {"generation_mode": "image", "default_model": "recraft-v4", "default_aspect_ratio": "4:5"},
    "event-poster": {"generation_mode": "image", "default_model": "recraft-v4", "default_aspect_ratio": "4:5"},
    "merch-poster": {"generation_mode": "image", "default_model": "recraft-v4", "default_aspect_ratio": "4:5"},
    "product-visual": {"generation_mode": "image", "default_model": "recraft-v4", "default_aspect_ratio": "4:5"},
    "styleframe": {"generation_mode": "image", "default_model": "recraft-v4", "default_aspect_ratio": "16:9"},
    "pattern-system": {"generation_mode": "image", "default_model": "recraft-v4", "default_aspect_ratio": "1:1"},
    "motif-system": {"generation_mode": "image", "default_model": "recraft-v4", "default_aspect_ratio": "1:1"},
    "sticker-family": {"generation_mode": "image", "default_model": "recraft-v4", "default_aspect_ratio": "1:1"},
    "badge-family": {"generation_mode": "image", "default_model": "recraft-v4", "default_aspect_ratio": "1:1"},
    "icon-family": {"generation_mode": "image", "default_model": "recraft-v4", "default_aspect_ratio": "1:1"},
    "storyboard": {"generation_mode": "image", "default_model": "recraft-v4", "default_aspect_ratio": "16:9"},
    "browser-illustration": {"generation_mode": "image", "default_model": "recraft-v4", "default_aspect_ratio": "16:9"},
    "feature-illustration": {"generation_mode": "image", "default_model": "recraft-v4", "default_aspect_ratio": "16:9"},
    "animation": {"generation_mode": "video", "default_model": "kling-v2.6", "default_aspect_ratio": "16:9"},
    "logo-animation": {"generation_mode": "video", "default_model": "kling-v2.6", "default_aspect_ratio": "16:9"},
    "bumper-animation": {"generation_mode": "video", "default_model": "kling-v2.6", "default_aspect_ratio": "16:9"},
    "stinger-animation": {"generation_mode": "video", "default_model": "kling-v2.6", "default_aspect_ratio": "16:9"},
    "feature-animation": {"generation_mode": "video", "default_model": "minimax", "default_aspect_ratio": "16:9"},
    "motion-loop": {"generation_mode": "video", "default_model": "luma", "default_aspect_ratio": "1:1"},
    "gif": {"generation_mode": "video", "default_model": "kling-v2.6", "default_aspect_ratio": "1:1"},
    "short-video": {"generation_mode": "video", "default_model": "minimax", "default_aspect_ratio": "16:9"},
}

INSPIRE_URLS = {
    "symbol": "https://logosystem.co/symbol",
    "wordmark": "https://logosystem.co/wordmark",
    "symbol-text": "https://logosystem.co/symbol-and-text",
    "brown": "https://logosystem.co/color/brown",
    "beige": "https://logosystem.co/color/beige",
    "black": "https://logosystem.co/color/black",
    "all": "https://logosystem.co/",
}

SOCIAL_SPECS = {
    "x-card": {
        "label": "X Summary Large Image card",
        "width": 1200,
        "height": 600,
        "aspect_ratio": "2:1",
        "notes": "Use for X link cards and illustrated feature cards.",
        "source": "X Developer docs — summary_large_image guidance",
    },
    "x-feed": {
        "label": "X feed post (landscape)",
        "width": 1600,
        "height": 900,
        "aspect_ratio": "16:9",
        "notes": "Practical wide-post default for organic X feed visuals when you want a broader editorial composition than X cards.",
        "source": "brand-gen practical feed preset for X organic posts",
    },
    "x-feed-square": {
        "label": "X feed post (square)",
        "width": 1080,
        "height": 1080,
        "aspect_ratio": "1:1",
        "notes": "Use when one square asset should work across multiple social feeds.",
        "source": "brand-gen practical multi-platform feed preset",
    },
    "x-feed-portrait": {
        "label": "X feed post (portrait)",
        "width": 1080,
        "height": 1350,
        "aspect_ratio": "4:5",
        "notes": "Use for taller organic X feed visuals that maximize mobile vertical space.",
        "source": "brand-gen practical mobile-first feed preset",
    },
    "linkedin-card": {
        "label": "LinkedIn custom image / link card",
        "width": 1200,
        "height": 627,
        "aspect_ratio": "1.91:1",
        "notes": "Best-fit default for LinkedIn link/share cards.",
        "source": "LinkedIn Help + Marketing Solutions docs",
    },
    "linkedin-feed": {
        "label": "LinkedIn feed post (landscape)",
        "width": 1200,
        "height": 627,
        "aspect_ratio": "1.91:1",
        "notes": "Safe landscape preset for LinkedIn feed posts and product announcements.",
        "source": "LinkedIn Marketing Solutions single image specs",
    },
    "linkedin-feed-square": {
        "label": "LinkedIn feed post (square)",
        "width": 1080,
        "height": 1080,
        "aspect_ratio": "1:1",
        "notes": "Use for cleaner feed posts where centered composition matters more than wide framing.",
        "source": "LinkedIn Marketing Solutions single image specs",
    },
    "linkedin-feed-portrait": {
        "label": "LinkedIn feed post (portrait)",
        "width": 627,
        "height": 1200,
        "aspect_ratio": "1:1.91",
        "notes": "Portrait preset aligned to LinkedIn's supported vertical single-image format.",
        "source": "LinkedIn Marketing Solutions single image specs",
    },
    "og-card": {
        "label": "Generic Open Graph social card",
        "width": 1200,
        "height": 630,
        "aspect_ratio": "1.91:1",
        "notes": "Common cross-platform OG default inferred from major social preview ecosystems.",
        "source": "brand-gen inference from major social preview ecosystems",
    },
}


def load_env_values() -> dict[str, str]:
    data: dict[str, str] = {}
    for path in reversed(ENV_CANDIDATES):
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def build_env() -> dict[str, str]:
    env = dict(os.environ)
    env.update(load_env_values())
    return env


def load_json_file(path: Path | None) -> dict:
    if not path or not path.exists():
        return {}
    try:
        value = json.loads(path.read_text())
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


DEFAULT_BRAND_GEN_CONFIG = {
    "version": 2,
    "active": None,
    "activeSession": None,
    "inspirationMode": False,
    "brandGenDir": None,
}

DEFAULT_ITERATION_MEMORY = {
    "version": 1,
    "brand_notes": [],
    "positive_examples": [],
    "negative_examples": [],
    "copy_notes": [],
    "messaging_notes": [],
    "material_notes": {},
}

DEFAULT_BLACKBOARD = {
    "schema_type": "brand_blackboard",
    "schema_version": 1,
    "brand_dna": {},
    "reference_analysis": {},
    "active_brief": {},
    "decisions": [],
    "iteration_history": {},
    "reference_assignments": {},
    "generated_assets": [],
    "artifacts": {
        "latest_plan_draft": "",
        "latest_plan_critique": "",
        "latest_generation_scratchpad": "",
        "latest_generated_version": "",
        "latest_auto_review": "",
    },
}

MATERIAL_PROMPT_SNIPPET_ALIASES = {
    "browser-illustration": "browser_illustration",
    "landing-hero": "landing_hero",
    "hero-banner": "landing_hero",
    "product-banner": "product_banner",
    "banner": "product_banner",
    "product-visual": "feature_illustration",
    "feature-illustration": "feature_illustration",
    "styleframe": "styleframe",
    "storyboard": "styleframe",
    "x-card": "social",
    "x-feed": "social",
    "x-feed-square": "social",
    "x-feed-portrait": "social",
    "linkedin-card": "social",
    "linkedin-feed": "social",
    "linkedin-feed-square": "social",
    "linkedin-feed-portrait": "social",
    "og-card": "social",
    "social": "social",
    "campaign-poster": "campaign_poster",
    "poster": "campaign_poster",
    "event-poster": "merch_poster",
    "merch-poster": "merch_poster",
    "pattern-system": "pattern_system",
    "motif-system": "pattern_system",
    "sticker-family": "sticker_family",
    "badge-family": "sticker_family",
    "icon-family": "sticker_family",
    "animation": "feature_animation",
    "logo-animation": "brand_bumper",
    "bumper-animation": "brand_bumper",
    "stinger-animation": "brand_bumper",
    "feature-animation": "feature_animation",
    "motion-loop": "feature_animation",
    "gif": "feature_animation",
    "short-video": "feature_animation",
}

NON_INTERFACE_MATERIAL_KEYS = {
    "campaign_poster",
    "pattern_system",
    "sticker_family",
    "merch_poster",
    "brand_bumper",
}

INTERFACE_MATERIAL_KEYS = {
    "landing_hero",
    "browser_illustration",
    "product_banner",
    "feature_illustration",
    "social",
    "feature_animation",
}

REFERENCE_ANALYSIS_VERSION = 1

ROLE_PACK_TAG_PRIORITY = ["composition", "motif", "application", "motion"]

ROLE_TRANSLATION_DEFAULTS = {
    "composition": {
        "borrow": ["hierarchy", "crop discipline", "whitespace", "scale contrast"],
        "avoid": ["their logo", "their typography", "their copy", "their exact page structure"],
    },
    "motif": {
        "borrow": ["system logic", "repeat behavior", "family variation", "carrier mechanics"],
        "avoid": ["their literal symbols", "their mascot logic", "their icon subject matter", "their letterforms"],
    },
    "application": {
        "borrow": ["how the identity lands on surfaces", "how one system appears across materials", "print or social pacing"],
        "avoid": ["their branded words", "their headlines", "their product claims", "their visual identity"],
    },
    "motion": {
        "borrow": ["reveal pacing", "masking attitude", "transition rhythm", "final-hold confidence"],
        "avoid": ["their exact animation content", "their cinematic language", "their logo timing signature"],
    },
}

MATERIAL_BRAND_POLICIES = {
    "landing_hero": {
        "role": "core explainer",
        "target_surface": "homepage hero",
        "purpose": "explain what the product is fast with unmistakable brand presence",
        "product_truth_expression": "real product proof such as a UI or CLI moment",
        "abstraction_level": "low",
        "logo_mode": "required",
        "clearly_branded_without_logo_min": 3,
    },
    "browser_illustration": {
        "role": "product proof",
        "target_surface": "landing page section or docs",
        "purpose": "package one real product moment inside a branded frame",
        "product_truth_expression": "one real product UI surface or workflow moment",
        "abstraction_level": "low",
        "logo_mode": "preferred",
        "clearly_branded_without_logo_min": 3,
    },
    "product_banner": {
        "role": "supporting product visual",
        "target_surface": "landing page, docs, or social crop",
        "purpose": "stage one proof moment inside a wider brand field",
        "product_truth_expression": "one real product proof surface",
        "abstraction_level": "low",
        "logo_mode": "preferred",
        "clearly_branded_without_logo_min": 3,
    },
    "feature_illustration": {
        "role": "feature story",
        "target_surface": "feature section or launch thread",
        "purpose": "connect a real feature moment to the larger brand system",
        "product_truth_expression": "one actual workflow, screen, or protocol proof point",
        "abstraction_level": "medium",
        "logo_mode": "preferred",
        "clearly_branded_without_logo_min": 3,
    },
    "social": {
        "role": "social launch or proof card",
        "target_surface": "social feed or preview card",
        "purpose": "be instantly recognizable and legible in-feed",
        "product_truth_expression": "either a real proof moment or a clearly branded product claim",
        "abstraction_level": "low",
        "logo_mode": "required",
        "clearly_branded_without_logo_min": 3,
    },
    "feature_animation": {
        "role": "motion proof",
        "target_surface": "social, hero loop, or launch page",
        "purpose": "animate a real product or workflow proof without losing the brand",
        "product_truth_expression": "a real product frame, workflow, or proof sequence",
        "abstraction_level": "low",
        "logo_mode": "preferred",
        "clearly_branded_without_logo_min": 3,
    },
    "campaign_poster": {
        "role": "campaign still",
        "target_surface": "poster, launch board, or event announcement",
        "purpose": "extend the identity into a campaign surface without losing the product brand",
        "product_truth_expression": "a concrete brand phrase, mark, or product concept that ladders back to the core value proposition",
        "abstraction_level": "medium",
        "logo_mode": "required",
        "clearly_branded_without_logo_min": 3,
    },
    "pattern_system": {
        "role": "supporting brand system",
        "target_surface": "backgrounds, borders, packaging, merch, and motion support",
        "purpose": "create reusable identity mechanics derived from the mark",
        "product_truth_expression": "the system behavior of the brand mark and brand memory, not a random abstract pattern",
        "abstraction_level": "medium",
        "logo_mode": "optional",
        "clearly_branded_without_logo_min": 3,
    },
    "sticker_family": {
        "role": "supporting family system",
        "target_surface": "community assets, packaging, event handouts, or social extras",
        "purpose": "extend the mark into a coherent family of branded units",
        "product_truth_expression": "the mark anatomy and brand system logic behind the product",
        "abstraction_level": "medium",
        "logo_mode": "preferred",
        "clearly_branded_without_logo_min": 3,
    },
    "merch_poster": {
        "role": "collectible extension",
        "target_surface": "print, event, merch, or campaign collateral",
        "purpose": "create a collectible branded surface without becoming generic poster art",
        "product_truth_expression": "a concrete brand theme, phrase, or motif tied to the actual product identity",
        "abstraction_level": "medium",
        "logo_mode": "required",
        "clearly_branded_without_logo_min": 3,
    },
    "brand_bumper": {
        "role": "identity sting",
        "target_surface": "video intro, social loop, or product reveal",
        "purpose": "make the brand memorable in motion while preserving exact mark recognition",
        "product_truth_expression": "the actual brand mark and one concrete motion attitude",
        "abstraction_level": "low",
        "logo_mode": "required",
        "clearly_branded_without_logo_min": 3,
    },
}

MATERIAL_SET_TEMPLATES = {
    "product_core": {
        "description": "Default product-led set for software brands that need clear product understanding before abstract identity play.",
        "materials": [
            {"material_type": "landing-hero", "role": "core explainer"},
            {"material_type": "browser-illustration", "role": "product proof"},
            {"material_type": "x-feed", "role": "social launch"},
            {"material_type": "feature-animation", "role": "motion proof"},
            {"material_type": "pattern-system", "role": "supporting identity system"},
        ],
    },
    "launch_core": {
        "description": "Launch-ready set with one hero, one feature visual, one social output, one motion asset, and one support system.",
        "materials": [
            {"material_type": "landing-hero", "role": "launch hero"},
            {"material_type": "feature-illustration", "role": "feature proof"},
            {"material_type": "x-feed", "role": "launch card"},
            {"material_type": "bumper-animation", "role": "motion identity"},
            {"material_type": "pattern-system", "role": "supporting brand field"},
        ],
    },
    "brand_system_core": {
        "description": "System-first set for brands that already have strong product proof and want applied identity extensions.",
        "materials": [
            {"material_type": "campaign-poster", "role": "campaign still"},
            {"material_type": "pattern-system", "role": "system core"},
            {"material_type": "sticker-family", "role": "family extension"},
            {"material_type": "bumper-animation", "role": "motion sting"},
        ],
    },
    "social_launch": {
        "description": "Social-first set tuned for launch cadence and repeated branded outputs across feeds.",
        "materials": [
            {"material_type": "x-feed", "role": "hero feed post"},
            {"material_type": "linkedin-card", "role": "trust card"},
            {"material_type": "og-card", "role": "preview card"},
            {"material_type": "feature-animation", "role": "social motion"},
            {"material_type": "pattern-system", "role": "supporting crop system"},
        ],
    },
}


def warn(message: str) -> None:
    print(f"WARNING: {message}", file=sys.stderr)


def dedupe_paths(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        resolved = str(Path(path).expanduser().resolve())
        if resolved in seen:
            continue
        seen.add(resolved)
        out.append(Path(resolved))
    return out


def dedupe_keep_order(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = str(item).strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def iteration_memory_paths(brand_dir: Path) -> tuple[Path, Path]:
    return brand_dir / "iteration-memory.json", brand_dir / "iteration-memory.md"


def normalize_iteration_memory(payload: dict | None) -> dict:
    out = dict(DEFAULT_ITERATION_MEMORY)
    if isinstance(payload, dict):
        out.update(payload)
    out["brand_notes"] = list(out.get("brand_notes") or [])
    out["positive_examples"] = list(out.get("positive_examples") or [])
    out["negative_examples"] = list(out.get("negative_examples") or [])
    out["copy_notes"] = list(out.get("copy_notes") or [])
    out["messaging_notes"] = list(out.get("messaging_notes") or [])
    out["material_notes"] = dict(out.get("material_notes") or {})
    return out


def load_iteration_memory(brand_dir: Path) -> dict:
    json_path, _ = iteration_memory_paths(brand_dir)
    if not json_path.exists():
        return dict(DEFAULT_ITERATION_MEMORY)
    return normalize_iteration_memory(load_json_file(json_path))


def render_iteration_memory_markdown(payload: dict) -> str:
    lines = ["# Iteration memory", ""]
    if payload.get("brand_notes"):
        lines += ["## Brand notes"] + [f"- {item}" for item in payload["brand_notes"]] + [""]
    if payload.get("messaging_notes"):
        lines += ["## Messaging notes"] + [f"- {item}" for item in payload["messaging_notes"]] + [""]
    if payload.get("copy_notes"):
        lines += ["## Copy notes"] + [f"- {item}" for item in payload["copy_notes"]] + [""]
    if payload.get("negative_examples"):
        lines += ["## Negative examples"]
        for item in payload["negative_examples"][-12:]:
            lines.append(f"- {item.get('version','note')}: {item.get('material_type','')} — {item.get('summary','')}")
        lines.append("")
    if payload.get("positive_examples"):
        lines += ["## Positive examples"]
        for item in payload["positive_examples"][-12:]:
            lines.append(f"- {item.get('version','note')}: {item.get('material_type','')} — {item.get('summary','')}")
        lines.append("")
    material_notes = payload.get("material_notes") or {}
    if material_notes:
        lines += ["## Material-specific notes"]
        for key, items in material_notes.items():
            lines.append(f"### {key}")
            for item in items[-8:]:
                lines.append(f"- {item}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def save_iteration_memory(brand_dir: Path, payload: dict) -> tuple[Path, Path]:
    json_path, md_path = iteration_memory_paths(brand_dir)
    normalized = normalize_iteration_memory(payload)
    json_path.write_text(json.dumps(normalized, indent=2) + "\n")
    md_path.write_text(render_iteration_memory_markdown(normalized))
    return json_path, md_path


def add_iteration_note(memory: dict, note: str, *, material_type: str | None = None, bucket: str = "brand_notes") -> dict:
    if not note.strip():
        return memory
    memory = normalize_iteration_memory(memory)
    if bucket == "material":
        key = role_pack_material_key(material_type) or (material_type or "general")
        memory["material_notes"].setdefault(key, [])
        if note not in memory["material_notes"][key]:
            memory["material_notes"][key].append(note)
        return memory
    if note not in memory.get(bucket, []):
        memory[bucket].append(note)
    return memory


def capture_feedback_into_iteration_memory(memory: dict, version: str, entry: dict, notes: str | None, score: int | None, status: str | None) -> dict:
    memory = normalize_iteration_memory(memory)
    material_type = entry.get("material_type") or ""
    summary = (notes or "").strip() or "Feedback recorded."
    record = {
        "version": version,
        "material_type": material_type,
        "summary": summary,
        "score": score,
        "status": status or "",
    }
    target_bucket = None
    if status == "favorite" or (score is not None and score >= 4):
        target_bucket = "positive_examples"
    elif status == "rejected" or (score is not None and score <= 2):
        target_bucket = "negative_examples"
    if target_bucket:
        existing = memory.get(target_bucket, [])
        existing = [item for item in existing if item.get("version") != version]
        existing.append(record)
        memory[target_bucket] = existing[-20:]
    if notes:
        lowered = notes.lower()
        if any(term in lowered for term in ["screenshot", "too much ui", "screenshot biased", "ui biased"]):
            memory = add_iteration_note(memory, "Avoid screenshot-biased compositions when the material needs a clearer brand or campaign idea.", material_type=material_type, bucket="material")
        if any(term in lowered for term in ["needs text", "needs slogan", "no text", "missing copy", "brand text"]):
            memory = add_iteration_note(memory, "If the material is a hero, social card, or ad illustration, include deterministic copy or a clear slogan rather than relying on image-only composition.", material_type=material_type, bucket="material")
            memory = add_iteration_note(memory, "Campaign surfaces often need a visible wordmark or slogan to feel clearly branded.", bucket="copy_notes")
        if any(term in lowered for term in ["not branded", "off-brand", "doesn't integrate the brand", "not the brand"]):
            memory = add_iteration_note(memory, "If a concept stops feeling like the brand as a product, strengthen logo, mark geometry, product truth, and brand naming before adding more style.", bucket="brand_notes")
    return memory


def build_iteration_memory_snippet(brand_dir: Path, material_type: str | None) -> str:
    memory = load_iteration_memory(brand_dir)
    lines: list[str] = []
    key = role_pack_material_key(material_type) or (material_type or "")
    brand_notes = memory.get("brand_notes") or []
    messaging_notes = memory.get("messaging_notes") or []
    copy_notes = memory.get("copy_notes") or []
    material_notes = (memory.get("material_notes") or {}).get(key, [])
    negative = memory.get("negative_examples") or []
    if brand_notes:
        lines.append("Recent brand memory:")
        for item in brand_notes[-2:]:
            lines.append(f"- {item}")
    if messaging_notes and (key in INTERFACE_MATERIAL_KEYS or key in {"campaign_poster", "merch_poster", "landing_hero"}):
        lines.append("Recent messaging notes:")
        for item in messaging_notes[-3:]:
            lines.append(f"- {item}")
    if material_notes:
        lines.append("Recent material-specific notes:")
        for item in material_notes[-3:]:
            lines.append(f"- {item}")
    if copy_notes and (key in INTERFACE_MATERIAL_KEYS or key in {"campaign_poster", "merch_poster"}):
        lines.append("Recent copy notes:")
        for item in copy_notes[-2:]:
            lines.append(f"- {item}")
    if negative:
        recent_negative = [item for item in reversed(negative) if not key or role_pack_material_key(item.get("material_type")) == key]
        if recent_negative:
            lines.append("Recent misses to avoid:")
            for item in recent_negative[:2]:
                lines.append(f"- {item.get('summary')}")
    return "\n".join(lines).strip()


def path_media_kind(path: Path | str) -> str:
    ext = Path(path).suffix.lower()
    if ext in SUPPORTED_IMAGE_EXTS:
        return "image"
    if ext in SUPPORTED_VIDEO_EXTS:
        return "video"
    return "other"


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*[max(0, min(255, int(value))) for value in rgb[:3]])


def _hex_to_rgb(value: str) -> tuple[int, int, int] | None:
    text = str(value or "").strip().lstrip("#")
    if len(text) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in text):
        return None
    return tuple(int(text[idx:idx + 2], 16) for idx in range(0, 6, 2))


def _image_content_signature(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def _token_frequency_ranked(values: list[tuple[str, float]], *, limit: int = 6, minimum_weight: float = 0.0) -> list[str]:
    weights: dict[str, float] = {}
    display: dict[str, str] = {}
    for raw_value, weight in values:
        text = str(raw_value or "").strip()
        if not text:
            continue
        key = text.lower()
        weights[key] = weights.get(key, 0.0) + float(weight)
        display.setdefault(key, text)
    ranked = sorted(weights.items(), key=lambda item: (-item[1], display[item[0]].lower()))
    return [display[key] for key, total in ranked if total >= minimum_weight][:limit]


def _weighted_majority(values: list[tuple[str, float]], default: str = "") -> str:
    ranked = _token_frequency_ranked(values, limit=1)
    return ranked[0] if ranked else default


def _average(values: list[float]) -> float:
    valid = [float(value) for value in values if value is not None]
    if not valid:
        return 0.0
    return sum(valid) / len(valid)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _brightness_label(value: float) -> str:
    if value >= 190:
        return "bright"
    if value >= 135:
        return "balanced-light"
    if value >= 90:
        return "balanced-dark"
    return "dark"


def _contrast_label(value: float) -> str:
    if value >= 72:
        return "high-contrast"
    if value >= 42:
        return "medium-contrast"
    return "low-contrast"


def _palette_temperature(colors: list[str]) -> str:
    warm = 0
    cool = 0
    for color in colors[:6]:
        rgb = _hex_to_rgb(color)
        if not rgb:
            continue
        r, _, b = rgb
        if r > b + 16:
            warm += 1
        elif b > r + 16:
            cool += 1
    if warm > cool:
        return "warm"
    if cool > warm:
        return "cool"
    return "neutral"


def extract_reference_image_stats(image_path: Path) -> dict:
    try:
        from PIL import Image, ImageFilter, ImageStat
    except Exception as exc:
        return {
            "dominant_colors": [],
            "brightness": 0.0,
            "brightness_label": "",
            "contrast": 0.0,
            "contrast_label": "",
            "aspect_ratio": "",
            "spatial_rhythm": "",
            "texture_patterns": [],
            "analysis_available": False,
            "analysis_error": f"Pillow unavailable: {exc}",
        }

    try:
        with Image.open(image_path) as img:
            rgb = img.convert("RGB")
            width, height = rgb.size
            sample = rgb.copy()
            sample.thumbnail((160, 160))
            quantized = sample.quantize(colors=6, method=2)
            palette_counts = sorted(quantized.getcolors() or [], reverse=True)
            palette_values = quantized.getpalette() or []
            dominant_colors: list[str] = []
            for _, color_index in palette_counts[:6]:
                base = color_index * 3
                if base + 2 >= len(palette_values):
                    continue
                color = _rgb_to_hex((palette_values[base], palette_values[base + 1], palette_values[base + 2]))
                if color not in dominant_colors:
                    dominant_colors.append(color)

            grayscale = sample.convert("L")
            stats = ImageStat.Stat(grayscale)
            brightness = float(stats.mean[0]) if stats.mean else 0.0
            contrast = float(stats.stddev[0]) if stats.stddev else 0.0
            edge = grayscale.filter(ImageFilter.FIND_EDGES)
            edge_stats = ImageStat.Stat(edge)
            edge_intensity = float(edge_stats.mean[0]) if edge_stats.mean else 0.0
            aspect = width / max(height, 1)
            if aspect >= 1.65:
                aspect_label = "wide"
            elif aspect <= 0.8:
                aspect_label = "portrait"
            else:
                aspect_label = "balanced"
            texture_patterns: list[str] = []
            if edge_intensity >= 36:
                texture_patterns.append("high edge detail")
            elif edge_intensity <= 12:
                texture_patterns.append("flat color fields")
            if contrast >= 72:
                texture_patterns.append("strong tonal separation")
            elif contrast <= 26:
                texture_patterns.append("soft tonal transitions")
            return {
                "dominant_colors": dominant_colors,
                "brightness": round(brightness, 2),
                "brightness_label": _brightness_label(brightness),
                "contrast": round(contrast, 2),
                "contrast_label": _contrast_label(contrast),
                "aspect_ratio": aspect_label,
                "spatial_rhythm": "dense-center" if edge_intensity >= 36 else ("airy-margins" if edge_intensity <= 12 else "balanced"),
                "texture_patterns": texture_patterns,
                "palette_temperature": _palette_temperature(dominant_colors),
                "analysis_available": True,
            }
    except Exception as exc:
        return {
            "dominant_colors": [],
            "brightness": 0.0,
            "brightness_label": "",
            "contrast": 0.0,
            "contrast_label": "",
            "aspect_ratio": "",
            "spatial_rhythm": "",
            "texture_patterns": [],
            "analysis_available": False,
            "analysis_error": str(exc),
        }


def reference_bucket_for_role(role: str, path: Path | None = None) -> str:
    normalized = str(role or "").strip().lower()
    if normalized in {"application", "product", "product-proof", "proof"}:
        return "product"
    if normalized in {"composition", "motif", "motion", "inspiration", "reference"}:
        return "inspiration"
    path_text = str(path or "").lower()
    if any(token in path_text for token in ["/product-screens/", "/screenshots/", "/capture-product/", "product-shot"]):
        return "product"
    return "reference"


def build_reference_analysis_inputs(reference_paths: list[Path], role_pack_roles: list[dict]) -> list[dict]:
    resolved_roles: dict[str, dict] = {}
    for item in role_pack_roles or []:
        raw_path = item.get("path")
        if not raw_path:
            continue
        try:
            resolved_path = str(Path(raw_path).expanduser().resolve())
        except Exception:
            continue
        resolved_roles[resolved_path] = item

    inputs: list[dict] = []
    seen_paths: set[str] = set()
    for path in reference_paths:
        try:
            resolved = path.expanduser().resolve()
        except Exception:
            resolved = path.expanduser()
        if not resolved.exists() or path_media_kind(resolved) != "image":
            continue
        key = str(resolved)
        if key in seen_paths:
            continue
        seen_paths.add(key)
        role_item = resolved_roles.get(key, {})
        role = str(role_item.get("role") or "").strip().lower()
        bucket = reference_bucket_for_role(role, resolved)
        inputs.append(
            {
                "path": resolved,
                "role": role or ("product" if bucket == "product" else "reference"),
                "bucket": bucket,
                "source_key": role_item.get("source_key") or "",
                "source_name": role_item.get("source_name") or "",
            }
        )
    return inputs


def find_role_asset_paths(source_root: Path) -> dict[str, Path]:
    role_assets: dict[str, Path] = {}
    search_roots = [source_root / "screenshots", source_root]
    for role in ROLE_PACK_TAG_PRIORITY:
        for root in search_roots:
            if not root.exists():
                continue
            exact_matches = [
                root / f"{role}.png",
                root / f"{role}.webp",
                root / f"{role}.jpg",
                root / f"{role}.jpeg",
                root / f"{role}.svg",
                root / f"{role}.gif",
                root / f"{role}.mp4",
                root / f"{role}.mov",
                root / f"{role}.webm",
                root / f"{role}.m4v",
            ]
            candidate = next((path for path in exact_matches if path.exists()), None)
            if not candidate:
                wildcard = sorted(
                    [
                        path
                        for path in root.glob(f"{role}*")
                        if path.is_file() and path_media_kind(path) in {"image", "video"}
                    ]
                )
                candidate = wildcard[0] if wildcard else None
            if candidate:
                role_assets[role] = candidate.resolve()
                break
    return role_assets


def sanitize_reference_tag(value: str, fallback: str) -> str:
    tag = re.sub(r"[^A-Za-z0-9]+", "", str(value or ""))
    if not tag:
        tag = fallback
    if not tag[0].isalpha():
        tag = f"r{tag}"
    if len(tag) < 3:
        tag = (tag + "ref")[:3]
    return tag[:15]


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", str(value or "").strip().lower())
    return value.strip("-") or "plan"


def build_reference_tag_context(
    model: str,
    generation_mode: str,
    reference_paths: list[Path],
    role_pack_entries: list[dict],
) -> dict:
    if generation_mode != "image" or model != "runway-gen4-image":
        return {
            "passed_refs": list(reference_paths),
            "reference_tags": [],
            "prompt_suffix": "",
        }

    selected: list[tuple[Path, str, str]] = []
    seen: set[str] = set()

    for index, ref in enumerate(reference_paths):
        resolved = Path(ref).expanduser().resolve()
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        fallback = "brandref" if index == 0 else f"ref{index+1}"
        tag = sanitize_reference_tag("brandref" if index == 0 else fallback, fallback)
        help_text = "Use this tag for brand truth, subject silhouette, and exact mark or product identity."
        selected.append((resolved, tag, help_text))
        if len(selected) >= 3:
            break

    role_priority: list[str] = []
    for item in role_pack_entries:
        role = item.get("role")
        if role and role not in role_priority:
            role_priority.append(role)
    for role in ROLE_PACK_TAG_PRIORITY:
        if role not in role_priority:
            role_priority.append(role)

    if len(selected) < 3:
        for role in role_priority:
            for item in role_pack_entries:
                if item.get("role") != role:
                    continue
                if item.get("asset_kind") != "image":
                    continue
                resolved = Path(item["path"]).expanduser().resolve()
                key = str(resolved)
                if key in seen:
                    continue
                seen.add(key)
                tag = sanitize_reference_tag(role, f"ref{len(selected)+1}")
                help_text = item.get("role_help") or f"Use @{tag} only for {role}."
                selected.append((resolved, tag, help_text))
                break
            if len(selected) >= 3:
                break

    tag_lines = []
    for _path, tag, help_text in selected:
        tag_lines.append(f"- @{tag}: {help_text}")

    prompt_suffix = ""
    if tag_lines:
        prompt_suffix = "Reference tags for this run:\n" + "\n".join(tag_lines)

    return {
        "passed_refs": [item[0] for item in selected],
        "reference_tags": [item[1] for item in selected],
        "prompt_suffix": prompt_suffix,
    }


def prefix_prompt(prelude: str, body: str, token_block: str | None = None) -> str:
    prelude = (prelude or "").strip()
    token_block = (token_block or "").strip()
    body = (body or "").strip()
    parts = [part for part in [prelude, token_block, body] if part]
    return "\n\n".join(parts)


def resolve_profile_path(brand_dir: Path, explicit: str | None = None) -> Path:
    return Path(explicit).expanduser().resolve() if explicit else (brand_dir / "brand-profile.json").resolve()


def resolve_identity_path(brand_dir: Path, explicit: str | None = None) -> Path:
    return Path(explicit).expanduser().resolve() if explicit else (brand_dir / "brand-identity.json").resolve()


def load_brand_memory(brand_dir: Path, profile_arg: str | None = None, identity_arg: str | None = None) -> tuple[Path, Path, dict, dict]:
    profile_path = resolve_profile_path(brand_dir, profile_arg)
    identity_path = resolve_identity_path(brand_dir, identity_arg)
    profile = load_json_file(profile_path)
    identity = load_json_file(identity_path)
    return profile_path, identity_path, profile, identity


def load_reference_role_packs() -> dict:
    return load_json_file(REFERENCE_ROLE_PACKS_PATH)


def load_prompt_review_rules() -> dict:
    return load_json_file(PROMPT_REVIEW_RULES_PATH)


def load_workflow_router_rules() -> dict:
    return load_json_file(WORKFLOW_ROUTER_RULES_PATH)


def role_pack_material_key(material_type: str | None) -> str:
    return MATERIAL_PROMPT_SNIPPET_ALIASES.get((material_type or "").strip().lower(), "")


def load_source_registry() -> dict:
    path = get_sources_registry_path()
    return load_json_file(path)


def load_source_registry_lookup() -> dict[str, dict]:
    registry = load_source_registry()
    out: dict[str, dict] = {}
    for item in registry.get("sources") or []:
        if isinstance(item, dict) and item.get("key"):
            out[str(item["key"])] = item
    return out


def source_risk_rank(value: str | None) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get((value or "medium").strip().lower(), 1)


def normalize_material_brand_policy(material_type: str | None, *, identity: dict | None = None) -> dict:
    """Build the brand policy for a material type.

    Starts from ``MATERIAL_BRAND_POLICIES`` defaults, then overlays any
    per-material overrides stored in ``identity["material_policies"]``.
    This lets each brand customize ``product_truth_expression``, ``purpose``,
    ``target_surface``, etc. without editing source code.

    ``identity["material_policies"]`` schema (optional)::

        {
            "browser_illustration": {
                "product_truth_expression": "a real Acme dashboard with the timeline visible",
                "purpose": "package one real Acme moment inside a branded frame"
            }
        }
    """
    key = role_pack_material_key(material_type)
    base = dict(MATERIAL_BRAND_POLICIES.get(key, {}))
    # Merge per-brand overrides from identity if available
    if identity:
        brand_overrides = (identity.get("material_policies") or {}).get(key)
        if isinstance(brand_overrides, dict):
            base.update({k: v for k, v in brand_overrides.items() if v})
    acceptable = [
        "logo or wordmark",
        "exact brand palette",
        "exact mark geometry or approved motif",
        "real product surface or workflow proof",
        "brand name or approved product phrase",
        "approved carrier or composition pattern",
    ]
    logo_mode = base.get("logo_mode", "preferred")
    min_without_logo = int(base.get("clearly_branded_without_logo_min", 3) or 3)
    base.update(
        {
            "material_key": key,
            "logo_mode": logo_mode,
            "clearly_branded_without_logo_min": min_without_logo,
            "acceptable_anchors": acceptable,
            "rule": (
                "Show the stored logo or wordmark clearly."
                if logo_mode == "required"
                else f"If the logo is not visible, make the piece clearly branded with at least {min_without_logo} anchors from palette, mark geometry, product truth, name, or approved carriers."
            ),
        }
    )
    return base


def summarize_brand_anchor_policy(policy: dict) -> str:
    if not policy:
        return "Keep the output clearly branded."
    pieces = []
    if policy.get("purpose"):
        pieces.append(f"Material job: {policy['purpose']}")
    if policy.get("target_surface"):
        pieces.append(f"Surface: {policy['target_surface']}")
    if policy.get("product_truth_expression"):
        pieces.append(f"Product truth: {policy['product_truth_expression']}")
    if policy.get("rule"):
        pieces.append(f"Branding rule: {policy['rule']}")
    if policy.get("abstraction_level"):
        pieces.append(f"Abstraction: {policy['abstraction_level']}")
    return ". ".join(piece.rstrip(".") for piece in pieces if piece).strip() + "."


def merge_source_metadata(source: dict, registry_lookup: dict[str, dict]) -> dict:
    registry_item = registry_lookup.get(source.get("key") or "", {})
    merged = dict(registry_item)
    merged.update(source or {})
    for key in ("notes", "name", "category", "url"):
        if not merged.get(key):
            merged[key] = registry_item.get(key) or source.get(key) or ""
    for key in ("tags", "role_strengths", "borrow_mechanics", "avoid_literal", "best_for"):
        merged[key] = merged.get(key) or registry_item.get(key) or []
    merged["direct_generation_risk"] = merged.get("direct_generation_risk") or registry_item.get("direct_generation_risk") or "medium"
    merged["translation_only"] = bool(merged.get("translation_only") or registry_item.get("translation_only"))
    return merged


GENERIC_REFERENCE_PATHS = {"", "/", "/work", "/work/", "/cases", "/cases/", "/projects", "/projects/", "/case-studies", "/case-studies/"}
MOTIF_TRIGGER_TERMS = [
    "motif",
    "pattern",
    "background",
    "geometric",
    "brand frame",
    "carrier",
    "band",
    "lattice",
    "route",
    "grid",
    "shape language",
]


def reference_capture_quality(item: dict) -> tuple[str, list[str]]:
    path = str(item.get("path") or "")
    source_key = str(item.get("source_key") or item.get("key") or "").lower()
    notes = str(item.get("notes") or "").lower()
    url = str(item.get("url") or item.get("source_url") or "")
    reasons: list[str] = []
    if source_key.startswith("custom-") or "/product-screens/" in path:
        return "custom-proof", reasons
    parsed_path = urlparse(url).path if url else ""
    normalized_path = parsed_path.rstrip("/") or "/"
    if "homepage" in notes or source_key.endswith("-home") or source_key.endswith("-homepage"):
        reasons.append("reference is captured from a generic homepage")
        return "generic-overview", reasons
    if normalized_path in GENERIC_REFERENCE_PATHS:
        reasons.append(f"reference URL is a generic overview path ({normalized_path})")
        return "generic-overview", reasons
    if any(segment in normalized_path for segment in ["/work/", "/cases/", "/projects/", "/case-studies/"]):
        return "targeted-case-study", reasons
    if "/examples/" in path:
        return "captured-example", reasons
    return "custom", reasons


def plan_implies_motif_reference(material_type: str | None, plan: dict | None = None, raw_prompt: str = "") -> bool:
    material_key = role_pack_material_key(material_type)
    if material_key not in INTERFACE_MATERIAL_KEYS:
        return False
    parts = [raw_prompt]
    if plan:
        parts.extend([
            str(plan.get("system_mechanic") or ""),
            str(plan.get("purpose") or ""),
            str(plan.get("product_truth_expression") or ""),
            " ".join(str(item) for item in (plan.get("push") or [])),
            " ".join(str(item) for item in (plan.get("preserve") or [])),
        ])
    haystack = " ".join(parts).lower()
    return any(term in haystack for term in MOTIF_TRIGGER_TERMS)


def evaluate_reference_quality(material_key: str, selected_roles: list[dict]) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    for item in selected_roles or []:
        role = str(item.get("role") or "").strip().lower()
        quality, reasons = reference_capture_quality(item)
        item["reference_quality"] = quality
        item["reference_quality_reasons"] = reasons
        if material_key in INTERFACE_MATERIAL_KEYS and role in {"composition", "application"} and quality == "generic-overview":
            source_name = item.get("source_name") or item.get("source_key") or role
            errors.append(
                f"{role.title()} ref '{source_name}' is a generic homepage/work index capture; use a targeted case-study or product-presentation crop instead."
            )
        elif quality == "generic-overview":
            warnings.append(f"{role.title()} ref '{item.get('source_name') or item.get('source_key')}' is a generic overview capture.")
    return {"errors": errors, "warnings": warnings}


def default_reference_translation(role: str, item: dict) -> dict:
    defaults = ROLE_TRANSLATION_DEFAULTS.get(role, {})
    borrow = dedupe_keep_order((item.get("borrow_mechanics") or []) + (defaults.get("borrow") or []))
    avoid = dedupe_keep_order((item.get("avoid_literal") or []) + (defaults.get("avoid") or []))
    risk = (item.get("direct_generation_risk") or "medium").strip().lower()
    translation_only = bool(item.get("translation_only"))
    summary_parts = []
    if borrow:
        summary_parts.append(f"Borrow {', '.join(borrow[:4])}")
    if avoid:
        summary_parts.append(f"do not borrow {', '.join(avoid[:4])}")
    if translation_only:
        summary_parts.append("use only as a translated mechanic reference, not a direct style target")
    elif risk == "high":
        summary_parts.append("treat as a high-risk reference and weaken its influence")
    return {
        "borrow_mechanics": borrow,
        "avoid_literal": avoid,
        "direct_generation_risk": risk,
        "translation_only": translation_only,
        "summary": "; ".join(summary_parts).strip(),
    }


def build_selected_role_translation(item: dict) -> dict:
    translation = default_reference_translation(item.get("role") or "", item)
    return {
        "role": item.get("role") or "",
        "source_key": item.get("source_key") or "",
        "source_name": item.get("source_name") or item.get("source_key") or "",
        **translation,
    }


def build_inspiration_translation_summary(selected_roles: list[dict]) -> dict:
    translations = [build_selected_role_translation(item) for item in selected_roles]
    rule = (
        "Translate inspiration into mechanics only. Borrow hierarchy, system logic, application attitude, or motion pacing from references, "
        "but never borrow another brand's logo, typography, copy, literal symbols, or product structure."
    )
    return {
        "rule": rule,
        "references": translations,
    }


def validate_material_plan_dict(plan: dict) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, bool] = {}
    brand_anchor_policy = plan.get("brand_anchor_policy") or {}
    role_pack = plan.get("role_pack") or {}
    translations = ((plan.get("inspiration_translation") or {}).get("references") or [])
    material_type = plan.get("material_type") or ""
    material_key = role_pack_material_key(material_type)
    role_pack_config = ((load_reference_role_packs().get("packs") or {}).get(material_key) or {})
    required_roles = role_pack.get("required_roles") or role_pack_config.get("required_roles") or []
    selected_role_names = [str(item.get("role") or "").strip() for item in (role_pack.get("selected_roles") or []) if str(item.get("role") or "").strip()]
    derived_missing_required = [role for role in required_roles if role not in selected_role_names]

    checks["material_type"] = bool(material_type)
    checks["purpose"] = bool(plan.get("purpose"))
    checks["target_surface"] = bool(plan.get("target_surface"))
    checks["product_truth_expression"] = bool(plan.get("product_truth_expression"))
    checks["abstraction_level"] = bool(plan.get("abstraction_level"))
    checks["brand_anchor_policy"] = bool(brand_anchor_policy.get("rule"))
    checks["system_mechanic"] = bool((plan.get("system_mechanic") or "").strip())
    checks["preserve"] = bool(plan.get("preserve"))
    checks["push"] = bool(plan.get("push"))
    checks["ban"] = bool(plan.get("ban"))
    checks["role_pack_selected_roles"] = bool(role_pack.get("selected_roles")) or not required_roles
    checks["inspiration_translation"] = bool(translations) or not required_roles
    checks["prompt_seed"] = bool(plan.get("prompt_seed"))

    for key in ("material_type", "purpose", "target_surface", "brand_anchor_policy", "prompt_seed", "system_mechanic", "preserve", "push", "ban"):
        if not checks[key]:
            errors.append(f"Missing {key.replace('_', ' ')}.")

    for key in ("product_truth_expression", "abstraction_level", "role_pack_selected_roles", "inspiration_translation"):
        if not checks[key]:
            warnings.append(f"Missing {key.replace('_', ' ')}.")

    if brand_anchor_policy.get("logo_mode") == "required" and not brand_anchor_policy.get("rule"):
        errors.append("Logo-required material is missing a branding rule.")
    if material_key in {"landing_hero", "browser_illustration", "product_banner", "feature_illustration", "social", "feature_animation"} and not plan.get("product_truth_expression"):
        errors.append("Product-led material is missing product truth expression.")
    if required_roles and not role_pack.get("selected_roles"):
        errors.append("Material plan needs translated inspiration refs.")
    if required_roles and derived_missing_required:
        errors.append("Material plan is missing required role refs: " + ", ".join(derived_missing_required))
    if any((item.get("direct_generation_risk") or "").lower() == "high" for item in translations):
        warnings.append("One or more selected references have high direct-generation risk; keep them translated rather than literal.")

    score = sum(1 for passed in checks.values() if passed)
    return {"ok": not errors, "score": score, "max_score": len(checks), "checks": checks, "errors": errors, "warnings": warnings}


def validate_set_manifest_dict(payload: dict) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, bool] = {}
    materials = payload.get("materials") or []
    template = payload.get("template") or ""
    checks["set_name"] = bool(payload.get("set_name"))
    checks["goal"] = bool(payload.get("goal"))
    checks["template"] = bool(template)
    checks["materials"] = bool(materials)
    checks["brand_anchor_rule"] = bool(payload.get("set_brand_rule"))
    checks["translation_rule"] = bool((payload.get("inspiration_translation") or {}).get("rule"))
    if not checks["set_name"]:
        errors.append("Missing set_name.")
    if not checks["goal"]:
        errors.append("Missing goal.")
    if not checks["materials"]:
        errors.append("Set has no materials.")
    if not checks["brand_anchor_rule"]:
        warnings.append("Set is missing the overall brand-anchor rule.")
    if not checks["translation_rule"]:
        warnings.append("Set is missing the inspiration translation rule.")
    product_led = 0
    abstractish = 0
    for item in materials:
        plan_path = Path(item.get("plan_path") or "").expanduser()
        if not plan_path.exists():
            errors.append(f"Missing plan file: {plan_path}")
            continue
        report = validate_material_plan_dict(load_json_file(plan_path))
        if not report["ok"]:
            errors.append(f"{item.get('material_type') or plan_path.name}: " + "; ".join(report["errors"]))
        if report["warnings"]:
            warnings.append(f"{item.get('material_type') or plan_path.name}: " + "; ".join(report["warnings"]))
        policy = normalize_material_brand_policy(item.get("material_type"))
        if policy.get("abstraction_level") == "low":
            product_led += 1
        else:
            abstractish += 1
    if product_led == 0:
        errors.append("Set needs at least one low-abstraction product-led material.")
    if abstractish > product_led:
        warnings.append("Set contains more abstract/system materials than product-led materials; brand may drift away from the product.")
    score = sum(1 for passed in checks.values() if passed)
    return {"ok": not errors, "score": score, "max_score": len(checks), "checks": checks, "errors": errors, "warnings": warnings}


def collect_example_capture_lookup(brand_dir: Path) -> dict[str, dict]:
    lookup: dict[str, dict] = {}
    examples_root = brand_dir / "examples"
    if not examples_root.exists():
        return lookup
    registry_lookup = load_source_registry_lookup()
    for source_json in examples_root.glob("*/*/source.json"):
        source = merge_source_metadata(load_json_file(source_json), registry_lookup)
        if not source:
            continue
        source_root = source_json.parent
        screenshots_dir = source_root / "screenshots"
        candidates = [
            screenshots_dir / "viewport.png",
            screenshots_dir / "full.png",
            source_root / "viewport.png",
            source_root / "full.png",
        ]
        image_path = next((path for path in candidates if path.exists() and path_media_kind(path) == "image"), None)
        if not image_path:
            continue
        role_assets = find_role_asset_paths(source_root)
        key = source.get("key") or source_json.parent.name
        lookup[key] = {
            "key": key,
            "name": source.get("name") or key,
            "notes": source.get("notes") or "",
            "tags": source.get("tags") or [],
            "role_strengths": source.get("role_strengths") or [],
            "borrow_mechanics": source.get("borrow_mechanics") or [],
            "avoid_literal": source.get("avoid_literal") or [],
            "direct_generation_risk": source.get("direct_generation_risk") or "medium",
            "translation_only": bool(source.get("translation_only")),
            "best_for": source.get("best_for") or [],
            "path": image_path.resolve(),
            "role_assets": {role: str(path) for role, path in role_assets.items()},
            "source_root": str(source_root.resolve()),
        }
    return lookup


def resolve_reference_role_pack(brand_dir: Path, material_type: str | None) -> dict:
    material_key = role_pack_material_key(material_type)
    config = load_reference_role_packs()
    pack = (config.get("packs") or {}).get(material_key) or {}
    if not pack:
        return {
            "material_key": material_key,
            "roles": [],
            "paths": [],
            "motion_paths": [],
            "snippet": "",
            "missing_roles": [],
            "required_roles": [],
            "priority": [],
        }
    role_help = config.get("roles") or {}
    lookup = collect_example_capture_lookup(brand_dir)
    priority = [role for role in (pack.get("priority") or []) if role in ROLE_PACK_TAG_PRIORITY]
    for role in ROLE_PACK_TAG_PRIORITY:
        if role not in priority:
            priority.append(role)
    required_roles = [role for role in (pack.get("required_roles") or []) if role in ROLE_PACK_TAG_PRIORITY]
    selection_note = (pack.get("selection_note") or "").strip()
    prefer_unique_sources = bool(pack.get("prefer_unique_sources", True))
    selected_roles: list[dict] = []
    missing_roles: list[str] = []
    used_sources: set[str] = set()
    for role in priority:
        source_keys = pack.get(role) or []
        picked = None
        fallback = None
        for key in source_keys:
            source = lookup.get(key)
            if not source:
                continue
            role_assets = source.get("role_assets") or {}
            asset_path = Path(role_assets.get(role) or source["path"]).expanduser().resolve()
            candidate = {
                "role": role,
                "role_help": role_help.get(role) or "",
                "source_key": source["key"],
                "source_name": source["name"],
                "notes": source["notes"],
                "path": str(asset_path),
                "asset_kind": path_media_kind(asset_path),
                "role_strengths": source.get("role_strengths") or [],
                "borrow_mechanics": source.get("borrow_mechanics") or [],
                "avoid_literal": source.get("avoid_literal") or [],
                "direct_generation_risk": source.get("direct_generation_risk") or "medium",
                "translation_only": bool(source.get("translation_only")),
                "best_for": source.get("best_for") or [],
                "used_role_asset": role in role_assets,
            }
            if not prefer_unique_sources or source["key"] not in used_sources:
                picked = candidate
                break
            if fallback is None:
                fallback = candidate
        if not picked:
            picked = fallback
        if not picked:
            missing_roles.append(role)
            continue
        selected_roles.append(picked)
        used_sources.add(picked["source_key"])

    paths = [Path(item["path"]) for item in selected_roles if item.get("asset_kind") == "image"]
    motion_paths = [Path(item["path"]) for item in selected_roles if item.get("asset_kind") == "video"]
    snippet_lines = []
    if selected_roles:
        snippet_lines.append("Reference role pack for this material:")
        if priority:
            snippet_lines.append(f"- Primary role order: {', '.join(priority[:3])}")
        if required_roles:
            snippet_lines.append(f"- Required roles: {', '.join(required_roles)}")
        snippet_lines.append(f"- Prefer unique sources: {'yes' if prefer_unique_sources else 'no'}")
        if selection_note:
            snippet_lines.append(f"- Selection note: {selection_note}")
        for item in selected_roles:
            line = f"- {item['role']}: {item['source_name']}"
            if item["notes"]:
                line += f" — {item['notes']}"
            if item.get("used_role_asset"):
                line += " [role-specific asset]"
            if item.get("translation_only"):
                line += " [translation-only]"
            if item.get("role_help"):
                line += f" ({item['role_help']})"
            snippet_lines.append(line)
            translation = default_reference_translation(item["role"], item)
            if translation.get("summary"):
                snippet_lines.append(f"  Translate it as: {translation['summary']}")
        snippet_lines.append("- Treat the first two primary roles as the strongest style inputs; support roles are sanity checks, not equal blends.")
    missing_required = [role for role in required_roles if role not in {item.get('role') for item in selected_roles}]
    return {
        "material_key": material_key,
        "roles": selected_roles,
        "paths": paths,
        "motion_paths": motion_paths,
        "snippet": "\n".join(snippet_lines).strip(),
        "missing_roles": missing_roles,
        "required_roles": required_roles,
        "missing_required_roles": missing_required,
        "priority": priority,
        "prefer_unique_sources": prefer_unique_sources,
    }


def suggest_reference_role_pack(brand_dir: Path, material_type: str | None) -> dict:
    material_key = role_pack_material_key(material_type)
    config = load_reference_role_packs()
    pack = (config.get("packs") or {}).get(material_key) or {}
    role_help = config.get("roles") or {}
    lookup = collect_example_capture_lookup(brand_dir)
    priority = [role for role in (pack.get("priority") or []) if role in ROLE_PACK_TAG_PRIORITY]
    for role in ROLE_PACK_TAG_PRIORITY:
        if role not in priority:
            priority.append(role)
    required_roles = [role for role in (pack.get("required_roles") or []) if role in ROLE_PACK_TAG_PRIORITY]
    candidates_by_role: dict[str, list[dict]] = {}
    for role in priority:
        candidates: list[dict] = []
        for key in pack.get(role) or []:
            source = lookup.get(key)
            if not source:
                continue
            role_assets = source.get("role_assets") or {}
            asset_path = Path(role_assets.get(role) or source["path"]).expanduser().resolve()
            candidates.append(
                {
                    "role": role,
                    "role_help": role_help.get(role) or "",
                    "source_key": source["key"],
                    "source_name": source["name"],
                    "notes": source["notes"],
                    "path": str(asset_path),
                    "asset_kind": path_media_kind(asset_path),
                    "borrow_mechanics": source.get("borrow_mechanics") or [],
                    "avoid_literal": source.get("avoid_literal") or [],
                    "direct_generation_risk": source.get("direct_generation_risk") or "medium",
                    "translation_only": bool(source.get("translation_only")),
                    "best_for": source.get("best_for") or [],
                    "used_role_asset": role in role_assets,
                }
            )
        candidates_by_role[role] = candidates
    return {
        "material_key": material_key,
        "priority": priority,
        "required_roles": required_roles,
        "prefer_unique_sources": bool(pack.get("prefer_unique_sources", True)),
        "selection_note": (pack.get("selection_note") or "").strip(),
        "candidates": candidates_by_role,
    }


def parse_role_pick(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise ValueError(f"Invalid --pick '{value}'. Expected role=source-key-or-path.")
    role, picked = value.split("=", 1)
    role = role.strip().lower()
    picked = picked.strip()
    if role not in ROLE_PACK_TAG_PRIORITY:
        raise ValueError(f"Invalid role '{role}'. Expected one of: {', '.join(ROLE_PACK_TAG_PRIORITY)}")
    if not picked:
        raise ValueError("Pick value cannot be empty.")
    return role, picked


def build_plan_prompt_seed(
    identity: dict,
    material_type: str,
    workflow_mode: str,
    system_mechanic: str,
    preserve: list[str],
    push: list[str],
    ban: list[str],
    purpose: str = "",
    target_surface: str = "",
    product_truth_expression: str = "",
    brand_anchor_rule: str = "",
) -> str:
    def join_items(items: list[str]) -> str:
        items = [str(item).strip() for item in items if str(item).strip()]
        if not items:
            return ""
        if len(items) == 1:
            return items[0]
        if len(items) == 2:
            return f"{items[0]} and {items[1]}"
        return f"{', '.join(items[:-1])}, and {items[-1]}"

    brand_name = (identity.get("brand") or {}).get("name") or "the brand"
    preserve_text = join_items(preserve) or "exact mark recognition, palette discipline, and approved brand primitives"
    push_text = join_items(push) or "composition authority, layout confidence, and one sharper system expression"
    ban_text = join_items(ban) or "generic startup symbols, invented copy, and unrelated decorative tricks"
    mechanic = system_mechanic.strip() or "one clear repeated system mechanic"
    framing_bits = []
    if purpose:
        framing_bits.append(f"Purpose: {purpose}")
    if target_surface:
        framing_bits.append(f"Surface: {target_surface}")
    if product_truth_expression:
        framing_bits.append(f"Product truth: {product_truth_expression}")
    if brand_anchor_rule:
        framing_bits.append(f"Branding rule: {brand_anchor_rule}")
    return (
        f"Create a {material_type} for {brand_name} in {workflow_mode} mode. "
        f"Use {mechanic} as the one system mechanic. "
        f"{' '.join(framing_bits)} "
        f"Preserve {preserve_text}. "
        f"Push {push_text}. "
        f"Ban {ban_text}. "
        f"Keep the output brand-led, concrete, and specific rather than abstract."
    )


def build_role_pack_override_from_plan(plan: dict) -> dict:
    role_pack = plan.get("role_pack") or {}
    selected = role_pack.get("selected_roles") or role_pack.get("roles") or []
    required_roles = role_pack.get("required_roles") or []
    selected_role_names = [str(item.get("role") or "").strip() for item in selected if str(item.get("role") or "").strip()]
    missing_required_roles = [role for role in required_roles if role not in selected_role_names]
    paths = [Path(item["path"]).expanduser().resolve() for item in selected if path_media_kind(item["path"]) == "image"]
    motion_paths = [Path(item["path"]).expanduser().resolve() for item in selected if path_media_kind(item["path"]) == "video"]
    snippet_lines = []
    if selected:
        snippet_lines.append("Planned reference role pack for this run:")
        if role_pack.get("priority"):
            snippet_lines.append(f"- Primary role order: {', '.join(role_pack['priority'])}")
        if role_pack.get("required_roles"):
            snippet_lines.append(f"- Required roles: {', '.join(role_pack['required_roles'])}")
        if role_pack.get("selection_note"):
            snippet_lines.append(f"- Selection note: {role_pack['selection_note']}")
        for item in selected:
            line = f"- {item['role']}: {item.get('source_name') or item.get('source_key') or 'custom'}"
            if item.get("notes"):
                line += f" — {item['notes']}"
            snippet_lines.append(line)
            translation = item.get("translation") or default_reference_translation(item.get("role") or "", item)
            if translation.get("summary"):
                snippet_lines.append(f"  Translate it as: {translation['summary']}")
    brand_anchor_policy = plan.get("brand_anchor_policy") or {}
    if brand_anchor_policy.get("rule"):
        snippet_lines.append(f"- Brand anchor policy: {brand_anchor_policy['rule']}")
    return {
        "material_key": role_pack.get("material_key") or role_pack_material_key(plan.get("material_type")),
        "roles": selected,
        "paths": paths,
        "motion_paths": motion_paths,
        "snippet": "\n".join(snippet_lines).strip(),
        "missing_roles": [],
        "required_roles": required_roles,
        "missing_required_roles": missing_required_roles,
        "priority": role_pack.get("priority") or [],
        "prefer_unique_sources": role_pack.get("prefer_unique_sources", True),
    }


def create_material_plan(
    *,
    brand_dir: Path,
    identity_path: Path,
    identity: dict,
    material_type: str,
    mode: str,
    mechanic: str,
    preserve: list[str],
    push: list[str],
    ban: list[str],
    picks: dict[str, str],
    prompt_seed: str | None = None,
    purpose: str | None = None,
    target_surface: str | None = None,
    product_truth_expression: str | None = None,
    abstraction_level: str | None = None,
    set_membership: dict | None = None,
) -> tuple[dict, list[str]]:
    candidates = suggest_reference_role_pack(brand_dir, material_type)
    selected_roles, missing_required = select_plan_roles(candidates, picks)
    selected_roles = [dict(item, translation=build_selected_role_translation(item)) for item in selected_roles]
    policy = normalize_material_brand_policy(material_type, identity=identity)
    preserve = preserve or [policy.get("product_truth_expression") or "stored brand palette, mark recognition, and real product truth"]
    push = push or ["clear focal hierarchy and one stronger composition move"]
    ban = ban or ["generic off-brand decoration or invented product chrome"]
    if purpose:
        policy["purpose"] = purpose
    if target_surface:
        policy["target_surface"] = target_surface
    if product_truth_expression:
        policy["product_truth_expression"] = product_truth_expression
    if abstraction_level:
        policy["abstraction_level"] = abstraction_level
    seed = prompt_seed or build_plan_prompt_seed(
        identity,
        material_type,
        mode,
        mechanic or "",
        preserve or [],
        push or [],
        ban or [],
        purpose=policy.get("purpose") or "",
        target_surface=policy.get("target_surface") or "",
        product_truth_expression=policy.get("product_truth_expression") or "",
        brand_anchor_rule=policy.get("rule") or "",
    )
    plan = {
        "version": 2,
        "brand_dir": str(brand_dir),
        "identity_path": str(identity_path),
        "material_type": material_type,
        "mode": mode,
        "purpose": policy.get("purpose") or "",
        "target_surface": policy.get("target_surface") or "",
        "product_truth_expression": policy.get("product_truth_expression") or "",
        "abstraction_level": policy.get("abstraction_level") or "",
        "brand_anchor_policy": policy,
        "system_mechanic": (mechanic or "").strip(),
        "preserve": preserve or [],
        "push": push or [],
        "ban": ban or [],
        "prompt_seed": seed,
        "inspiration_translation": build_inspiration_translation_summary(selected_roles),
        "role_pack": {
            "material_key": candidates.get("material_key"),
            "priority": candidates.get("priority") or [],
            "required_roles": candidates.get("required_roles") or [],
            "prefer_unique_sources": candidates.get("prefer_unique_sources", True),
            "selection_note": candidates.get("selection_note") or "",
            "selected_roles": selected_roles,
            "missing_required_roles": missing_required,
        },
    }
    if set_membership:
        plan["set_membership"] = set_membership
    return plan, missing_required


def build_material_plan_from_args(args, brand_dir: Path) -> tuple[Path, dict, list[str]]:
    _, identity_path, _, identity = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))
    picks: dict[str, str] = {}
    for raw in getattr(args, "pick", None) or []:
        role, value = parse_role_pick(raw)
        picks[role] = value
    plan, missing_required = create_material_plan(
        brand_dir=brand_dir,
        identity_path=identity_path,
        identity=identity,
        material_type=args.material_type,
        mode=args.mode,
        mechanic=args.mechanic or "",
        preserve=getattr(args, "preserve", None) or [],
        push=getattr(args, "push", None) or [],
        ban=getattr(args, "ban", None) or [],
        picks=picks,
        prompt_seed=getattr(args, "prompt_seed", None),
        purpose=getattr(args, "purpose", None),
        target_surface=getattr(args, "target_surface", None),
        product_truth_expression=getattr(args, "product_truth_expression", None),
        abstraction_level=getattr(args, "abstraction_level", None),
    )
    return identity_path, plan, missing_required


def default_idea_tracks(material_type: str) -> list[dict]:
    key = role_pack_material_key(material_type) or (material_type or "").strip().lower().replace("-", "_")
    if key == "pattern_system":
        return [
            {
                "name": "banded route lattice",
                "mechanic": "banded route lattice",
                "why": "Best when the brand should feel systemic, infrastructural, and modular without becoming abstract slop.",
                "preserve": ["exact cap-and-stem silhouette", "copper-square carrier logic", "cream/copper/espresso palette discipline"],
                "push": ["repeat-tile logic", "border-band treatment", "junction emphasis"],
                "ban": ["gallery mockups", "unrelated rounded icons", "invented text"],
            },
            {
                "name": "pillar fragment grid",
                "mechanic": "pillar fragment crop grid",
                "why": "Best when you want the mark to feel editorial and architectural with tighter module discipline.",
                "preserve": ["pillar proportions", "softly rounded cap bar", "flat board presentation"],
                "push": ["crop variation", "tile tension", "negative-space rhythm"],
                "ban": ["photo environments", "3D embossing", "decorative gradients"],
            },
            {
                "name": "carrier field system",
                "mechanic": "carrier repetition",
                "why": "Best when the system should branch easily into posters, stickers, and product accents later.",
                "preserve": ["square carrier silhouette", "line-weight consistency", "quiet cream field"],
                "push": ["carrier scale contrast", "badge variants", "repeat spacing"],
                "ban": ["random symbols", "moodboard collage", "startup-knot geometry"],
            },
        ]
    if key == "sticker_family":
        return [
            {
                "name": "carrier repetition",
                "mechanic": "carrier repetition",
                "why": "Best when you want the family to feel unmistakably branded and easy to deploy as merch or social accents.",
                "preserve": ["exact mark anatomy", "carrier geometry", "cream/copper palette"],
                "push": ["badge silhouette variety", "capsule variants", "collectible sheet rhythm"],
                "ban": ["invented text", "faces or mascots", "generic startup icons"],
            },
            {
                "name": "utility badge family",
                "mechanic": "utility badge family",
                "why": "Best when you want a more functional, product-adjacent sticker set with tight system coherence.",
                "preserve": ["mark-derived strokes", "repeat corner logic", "flat cutout presentation"],
                "push": ["utility badge shapes", "small emblem variations", "sheet spacing"],
                "ban": ["poster framing", "human illustration", "meme stickers"],
            },
            {
                "name": "capsule strip set",
                "mechanic": "capsule strip set",
                "why": "Best when the brand should feel more collectible and motion-ready without losing discipline.",
                "preserve": ["mark-derived pillar fragments", "one repeated line weight", "brand palette discipline"],
                "push": ["horizontal formats", "capsule carriers", "set contrast"],
                "ban": ["freeform doodles", "dashboard UI chrome", "unrelated medallions"],
            },
        ]
    if key == "campaign_poster":
        return [
            {
                "name": "single emblem field",
                "mechanic": "single emblem field",
                "why": "Best for bold poster framing with one commanding brand move.",
                "preserve": ["exact mark recognition", "quiet field", "deterministic copy"],
                "push": ["headline scale", "band support move", "print authority"],
                "ban": ["fake SaaS hero layout", "extra symbols", "copy invented by model"],
            },
            {
                "name": "band strike poster",
                "mechanic": "band strike",
                "why": "Best when the brand should feel more active and infrastructural.",
                "preserve": ["brand palette", "mark-derived banding", "poster logic"],
                "push": ["diagonal energy", "scale tension", "footer detail"],
                "ban": ["installation photos", "multiple slogans", "visual clutter"],
            },
            {
                "name": "quiet field with footer",
                "mechanic": "quiet field with footer",
                "why": "Best when you want more editorial restraint and premium calm.",
                "preserve": ["ample negative space", "one emblem block", "tight copy system"],
                "push": ["footer rhythm", "micro-detail", "tone authority"],
                "ban": ["collage layout", "generic illustration", "UI remnants"],
            },
        ]
    if key == "brand_bumper":
        return [
            {
                "name": "mask reveal",
                "mechanic": "mask reveal",
                "why": "Best when you want one elegant reveal and a clean final hold.",
                "preserve": ["exact end-frame mark", "camera lock", "palette discipline"],
                "push": ["reveal pacing", "edge wipe confidence", "final hold polish"],
                "ban": ["3D spin", "particles", "extra symbols"],
            },
            {
                "name": "band slide reveal",
                "mechanic": "band slide reveal",
                "why": "Best when the identity should feel more infrastructural and system-led.",
                "preserve": ["mark fidelity", "flat field", "single motion idea"],
                "push": ["band timing", "mask overlap", "tempo"],
                "ban": ["camera moves", "multi-effect blends", "chaotic transitions"],
            },
            {
                "name": "edge crop settle",
                "mechanic": "edge crop settle",
                "why": "Best when you want a calmer, more editorial motion signature.",
                "preserve": ["locked composition", "final silhouette", "quiet hold"],
                "push": ["crop rhythm", "subtle scale change", "timing confidence"],
                "ban": ["glow bursts", "audio gimmicks", "brand morphing"],
            },
        ]
    return [
        {
            "name": "core brand extension",
            "mechanic": "one clear repeated brand mechanic",
            "why": "Best when you need a safe starting direction before branching.",
            "preserve": ["brand truth", "palette", "mark recognition"],
            "push": ["one composition move", "one system mechanic", "one application idea"],
            "ban": ["generic startup aesthetics", "invented text", "unrelated symbols"],
        }
    ]


def default_alignment_questions(material_type: str) -> list[str]:
    key = role_pack_material_key(material_type) or (material_type or "").strip().lower().replace("-", "_")
    common = [
        "Which direction feels most like the brand you want to become, not just the brand you have now?",
        "Should this feel calmer and more institutional, or bolder and more collectible?",
        "What would make you reject a version immediately?",
    ]
    if key == "pattern_system":
        return common + [
            "Do you want the system to feel more infrastructural and routed, or more emblematic and poster-like?",
            "Should this extend more naturally into product surfaces or into editorial/poster surfaces first?",
        ]
    if key == "sticker_family":
        return common + [
            "Should the family feel more utility-badge, more collectible, or more merch-ready?",
            "How much silhouette variety is too much before it stops feeling like one family?",
        ]
    if key == "brand_bumper":
        return common + [
            "Should the motion feel more calm and editorial, or more active and infrastructural?",
            "Is the final hold the main goal, or is the reveal itself supposed to be memorable?",
        ]
    return common


def build_route_payload(args, brand_dir: Path, profile: dict, identity: dict) -> dict:
    try:
        from route_predicates import RoutingBrief, route_brief

        route_info = route_brief(
            RoutingBrief(
                material_type=getattr(args, "material_type", None),
                material_key=role_pack_material_key(getattr(args, "material_type", None)),
                goal=getattr(args, "goal", "") or "",
                request=getattr(args, "request", "") or "",
                has_motion_reference=bool(getattr(args, "motion_reference", None)),
                set_scope=bool(getattr(args, "set_scope", False)),
                reference_image_count=0,
                mode=getattr(args, "mode", None),
            )
        )
    except Exception:
        route_info = classify_workflow_route_smart(
            getattr(args, "material_type", None),
            goal=getattr(args, "goal", "") or "",
            request=getattr(args, "request", "") or "",
            has_motion_reference=bool(getattr(args, "motion_reference", None)),
            set_scope=bool(getattr(args, "set_scope", False)),
        )
    route = route_info["route"]
    plan_needed = route_info["route_key"] in {"reference_translate", "generative_explore", "motion_specialist"}
    return {
        "schema_type": "workflow_route",
        "schema_version": 1,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "material_type": getattr(args, "material_type", None) or "",
        "goal": getattr(args, "goal", "") or "",
        "request": getattr(args, "request", "") or "",
        "route_key": route_info["route_key"],
        "route_label": route.get("label") or route_info["route_key"],
        "specialists": route.get("specialists") or [],
        "required_assets": route.get("required_assets") or [],
        "required_questions": route.get("required_questions") or [],
        "next_commands": route.get("next_commands") or [],
        "notes": route.get("notes") or "",
        "should_plan_first": plan_needed,
        "should_compose_deterministically": False,
        "llm_routed": route_info.get("llm_routed", False),
        "score": route_info.get("score", 0.0),
        "method": route_info.get("method", "default"),
        "score_vector": route_info.get("score_vector", {}),
        "brand_dir": str(brand_dir),
        "brand_dna": summarize_identity(profile, identity),
    }


def derive_copy_candidates(profile: dict, identity: dict, material_type: str, goal: str = "", surface: str = "", *, brand_dir: Path | None = None) -> dict:
    brand_name = ((identity.get("brand") or {}).get("name") or profile.get("brand_name") or "Brand").strip()
    summary = ((identity.get("brand") or {}).get("summary") or profile.get("description") or "").strip()
    tone_words = (identity.get("identity_core") or {}).get("tone_words") or profile.get("keywords") or []
    tone_words = [str(item).strip() for item in tone_words if str(item).strip()]
    memory = load_iteration_memory(brand_dir) if brand_dir else normalize_iteration_memory(None)
    messaging_notes = list(memory.get("messaging_notes") or [])
    copy_notes = list(memory.get("copy_notes") or [])

    # Read from messaging section in brand identity (preferred) with hardcoded fallbacks
    messaging = identity.get("messaging") or {}
    copy_bank = messaging.get("approved_copy_bank") or {}

    hooks = dedupe_keep_order(copy_bank.get("headlines") or [
        f"Welcome to {brand_name}",
        f"What {brand_name} does, in one line",
        f"The core promise of {brand_name}",
    ])
    # Supplement from brand name if copy bank is thin
    if len(hooks) < 3:
        hooks.append(f"Learn more about {brand_name}")
        hooks = dedupe_keep_order(hooks)
    hooks = dedupe_keep_order(hooks + [note for note in messaging_notes if len(note.split()) <= 10])

    subheads = dedupe_keep_order(copy_bank.get("subheadlines") or [
        f"A short description of what {brand_name} offers and why it matters.",
        f"Explain {brand_name} in one sentence that a new visitor can scan.",
    ])
    if messaging.get("elevator"):
        subheads.insert(0, str(messaging["elevator"]).strip())
    subheads = dedupe_keep_order(subheads + [note for note in messaging_notes if len(note.split()) > 10][:2])
    slogans = dedupe_keep_order(copy_bank.get("slogans") or [
        f"{brand_name} — your tagline here",
        f"Built for [audience]. Made by [team].",
    ])
    if messaging.get("tagline"):
        slogans.insert(0, str(messaging["tagline"]).strip())
    slogans = dedupe_keep_order(slogans + [note for note in messaging_notes if len(note.split()) <= 8][:2])
    ctas = copy_bank.get("cta_pairs") or [
        {"primary": "Explore skills", "secondary": "View libraries"},
        {"primary": "Get Started", "secondary": "See communities"},
        {"primary": "Browse skills", "secondary": "Learn how it works"},
    ]
    visual_angles = [
        "Wordmark + one strong product crop + one proof line",
        "Logo-led ad illustration + short slogan + one UI proof inset",
        "Quiet product frame + bold headline + minimal proof chips",
    ]
    if role_pack_material_key(material_type) in {"campaign_poster", "merch_poster", "social"}:
        visual_angles.insert(0, "Ad illustration with slogan + visible brand wordmark + one proof cue")
    if goal:
        slogans.insert(0, goal.strip())

    # Include messaging context so agents can use product voice
    messaging_context = {}
    if messaging.get("tagline"):
        messaging_context["tagline"] = messaging["tagline"]
    if messaging.get("elevator"):
        messaging_context["elevator"] = messaging["elevator"]
    if messaging.get("value_propositions"):
        messaging_context["value_propositions"] = messaging["value_propositions"][:4]
    if messaging.get("voice"):
        messaging_context["voice"] = messaging["voice"]
    if messaging_notes:
        messaging_context["iteration_notes"] = messaging_notes[-4:]
    if copy_notes:
        messaging_context["copy_notes"] = copy_notes[-3:]

    return {
        "brand_name": brand_name,
        "material_type": material_type,
        "goal": goal,
        "surface": surface,
        "messaging": messaging_context,
        "headlines": hooks[:8],
        "slogans": slogans[:8],
        "subheadlines": subheads[:6],
        "cta_pairs": ctas,
        "visual_angles": visual_angles,
        "anti_patterns": [
            "screenshot-only composition with no brand copy",
            "headline text invented by the image model",
            "generic AI dashboard marketing phrasing",
            "social card without visible brand anchor",
        ],
    }


def get_base_brand_guardrail_prelude(profile: dict, identity: dict, material_type: str | None = None) -> str:
    guardrails = identity.get("generation_guardrails") or {}
    material_key = role_pack_material_key(material_type)
    if material_key in INTERFACE_MATERIAL_KEYS:
        return (
            guardrails.get("interface_prompt_prelude")
            or guardrails.get("prompt_prelude")
            or profile.get("brand_guardrail_prelude")
            or (profile.get("identity") or {}).get("brand_guardrail_prelude")
            or ""
        )
    if material_key in NON_INTERFACE_MATERIAL_KEYS:
        return (
            guardrails.get("non_interface_prompt_prelude")
            or guardrails.get("prompt_prelude")
            or profile.get("brand_guardrail_prelude")
            or (profile.get("identity") or {}).get("brand_guardrail_prelude")
            or ""
        )
    return (
        guardrails.get("prompt_prelude")
        or profile.get("brand_guardrail_prelude")
        or (profile.get("identity") or {}).get("brand_guardrail_prelude")
        or ""
    )


def resolve_material_prompt_snippet(profile: dict, identity: dict, material_type: str | None, workflow_mode: str | None = None) -> tuple[str, str, str]:
    key = MATERIAL_PROMPT_SNIPPET_ALIASES.get((material_type or "").strip().lower(), "")
    if not key:
        return "", "", ""
    snippets = (
        (identity.get("generation_guardrails") or {}).get("material_prompt_snippets")
        or profile.get("material_prompt_snippets")
        or {}
    )
    if not isinstance(snippets, dict):
        return key, "", ""
    value = snippets.get(key) or ""
    if isinstance(value, str):
        return key, "default", value.strip()
    if not isinstance(value, dict):
        return key, "", ""
    requested_mode = (workflow_mode or "").strip().lower()
    if requested_mode in {"reference", "inspiration", "hybrid"}:
        variant = requested_mode
    else:
        variant = "default"
    default_value = value.get("default") or ""
    variant_value = value.get(variant) or ""
    parts = [part.strip() for part in [default_value, variant_value if variant != "default" else ""] if isinstance(part, str) and part.strip()]
    return key, variant, "\n\n".join(parts)


def get_brand_guardrail_prelude(profile: dict, identity: dict, brand_gen_dir: Path | None = None, active_brand: str | None = None) -> str:
    brand_prelude = get_base_brand_guardrail_prelude(profile, identity)
    context = load_inspiration_prompt_context(brand_gen_dir=brand_gen_dir, active_brand=active_brand)
    doctrine = context.get("doctrine", "")
    parts = [part.strip() for part in [brand_prelude, doctrine] if part and part.strip()]
    return "\n\n".join(parts)


def summarize_identity(profile: dict, identity: dict) -> dict:
    brand = identity.get("brand") or {}
    identity_core = identity.get("identity_core") or {}
    must_preserve = identity_core.get("must_preserve") or {}
    design_language = identity.get("design_language") or profile.get("design_language") or {}
    tokens = identity.get("design_tokens") or profile.get("design_tokens") or {}
    design_memory = identity.get("design_memory") or profile.get("design_memory") or {}
    guardrails = identity.get("generation_guardrails") or {}
    material_prompt_snippets = ((identity.get("generation_guardrails") or {}).get("material_prompt_snippets") or profile.get("material_prompt_snippets") or {})
    material_set_templates = identity.get("material_set_templates") or {}
    return {
        "brand_name": brand.get("name") or profile.get("brand_name") or "",
        "summary": brand.get("summary") or profile.get("description") or "",
        "homepage_url": brand.get("homepage_url") or profile.get("homepage_url") or "",
        "tone_words": identity_core.get("tone_words") or profile.get("keywords") or [],
        "brand_anchors": identity_core.get("brand_anchors") or profile.get("logo_candidates") or [],
        "palette_direction": must_preserve.get("palette_direction") or profile.get("color_candidates") or [],
        "typography_cues": must_preserve.get("typography_cues") or profile.get("font_candidates") or [],
        "shape_language": must_preserve.get("shape_language") or profile.get("radius_tokens") or [],
        "approved_graphic_devices": identity_core.get("approved_graphic_devices") or [],
        "forbidden_elements": identity_core.get("forbidden_elements") or [],
        "semantic_palette_roles": design_language.get("semantic_palette_roles") or [],
        "component_cues": design_language.get("component_cues") or [],
        "framework_cues": design_language.get("framework_cues") or [],
        "spacing_scale": design_language.get("spacing_scale") or [],
        "design_memory_source": design_memory.get("source_dir") or "",
        "design_memory_principles": design_memory.get("principles") or [],
        "design_memory_components": design_memory.get("components") or [],
        "material_prompt_snippet_keys": sorted(material_prompt_snippets.keys()) if isinstance(material_prompt_snippets, dict) else [],
        "material_set_template_keys": sorted(material_set_templates.keys()) if isinstance(material_set_templates, dict) else [],
        "prompt_prelude": get_brand_guardrail_prelude(profile, identity),
        "inspiration_translation_rule": guardrails.get("inspiration_translation_rule") or "",
        "non_interface_rule": guardrails.get("non_interface_rule") or "",
        "copy_rule": guardrails.get("copy_rule") or "",
        "token_sources": {
            "source_file": tokens.get("source_file") or "",
            "source_url": tokens.get("source_url") or "",
            "has_tokens": bool(tokens),
        },
    }


def validate_identity_summary(profile_path: Path, identity_path: Path, profile: dict, identity: dict) -> dict:
    summary = summarize_identity(profile, identity)
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, bool] = {}

    checks["profile_exists"] = profile_path.exists()
    checks["identity_exists"] = identity_path.exists()
    checks["brand_name"] = bool(summary["brand_name"])
    checks["summary"] = bool(summary["summary"])
    checks["tone_words"] = bool(summary["tone_words"])
    checks["palette_direction"] = bool(summary["palette_direction"])
    checks["typography_cues"] = bool(summary["typography_cues"])
    checks["shape_language"] = bool(summary["shape_language"])
    checks["brand_anchors"] = bool(summary["brand_anchors"])
    checks["approved_graphic_devices"] = bool(summary["approved_graphic_devices"])
    checks["component_cues"] = bool(summary["component_cues"])
    checks["prompt_prelude"] = bool(summary["prompt_prelude"])

    design_language = profile.get("design_language") or identity.get("design_language") or {}
    checks["spacing_scale"] = bool(design_language.get("spacing_scale"))
    checks["semantic_palette_roles"] = bool(design_language.get("semantic_palette_roles"))
    checks["design_tokens"] = bool((identity.get("design_tokens") or profile.get("design_tokens") or {}))

    if not checks["profile_exists"]:
        errors.append(f"Missing brand profile: {profile_path}")
    if not checks["identity_exists"]:
        errors.append(f"Missing brand identity: {identity_path}")
    if not checks["brand_name"]:
        errors.append("Missing brand name.")
    if not checks["prompt_prelude"]:
        errors.append("Missing global brand guardrail prompt prelude.")

    for field, label in [
        ("summary", "brand summary"),
        ("tone_words", "tone words"),
        ("palette_direction", "palette direction"),
        ("typography_cues", "typography cues"),
        ("shape_language", "shape/radius cues"),
    ]:
        if not checks[field]:
            warnings.append(f"Missing {label}.")

    if not checks["brand_anchors"]:
        warnings.append("No brand anchors / logo candidates stored.")
    if not checks["approved_graphic_devices"]:
        warnings.append("No approved non-interface graphic devices stored.")
    if not checks["component_cues"]:
        warnings.append("No component cues stored; outputs may feel generic.")
    if not checks["spacing_scale"]:
        warnings.append("No spacing scale stored; deterministic composition will use generic spacing defaults.")
    if not checks["semantic_palette_roles"]:
        warnings.append("No semantic palette roles stored.")
    if not checks["design_tokens"]:
        warnings.append("No imported design tokens stored.")

    score = sum(1 for passed in checks.values() if passed)
    return {
        "ok": not errors,
        "score": score,
        "max_score": len(checks),
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
        "summary": summary,
        "files": {
            "profile": str(profile_path),
            "identity": str(identity_path),
        },
    }


def load_inspiration_index(brand_gen_dir: Path | None = None) -> dict:
    path = get_inspiration_index_path(brand_gen_dir)
    if not path or not path.exists():
        return {"version": 1, "sources": {}}
    return load_json_file(path) or {"version": 1, "sources": {}}


def inspirations_config_path(active_brand: str | None = None, brand_gen_dir: Path | None = None) -> Path | None:
    resolved = brand_gen_dir or get_brand_gen_dir()
    brand_key = active_brand or resolve_active_brand_key(resolved)
    if not resolved or not brand_key:
        return None
    return resolved / "brands" / brand_key / "inspirations.json"


def load_inspirations_config(active_brand: str | None = None, brand_gen_dir: Path | None = None) -> dict:
    path = inspirations_config_path(active_brand, brand_gen_dir)
    if not path or not path.exists():
        return {"version": 1, "sources": [], "mode": "principles", "mergeStrategy": "concat"}
    payload = load_json_file(path)
    merged = {"version": 1, "sources": [], "mode": "principles", "mergeStrategy": "concat"}
    merged.update(payload)
    merged["sources"] = merged.get("sources") or []
    return merged


def save_inspirations_config(config: dict, active_brand: str, brand_gen_dir: Path | None = None) -> Path:
    resolved = brand_gen_dir or get_brand_gen_dir() or (REPO_ROOT / ".brand-gen")
    path = resolved / "brands" / active_brand / "inspirations.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "sources": [], "mode": "principles", "mergeStrategy": "concat"}
    payload.update(config or {})
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def load_inspiration_prompt_context(brand_gen_dir: Path | None = None, active_brand: str | None = None, material_type: str | None = None) -> dict:
    resolved = brand_gen_dir or get_brand_gen_dir()
    brand_key = active_brand or resolve_active_brand_key(resolved)
    if not resolved or not brand_key:
        return {"doctrine": "", "token_block": "", "sources": [], "skipped": [], "mode": "principles"}

    config = load_brand_gen_config(resolved)
    inspiration_config = load_inspirations_config(brand_key, resolved)
    index = load_inspiration_index(resolved).get("sources", {})
    available_paths: list[Path] = []
    used_sources: list[str] = []
    skipped: list[dict[str, str]] = []
    for key in inspiration_config.get("sources", []):
        item = index.get(key)
        if not item:
            skipped.append({"source": key, "reason": "not indexed"})
            continue
        status = item.get("status")
        if status != "complete":
            skipped.append({"source": key, "reason": f"status={status or 'unknown'}"})
            continue
        design_path = item.get("designMemoryPath")
        if not design_path:
            skipped.append({"source": key, "reason": "missing designMemoryPath"})
            continue
        path = Path(design_path).expanduser()
        if not path.is_absolute():
            path = (resolved / design_path).resolve()
        if not path.exists():
            skipped.append({"source": key, "reason": "design memory path missing"})
            continue
        available_paths.append(path)
        used_sources.append(key)

    doctrine = merge_inspiration_doctrine(available_paths, material_type=material_type) if available_paths else ""
    token_parts = []
    if config.get("inspirationMode"):
        seen_token_blocks: set[str] = set()
        for path in available_paths:
            token_text = load_tokens(path)
            if token_text:
                normalized = token_text.strip()
                if not normalized or normalized in seen_token_blocks:
                    continue
                seen_token_blocks.add(normalized)
                token_parts.append(token_text)
        token_block = "\n\n".join(token_parts).strip()
        if len(token_block) > 2000:
            warn("Inspiration token block exceeded 2000 chars; truncating.")
            token_block = token_block[:2000].rstrip()
    else:
        token_block = ""
    return {
        "doctrine": doctrine,
        "token_block": token_block,
        "sources": used_sources,
        "skipped": skipped,
        "mode": "full" if config.get("inspirationMode") else "principles",
    }


def build_effective_prompt(profile: dict, identity: dict, body: str, *, brand_gen_dir: Path | None = None, active_brand: str | None = None, brand_dir: Path | None = None, material_type: str | None = None, workflow_mode: str | None = None, disable_brand_guardrails: bool = False, role_pack_override: dict | None = None, reference_analysis: dict | None = None) -> dict:
    brand_prelude = "" if disable_brand_guardrails else get_base_brand_guardrail_prelude(profile, identity, material_type)
    material_key, material_variant, material_snippet = ("", "", "") if disable_brand_guardrails else resolve_material_prompt_snippet(profile, identity, material_type, workflow_mode)
    iteration_memory_snippet = "" if disable_brand_guardrails or not brand_dir else build_iteration_memory_snippet(brand_dir, material_type)
    if role_pack_override is not None:
        role_pack = role_pack_override
    elif brand_dir and not disable_brand_guardrails:
        role_pack = resolve_reference_role_pack(brand_dir, material_type)
    else:
        role_pack = {"snippet": "", "roles": [], "paths": [], "motion_paths": [], "missing_roles": [], "required_roles": [], "missing_required_roles": [], "priority": [], "prefer_unique_sources": True, "material_key": ""}
    role_pack_snippet = role_pack.get("snippet", "")
    reference_analysis_snippet = "" if disable_brand_guardrails else build_reference_analysis_snippet(reference_analysis or {}, material_type)
    inspiration = load_inspiration_prompt_context(brand_gen_dir=brand_gen_dir, active_brand=active_brand, material_type=material_type)
    doctrine = "" if disable_brand_guardrails else inspiration.get("doctrine", "")
    token_block = "" if disable_brand_guardrails else inspiration.get("token_block", "")

    # Inject compact messaging context so copy-bearing materials use real brand language
    messaging_snippet = ""
    if not disable_brand_guardrails:
        messaging = identity.get("messaging") or {}
        _msg_parts: list[str] = []
        if messaging.get("tagline"):
            _msg_parts.append(f"Tagline: {messaging['tagline']}")
        if messaging.get("elevator"):
            _msg_parts.append(messaging["elevator"])
        voice = messaging.get("voice") or {}
        if voice.get("description"):
            _msg_parts.append(f"Voice: {voice['description']}")
        if brand_dir:
            memory = load_iteration_memory(brand_dir)
            messaging_notes = list(memory.get("messaging_notes") or [])
            if messaging_notes:
                _msg_parts.append("Recent messaging notes: " + " | ".join(messaging_notes[-2:]))
        if _msg_parts:
            messaging_snippet = "Brand context: " + " ".join(_msg_parts)
            # Keep it compact for interface materials
            if material_key in INTERFACE_MATERIAL_KEYS and len(messaging_snippet) > 250:
                messaging_snippet = messaging_snippet[:250].rstrip() + "…"

    # Apply per-part caps for non-interface materials to prevent prelude bloat
    if material_key not in INTERFACE_MATERIAL_KEYS:
        brand_prelude = cap_text_at_sentence(brand_prelude, NON_INTERFACE_PRELUDE_CAP)
        doctrine = cap_text_at_sentence(doctrine, NON_INTERFACE_DOCTRINE_CAP)
        reference_analysis_snippet = cap_text_at_sentence(reference_analysis_snippet, NON_INTERFACE_REF_ANALYSIS_CAP)

    combined_prelude = "\n\n".join(
        part for part in [brand_prelude.strip(), messaging_snippet.strip(), iteration_memory_snippet.strip(), material_snippet.strip(), role_pack_snippet.strip(), reference_analysis_snippet.strip(), doctrine.strip()] if part and part.strip()
    )
    # Hard cap on total prelude for non-interface materials
    if material_key not in INTERFACE_MATERIAL_KEYS and len(combined_prelude) > NON_INTERFACE_TOTAL_PRELUDE_CAP:
        combined_prelude = cap_text_at_sentence(combined_prelude, NON_INTERFACE_TOTAL_PRELUDE_CAP)
    resolved = prefix_prompt(combined_prelude, body, token_block=token_block)
    return {
        "brand_prelude": brand_prelude,
        "iteration_memory_snippet": iteration_memory_snippet,
        "material_prompt_key": material_key,
        "material_prompt_variant": material_variant,
        "material_prompt_snippet": material_snippet,
        "reference_role_pack": role_pack.get("roles", []),
        "reference_role_pack_paths": [str(path) for path in role_pack.get("paths", [])],
        "reference_role_pack_motion_paths": [str(path) for path in role_pack.get("motion_paths", [])],
        "reference_role_pack_snippet": role_pack_snippet,
        "reference_role_pack_missing_roles": role_pack.get("missing_roles", []),
        "reference_role_pack_required_roles": role_pack.get("required_roles", []),
        "reference_role_pack_missing_required_roles": role_pack.get("missing_required_roles", []),
        "reference_role_pack_priority": role_pack.get("priority", []),
        "reference_role_pack_prefer_unique_sources": role_pack.get("prefer_unique_sources", True),
        "reference_analysis": reference_analysis or {},
        "reference_analysis_snippet": reference_analysis_snippet,
        "inspiration_doctrine": doctrine,
        "token_block": token_block,
        "resolved_prompt": resolved,
        "inspiration_sources": inspiration.get("sources", []),
        "skipped_inspiration_sources": inspiration.get("skipped", []),
        "inspiration_mode": inspiration.get("mode", "principles"),
    }


def split_prompt_sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return []
    raw_parts = re.split(r"(?<=[.!?])\s+|(?:\s+-\s+)", cleaned)
    out: list[str] = []
    seen: set[str] = set()
    for part in raw_parts:
        part = part.strip(" -\n\t")
        if not part:
            continue
        key = part.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(part)
    return out


def sentence_join(items: list[str]) -> str:
    cleaned = [str(item).strip() for item in items if str(item).strip()]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return ", ".join(cleaned[:-1]) + f", and {cleaned[-1]}"


def compact_role_pack_snippet(roles: list[dict]) -> str:
    if not roles:
        return ""
    lines = ["Translate references into mechanics only:"]
    for item in roles[:3]:
        translation = item.get("translation") or default_reference_translation(item.get("role") or "", item)
        borrow = translation.get("borrow_mechanics") or []
        avoid = translation.get("avoid_literal") or []
        bits = []
        if borrow:
            bits.append(f"borrow {sentence_join(borrow[:2])}")
        if avoid:
            bits.append(f"avoid {sentence_join(avoid[:2])}")
        source_name = item.get("source_name") or item.get("source_key") or item.get("role") or "reference"
        role = item.get("role") or "reference"
        suffix = f" from {source_name}" if source_name else ""
        detail = "; ".join(bits).strip()
        lines.append(f"- {role}{suffix}: {detail}".rstrip(": "))
    return "\n".join(lines)


def material_group_for_prompt_review(material_key: str) -> str:
    if material_key in INTERFACE_MATERIAL_KEYS:
        return "interface"
    if material_key in NON_INTERFACE_MATERIAL_KEYS:
        return "non_interface"
    return "general"


def prompt_review_rule_matches(rule: dict, *, material_key: str, raw_prompt: str, context: dict) -> bool:
    material_groups = set(rule.get("material_groups") or [])
    materials = set(rule.get("materials") or [])
    current_group = material_group_for_prompt_review(material_key)
    if material_groups and current_group not in material_groups:
        return False
    if materials and material_key not in materials:
        return False
    when = rule.get("when") or {}
    brand_prelude = context.get("brand_prelude") or ""
    resolved_prompt = context.get("resolved_prompt") or ""
    role_pack = context.get("reference_role_pack") or []
    raw_lower = (raw_prompt or "").lower()

    if "brand_prelude_contains" in when and when["brand_prelude_contains"] not in brand_prelude:
        return False
    if "resolved_prompt_chars_gt" in when and len(resolved_prompt) <= int(when["resolved_prompt_chars_gt"]):
        return False
    if when.get("role_pack_empty") is True and role_pack:
        return False
    if "raw_prompt_missing_any_keywords" in when:
        keywords = [str(item).lower() for item in when["raw_prompt_missing_any_keywords"]]
        if any(keyword in raw_lower for keyword in keywords):
            return False
    if "raw_prompt_phrase_count_gte" in when:
        payload = when["raw_prompt_phrase_count_gte"] or {}
        phrases = [str(item).lower() for item in payload.get("phrases", [])]
        threshold = int(payload.get("count", 1) or 1)
        count = sum(raw_lower.count(phrase) for phrase in phrases)
        if count < threshold:
            return False
    return True


def evaluate_prompt_review_rules(material_key: str, raw_prompt: str, context: dict) -> tuple[list[str], list[str]]:
    issues: list[str] = []
    recommendations: list[str] = []
    for rule in (load_prompt_review_rules().get("rules") or []):
        if not isinstance(rule, dict):
            continue
        if not prompt_review_rule_matches(rule, material_key=material_key, raw_prompt=raw_prompt, context=context):
            continue
        issue = (rule.get("issue") or "").strip()
        recommendation = (rule.get("recommendation") or "").strip()
        if issue and issue not in issues:
            issues.append(issue)
        if recommendation and recommendation not in recommendations:
            recommendations.append(recommendation)
    return issues, recommendations


# ── Prelude budget caps ──────────────────────────────────────────────
# Interface materials have tight per-part caps (already in place).
# Non-interface materials (posters, stickers, merch) had no caps,
# causing preludes to balloon (v15: 7205 chars). These constants set
# reasonable ceilings for the non-interface path.
NON_INTERFACE_PRELUDE_CAP = 1500      # base brand guardrail prelude
NON_INTERFACE_DOCTRINE_CAP = 600      # inspiration doctrine
NON_INTERFACE_REF_ANALYSIS_CAP = 500  # reference analysis snippet
NON_INTERFACE_TOTAL_PRELUDE_CAP = 3000  # combined prelude (all parts before body)


def cap_text_at_sentence(text: str, max_chars: int) -> str:
    """Truncate *text* at the nearest sentence boundary ≤ *max_chars*.

    Falls back to hard truncation + "…" if no sentence boundary is found.
    """
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    sentences = split_prompt_sentences(text)
    if not sentences:
        return text[:max_chars].rstrip() + "…"
    result: list[str] = []
    total = 0
    for s in sentences:
        addition = len(s) + (2 if result else 0)  # account for ". " join
        if total + addition > max_chars:
            break
        result.append(s)
        total += addition
    if not result:
        return text[:max_chars].rstrip() + "…"
    joined = " ".join(result)
    if not joined.endswith((".", "!", "?")):
        joined += "."
    return joined


def compress_prompt_body(body: str, material_key: str, *, max_sentences: int | None = None, max_chars: int | None = None) -> str:
    if max_sentences is None:
        max_sentences = 4 if material_key in INTERFACE_MATERIAL_KEYS else 6
    if max_chars is None:
        max_chars = 400 if material_key in INTERFACE_MATERIAL_KEYS else 700
    sentences = split_prompt_sentences(body)
    if not sentences:
        return ""
    prioritized: list[tuple[int, str]] = []
    keywords = []
    if material_key in INTERFACE_MATERIAL_KEYS:
        keywords = ["real", "product", "ui", "screenshot", "hero", "moment", "crop", "preserve", "logo", "copy", "headline"]
    elif material_key in NON_INTERFACE_MATERIAL_KEYS:
        keywords = ["logo", "mark", "motif", "copy", "headline", "slogan", "brand", "palette", "poster"]
    else:
        keywords = ["brand", "product", "logo", "headline"]
    for idx, sentence in enumerate(sentences):
        score = 0
        lower = sentence.lower()
        for kw in keywords:
            if kw in lower:
                score += 3
        if "do not" in lower or "never" in lower:
            score += 2
        if idx < 3:
            score += 1
        prioritized.append((score, sentence))
    picked: list[str] = []
    total = 0
    for _, sentence in sorted(prioritized, key=lambda item: (-item[0], sentences.index(item[1]))):
        candidate_len = total + len(sentence) + (1 if picked else 0)
        if len(picked) >= max_sentences or candidate_len > max_chars:
            continue
        picked.append(sentence)
        total = candidate_len
    if not picked:
        picked = sentences[: min(max_sentences, len(sentences))]
    return " ".join(picked).strip()


def review_prompt_architecture(
    profile: dict,
    identity: dict,
    raw_prompt: str,
    context: dict,
    *,
    material_type: str | None = None,
    workflow_mode: str | None = None,
    token_block: str | None = None,
) -> dict:
    material_key = context.get("material_prompt_key") or role_pack_material_key(material_type)
    issues, recommendations = evaluate_prompt_review_rules(material_key, raw_prompt, context)
    ref_issues, ref_recommendations = reference_analysis_review_notes(context.get("reference_analysis") or {})
    for issue in ref_issues:
        if issue not in issues:
            issues.append(issue)
    for recommendation in ref_recommendations:
        if recommendation not in recommendations:
            recommendations.append(recommendation)
    # Interface materials: flag too many refs (prefer 1 product + 1 inspiration max)
    role_pack = context.get("reference_role_pack") or []
    if material_key in INTERFACE_MATERIAL_KEYS and len(role_pack) > 2:
        note = f"Interface material has {len(role_pack)} refs; prefer 1 product hero + 1 inspiration ref for tighter composition."
        if note not in recommendations:
            recommendations.append(note)

    base_prelude = get_base_brand_guardrail_prelude(profile, identity, material_type)
    resolved_prompt = context.get("resolved_prompt") or ""

    # Cap base prelude for non-interface materials (was uncapped → 2000+ chars)
    if material_key not in INTERFACE_MATERIAL_KEYS:
        base_prelude = cap_text_at_sentence(base_prelude, NON_INTERFACE_PRELUDE_CAP)

    compact_parts = [base_prelude.strip()]
    material_snippet = (context.get("material_prompt_snippet") or "").strip()
    if material_snippet:
        compact_parts.append(material_snippet)
    compact_roles = compact_role_pack_snippet(role_pack)
    if compact_roles:
        compact_parts.append(compact_roles)
    reference_analysis_snippet = (context.get("reference_analysis_snippet") or "").strip()
    ref_analysis_cap = 250 if material_key in INTERFACE_MATERIAL_KEYS else NON_INTERFACE_REF_ANALYSIS_CAP
    if reference_analysis_snippet and len(reference_analysis_snippet) <= ref_analysis_cap:
        compact_parts.append(reference_analysis_snippet)
    elif reference_analysis_snippet:
        compact_parts.append(cap_text_at_sentence(reference_analysis_snippet, ref_analysis_cap))
    doctrine = (context.get("inspiration_doctrine") or "").strip()
    doctrine_cap = 350 if material_key in INTERFACE_MATERIAL_KEYS else NON_INTERFACE_DOCTRINE_CAP
    if doctrine and len(doctrine) <= doctrine_cap:
        compact_parts.append(doctrine)
    elif doctrine:
        compact_parts.append(cap_text_at_sentence(doctrine, doctrine_cap))
    compact_memory = (context.get("iteration_memory_snippet") or "").strip()
    if compact_memory and len(compact_memory) < 500:
        compact_parts.append(compact_memory)
    compact_body = compress_prompt_body(raw_prompt, material_key)
    compact_prelude = "\n\n".join(part for part in compact_parts if part)
    # Hard cap on total prelude for non-interface materials
    if material_key not in INTERFACE_MATERIAL_KEYS and len(compact_prelude) > NON_INTERFACE_TOTAL_PRELUDE_CAP:
        compact_prelude = cap_text_at_sentence(compact_prelude, NON_INTERFACE_TOTAL_PRELUDE_CAP)
    refined_prompt = prefix_prompt(compact_prelude, compact_body, token_block=token_block or "")

    return {
        "material_key": material_key,
        "workflow_mode": workflow_mode or "",
        "issues": issues,
        "recommendations": recommendations,
        "used_refined_prompt": bool(refined_prompt and refined_prompt != resolved_prompt),
        "refined_prompt": refined_prompt or resolved_prompt,
        "resolved_prompt": resolved_prompt,
        "compact_role_pack": compact_roles,
        "reference_analysis_snippet": reference_analysis_snippet,
        "compact_body": compact_body,
    }


def save_prompt_review_scratchpad(brand_dir: Path, review: dict, *, label: str) -> Path:
    scratch_dir = brand_dir / "scratchpads" / "prompt-reviews"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    path = scratch_dir / f"{slugify(label)}.json"
    path.write_text(json.dumps(review, indent=2) + "\n")
    return path


def save_plan_draft(brand_dir: Path, payload: dict, *, label: str) -> Path:
    scratch_dir = brand_dir / "scratchpads" / "plan-drafts"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    path = scratch_dir / f"{slugify(label)}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def save_plan_critique(brand_dir: Path, payload: dict, *, label: str) -> Path:
    scratch_dir = brand_dir / "scratchpads" / "plan-critiques"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    path = scratch_dir / f"{slugify(label)}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def save_generation_scratchpad(brand_dir: Path, payload: dict, *, label: str) -> Path:
    scratch_dir = brand_dir / "scratchpads" / "generation"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    path = scratch_dir / f"{slugify(label)}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def resolve_workflow_id(*payloads: dict | None) -> str:
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        value = payload.get("workflow_id")
        if value:
            return str(value)
        meta = payload.get("meta") or {}
        if isinstance(meta, dict) and meta.get("workflow_id"):
            return str(meta["workflow_id"])
    return uuid.uuid4().hex[:12]


def iter_workflow_artifact_paths(brand_dir: Path) -> list[Path]:
    roots = [
        brand_dir / "scratchpads" / "plan-drafts",
        brand_dir / "scratchpads" / "plan-critiques",
        brand_dir / "scratchpads" / "generation",
    ]
    paths: list[Path] = []
    for root in roots:
        if root.exists():
            paths.extend(sorted(root.glob("*.json")))
    return paths


def collect_workflow_artifacts(brand_dir: Path, workflow_id: str) -> dict[str, list[dict]]:
    grouped = {
        "plan_drafts": [],
        "plan_critiques": [],
        "generation_scratchpads": [],
    }
    mapping = {
        "plan_draft": "plan_drafts",
        "plan_critique": "plan_critiques",
        "generation_scratchpad": "generation_scratchpads",
    }
    for path in iter_workflow_artifact_paths(brand_dir):
        try:
            payload = load_json_file(path)
        except Exception:
            continue
        current = resolve_workflow_id(payload)
        if current != workflow_id:
            continue
        schema_type = str(payload.get("schema_type") or "")
        bucket = mapping.get(schema_type)
        if not bucket:
            continue
        grouped[bucket].append(
            {
                "path": str(path),
                "schema_type": schema_type,
                "created_at": payload.get("created_at") or "",
                "material_type": payload.get("material_type") or ((payload.get("plan") or {}).get("material_type") or ""),
                "mode": payload.get("workflow_mode") or payload.get("mode") or ((payload.get("plan") or {}).get("mode") or ""),
            }
        )
    return grouped


def blackboard_path(brand_dir: Path) -> Path:
    return brand_dir / "blackboard.json"


def summarize_iteration_memory_for_blackboard(memory: dict) -> dict:
    return {
        "brand_notes": (memory.get("brand_notes") or [])[-5:],
        "copy_notes": (memory.get("copy_notes") or [])[-5:],
        "negative_examples": (memory.get("negative_examples") or [])[-5:],
        "positive_examples": (memory.get("positive_examples") or [])[-5:],
        "material_notes": memory.get("material_notes") or {},
    }


def append_blackboard_decision(
    board: dict,
    *,
    agent: str,
    decision: str,
    confidence: float | None = None,
    severity: str | None = None,
    data: dict | None = None,
    workflow_id: str | None = None,
) -> dict:
    decisions = board.setdefault("decisions", [])
    item = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "agent": agent,
        "decision": decision,
    }
    if workflow_id:
        item["workflow_id"] = workflow_id
    if confidence is not None:
        item["confidence"] = confidence
    if severity:
        item["severity"] = severity
    if data:
        item["data"] = data
    decisions.append(item)
    board["decisions"] = decisions[-40:]
    return board


def get_workflow_lineage(board: dict, workflow_id: str) -> dict:
    decisions = [item for item in (board.get("decisions") or []) if item.get("workflow_id") == workflow_id]
    assets = [item for item in (board.get("generated_assets") or []) if item.get("workflow_id") == workflow_id]
    return {"workflow_id": workflow_id, "decisions": decisions, "assets": assets}


def load_blackboard(brand_dir: Path, profile: dict | None = None, identity: dict | None = None) -> dict:
    path = blackboard_path(brand_dir)
    if path.exists():
        try:
            value = json.loads(path.read_text())
            if isinstance(value, dict):
                board = dict(DEFAULT_BLACKBOARD)
                board.update(value)
            else:
                board = dict(DEFAULT_BLACKBOARD)
        except Exception:
            board = dict(DEFAULT_BLACKBOARD)
    else:
        board = dict(DEFAULT_BLACKBOARD)
    if profile is not None and identity is not None:
        board["brand_dna"] = summarize_identity(profile, identity)
    board["iteration_history"] = summarize_iteration_memory_for_blackboard(load_iteration_memory(brand_dir))
    return board


def save_blackboard(brand_dir: Path, board: dict) -> Path:
    path = blackboard_path(brand_dir)
    payload = dict(DEFAULT_BLACKBOARD)
    payload.update(board or {})
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def update_blackboard_active_brief(board: dict, plan: dict, *, stage: str, path: str = "") -> dict:
    role_pack = plan.get("role_pack") or {}
    board["active_brief"] = {
        "stage": stage,
        "material_type": plan.get("material_type") or "",
        "mode": plan.get("mode") or "",
        "purpose": plan.get("purpose") or "",
        "target_surface": plan.get("target_surface") or "",
        "product_truth_expression": plan.get("product_truth_expression") or "",
        "abstraction_level": plan.get("abstraction_level") or "",
        "system_mechanic": plan.get("system_mechanic") or "",
        "preserve": plan.get("preserve") or [],
        "push": plan.get("push") or [],
        "ban": plan.get("ban") or [],
        "prompt_seed": plan.get("prompt_seed") or "",
        "path": path,
    }
    board["reference_assignments"] = {
        item.get("role") or "reference": {
            "source_key": item.get("source_key") or "",
            "source_name": item.get("source_name") or "",
            "path": item.get("path") or "",
            "translation": item.get("translation") or {},
        }
        for item in (role_pack.get("selected_roles") or [])
    }
    return board


def persist_plan_draft_to_blackboard(brand_dir: Path, profile: dict, identity: dict, draft: dict, *, output_path: Path, workflow_id: str | None = None) -> Path:
    board = load_blackboard(brand_dir, profile, identity)
    plan = extract_plan_payload(draft)
    update_blackboard_active_brief(board, plan, stage="plan_draft", path=str(output_path))
    board["artifacts"]["latest_plan_draft"] = str(output_path)
    append_blackboard_decision(
        board,
        agent="brand_director",
        decision=f"Drafted {plan.get('material_type') or 'material'} brief with mechanic '{plan.get('system_mechanic') or 'n/a'}'.",
        confidence=0.72,
        data={"mode": plan.get("mode"), "missing_required_roles": ((draft.get("derived") or {}).get("missing_required_roles") or [])},
        workflow_id=workflow_id,
    )
    return save_blackboard(brand_dir, board)


def persist_plan_critique_to_blackboard(brand_dir: Path, profile: dict, identity: dict, critique: dict, *, output_path: Path, workflow_id: str | None = None) -> Path:
    board = load_blackboard(brand_dir, profile, identity)
    plan = extract_plan_payload(critique.get("plan") or {})
    if plan:
        update_blackboard_active_brief(board, plan, stage="plan_critique", path=critique.get("plan_path") or "")
    board["artifacts"]["latest_plan_critique"] = str(output_path)
    blocking = ((critique.get("checks") or {}).get("blocking") or [])
    append_blackboard_decision(
        board,
        agent="critic_agent",
        decision=f"Critiqued {plan.get('material_type') or 'material'} plan: {'blocking issues remain' if blocking else 'ready for scratchpad build'}.",
        confidence=0.84 if not blocking else 0.9,
        severity="P1" if blocking else "P2",
        data={
            "blocking": blocking,
            "plan_errors": ((critique.get("plan_validation") or {}).get("errors") or []),
            "prompt_issues": ((critique.get("prompt_review") or {}).get("issues") or []),
        },
        workflow_id=workflow_id,
    )
    return save_blackboard(brand_dir, board)


def persist_generation_scratchpad_to_blackboard(brand_dir: Path, profile: dict, identity: dict, payload: dict, *, output_path: Path, workflow_id: str | None = None) -> Path:
    board = load_blackboard(brand_dir, profile, identity)
    plan = payload.get("plan") or {}
    if plan:
        update_blackboard_active_brief(board, plan, stage="generation_scratchpad", path=payload.get("plan_path") or "")
    board["artifacts"]["latest_generation_scratchpad"] = str(output_path)
    append_blackboard_decision(
        board,
        agent="visual_composer",
        decision=f"Built generation scratchpad for {payload.get('material_type') or 'material'} using {((payload.get('execution') or {}).get('model') or 'unknown model')}.",
        confidence=0.76,
        severity="P1" if ((payload.get("checks") or {}).get("blocking") or []) else "P3",
        data={
            "workflow_mode": payload.get("workflow_mode"),
            "blocking": ((payload.get("checks") or {}).get("blocking") or []),
            "warnings": ((payload.get("checks") or {}).get("warnings") or []),
        },
        workflow_id=workflow_id,
    )
    return save_blackboard(brand_dir, board)


def persist_generated_asset_to_blackboard(
    brand_dir: Path,
    profile: dict,
    identity: dict,
    *,
    version_id: str,
    entry: dict,
    scratchpad_path: str,
    auto_review_path: str = "",
    critic_summary: dict | None = None,
    workflow_id: str | None = None,
) -> Path:
    board = load_blackboard(brand_dir, profile, identity)
    board["artifacts"]["latest_generated_version"] = version_id
    if auto_review_path:
        board["artifacts"]["latest_auto_review"] = auto_review_path
    history = board.setdefault("generated_assets", [])
    history.append(
        {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "workflow_id": workflow_id or "",
            "version": version_id,
            "material_type": entry.get("material_type") or "",
            "files": entry.get("files") or [],
            "scratchpad_path": scratchpad_path,
            "auto_review_path": auto_review_path,
            "critic_summary": critic_summary or {},
        }
    )
    board["generated_assets"] = history[-20:]
    append_blackboard_decision(
        board,
        agent="brand_director",
        decision=f"Generated {version_id} ({entry.get('material_type') or 'material'}) and queued critic review.",
        confidence=0.7,
        severity="P2" if (critic_summary or {}).get("p1") else "P3",
        data={"scratchpad_path": scratchpad_path, "auto_review_path": auto_review_path},
        workflow_id=workflow_id,
    )
    return save_blackboard(brand_dir, board)


for _key, _value in load_env_values().items():
    os.environ.setdefault(_key, _value)


def get_legacy_brand_dir() -> Path:
    if os.environ.get("BRAND_DIR"):
        return Path(os.environ["BRAND_DIR"]).expanduser()
    if os.environ.get("LOGO_DIR"):
        return Path(os.environ["LOGO_DIR"]).expanduser()
    base = Path(os.environ.get("SCREENSHOTS_DIR", ".")).expanduser()
    return base / "brand-materials"


def get_brand_gen_dir() -> Path | None:
    override = os.environ.get("BRAND_GEN_DIR")
    if override:
        return Path(override).expanduser()
    candidate = REPO_ROOT / ".brand-gen"
    if candidate.exists():
        return candidate
    return None


def brand_gen_config_path(brand_gen_dir: Path | None = None) -> Path | None:
    resolved = brand_gen_dir or get_brand_gen_dir()
    if not resolved:
        return None
    return resolved / "config.json"


def load_brand_gen_config(brand_gen_dir: Path | None = None) -> dict:
    path = brand_gen_config_path(brand_gen_dir)
    if not path or not path.exists():
        return dict(DEFAULT_BRAND_GEN_CONFIG)
    try:
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise ValueError("config is not an object")
    except Exception:
        warn(f"Corrupted brand-gen config at {path}; using defaults.")
        return dict(DEFAULT_BRAND_GEN_CONFIG)
    merged = dict(DEFAULT_BRAND_GEN_CONFIG)
    merged.update(value)
    return merged


def save_brand_gen_config(config: dict, brand_gen_dir: Path | None = None) -> Path:
    resolved = brand_gen_dir or get_brand_gen_dir() or (REPO_ROOT / ".brand-gen")
    resolved.mkdir(parents=True, exist_ok=True)
    path = resolved / "config.json"
    payload = dict(DEFAULT_BRAND_GEN_CONFIG)
    payload.update(config or {})
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def get_sources_registry_path(brand_gen_dir: Path | None = None) -> Path:
    resolved = brand_gen_dir or get_brand_gen_dir()
    candidate = resolved / "sources" / "brand_example_sources.json" if resolved else None
    if candidate and candidate.exists():
        return candidate
    return REPO_ROOT / "data" / "brand_example_sources.json"


def get_inspiration_index_path(brand_gen_dir: Path | None = None) -> Path | None:
    resolved = brand_gen_dir or get_brand_gen_dir()
    if not resolved:
        return None
    return resolved / "inspiration" / "index.json"


def list_brand_dirs(brand_gen_dir: Path | None = None) -> list[Path]:
    resolved = brand_gen_dir or get_brand_gen_dir()
    if not resolved:
        return []
    brands_dir = resolved / "brands"
    if not brands_dir.exists():
        return []
    return sorted([path for path in brands_dir.iterdir() if path.is_dir()])


def resolve_active_brand_key(brand_gen_dir: Path | None = None) -> str | None:
    config = load_brand_gen_config(brand_gen_dir)
    active = config.get("active")
    return str(active) if active else None


def resolve_active_session_key(brand_gen_dir: Path | None = None) -> str | None:
    config = load_brand_gen_config(brand_gen_dir)
    active = config.get("activeSession")
    return str(active) if active else None


def get_sessions_dir(brand_gen_dir: Path | None = None) -> Path | None:
    resolved = brand_gen_dir or get_brand_gen_dir()
    if not resolved:
        return None
    return resolved / "sessions"


def explicit_legacy_brand_override() -> Path | None:
    if os.environ.get("BRAND_DIR"):
        return Path(os.environ["BRAND_DIR"]).expanduser()
    if os.environ.get("LOGO_DIR"):
        return Path(os.environ["LOGO_DIR"]).expanduser()
    if os.environ.get("SCREENSHOTS_DIR"):
        return Path(os.environ["SCREENSHOTS_DIR"]).expanduser() / "brand-materials"
    return None


def infer_brand_key_from_path(path: Path | None, brand_gen_dir: Path | None = None) -> str | None:
    resolved = brand_gen_dir or get_brand_gen_dir()
    if not resolved or not path:
        return None
    try:
        rel = path.resolve().relative_to((resolved / "brands").resolve())
    except Exception:
        return None
    parts = rel.parts
    return parts[0] if parts else None


def resolve_context_brand_key(
    *,
    brand_dir: Path | None = None,
    profile_path: Path | None = None,
    identity_path: Path | None = None,
    profile: dict | None = None,
    identity: dict | None = None,
    brand_gen_dir: Path | None = None,
) -> str | None:
    inferred = infer_brand_key_from_path(
        profile_path if profile_path and profile_path.exists() else identity_path if identity_path and identity_path.exists() else None,
        brand_gen_dir,
    )
    if inferred:
        return inferred
    for payload in (profile or {}, identity or {}):
        session_context = payload.get("session_context") or {}
        seeded_from = str(session_context.get("seeded_from_brand") or "").strip()
        if seeded_from:
            return seeded_from
    inferred_brand_dir = None
    if brand_dir:
        inferred_brand_dir = brand_dir
    elif profile_path and profile_path.exists():
        inferred_brand_dir = profile_path.parent
    elif identity_path and identity_path.exists():
        inferred_brand_dir = identity_path.parent
    if inferred_brand_dir:
        board_path = inferred_brand_dir / "blackboard.json"
        if board_path.exists():
            try:
                board = json.loads(board_path.read_text())
                for decision in reversed(board.get("decisions") or []):
                    data = decision.get("data") or {}
                    seeded_from = str(data.get("seeded_from_brand") or "").strip()
                    if seeded_from:
                        return seeded_from
            except Exception:
                pass
    return resolve_active_brand_key(brand_gen_dir)


def resolve_active_brand_dir(brand_gen_dir: Path | None = None, *, strict: bool = False) -> Path:
    resolved = brand_gen_dir or get_brand_gen_dir()
    active_session = resolve_active_session_key(resolved)
    if resolved and active_session:
        session_dir = resolved / "sessions" / active_session / "brand-materials"
        if session_dir.exists():
            return session_dir
        message = f"Active testing session '{active_session}' not found under {resolved / 'sessions'}."
        if strict:
            raise SystemExit(message)
        warn(message)
    active = resolve_active_brand_key(resolved)
    if resolved and active:
        active_dir = resolved / "brands" / active
        if active_dir.exists():
            return active_dir
        message = f"Active brand '{active}' not found under {resolved / 'brands'}."
        if strict:
            raise SystemExit(message)
        warn(message)
    legacy = explicit_legacy_brand_override()
    if legacy is not None:
        return legacy
    message = (
        "No active brand context. Start with `brand_iterate.py start-testing --session-name <name>` "
        "for a working session, or switch to a saved brand with `brand_iterate.py use <brand>`."
    )
    raise SystemExit(message)


def get_brand_dir() -> Path:
    return resolve_active_brand_dir(strict=True)


def get_manifest_path() -> Path:
    return get_brand_dir() / "manifest.json"


def load_manifest() -> dict:
    path = get_manifest_path()
    if path.exists():
        return json.loads(path.read_text())
    return {"versions": {}, "locked_fragments": [], "reference_versions": []}


def save_manifest(manifest: dict) -> None:
    get_manifest_path().write_text(json.dumps(manifest, indent=2) + "\n")


def next_version_num(manifest: dict) -> int:
    nums = []
    for key in manifest["versions"]:
        match = re.match(r"v(\d+)", key)
        if match:
            nums.append(int(match.group(1)))
    for path in get_brand_dir().glob("v*"):
        match = re.match(r"v(\d+)", path.stem)
        if match:
            nums.append(int(match.group(1)))
    return max(nums, default=0) + 1


def normalize_image_args(images) -> list[str]:
    if not images:
        return []
    if isinstance(images, str):
        return [images]
    flattened: list[str] = []
    for image in images:
        if isinstance(image, (list, tuple)):
            flattened.extend(image)
        else:
            flattened.append(image)
    return flattened


def expand_reference_paths(images, reference_dir=None) -> list[Path]:
    refs: list[Path] = []
    for image in normalize_image_args(images):
        path = Path(image).expanduser()
        if not path.exists():
            print(f"ERROR: Reference asset not found: {image}", file=sys.stderr)
            sys.exit(1)
        if path.suffix.lower() not in SUPPORTED_MEDIA_EXTS:
            print(f"ERROR: Unsupported reference asset type: {image}", file=sys.stderr)
            sys.exit(1)
        refs.append(path.resolve())

    if reference_dir:
        ref_dir = Path(reference_dir).expanduser()
        if not ref_dir.exists() or not ref_dir.is_dir():
            print(f"ERROR: Reference directory not found: {reference_dir}", file=sys.stderr)
            sys.exit(1)
        dir_refs = sorted(
            path.resolve()
            for path in ref_dir.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_MEDIA_EXTS
        )
        if not dir_refs:
            print(f"ERROR: No supported reference assets found in: {reference_dir}", file=sys.stderr)
            sys.exit(1)
        refs.extend(dir_refs)

    deduped: list[Path] = []
    seen = set()
    for ref in refs:
        key = str(ref)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ref)
    return deduped


def stage_reference_assets(version_id: str, reference_paths: list[Path], brand_dir: Path) -> list[str]:
    if not reference_paths:
        return []
    references_dir = brand_dir / "references"
    references_dir.mkdir(parents=True, exist_ok=True)
    staged: list[str] = []
    for idx, source in enumerate(reference_paths, start=1):
        dest_name = f"{version_id}-ref-{idx:02d}{source.suffix.lower()}"
        dest = references_dir / dest_name
        shutil.copy2(source, dest)
        staged.append(str(Path("references") / dest_name))
    return staged


def resolve_workflow_mode(requested_mode: str, reference_paths: list[Path]) -> str:
    if requested_mode != "auto":
        return requested_mode
    return "reference" if reference_paths else "inspiration"


def normalize_material_type(material_type: str) -> str:
    key = (material_type or "logo").strip().lower()
    if key not in MATERIAL_CONFIG:
        available = ", ".join(sorted(MATERIAL_CONFIG))
        print(f"ERROR: Unknown material type '{material_type}'.", file=sys.stderr)
        print(f"Available: {available}", file=sys.stderr)
        sys.exit(1)
    return key


def resolve_generation_mode(material_type: str, requested_mode: str) -> str:
    if requested_mode != "auto":
        return requested_mode
    return MATERIAL_CONFIG[material_type]["generation_mode"]


def resolve_default_model(
    material_type: str,
    generation_mode: str,
    workflow_mode: str,
    reference_paths: list[Path],
    material_prompt_key: str = "",
    has_motion_reference: bool = False,
) -> str:
    if generation_mode == "video" and has_motion_reference:
        return "kling-v2.6-motion-control"
    if generation_mode == "image" and reference_paths and workflow_mode in {"reference", "hybrid"}:
        return "nano-banana-2"
    if material_type in {"pattern-system", "motif-system", "sticker-family", "badge-family", "icon-family"}:
        return MATERIAL_CONFIG[material_type]["default_model"]
    return MATERIAL_CONFIG[material_type]["default_model"]


def model_supports_reference_images(model_config: dict, generation_mode: str) -> bool:
    field_map = model_config.get("field_map") or {}
    if generation_mode == "image":
        return bool(field_map.get("image"))
    return bool(field_map.get("start_image"))


def model_supports_reference_tags(model_config: dict) -> bool:
    field_map = model_config.get("field_map") or {}
    return bool(field_map.get("image_tags"))


def model_supports_motion_reference(model_config: dict) -> bool:
    field_map = model_config.get("field_map") or {}
    return bool(field_map.get("motion_reference"))


def resolve_default_aspect_ratio(material_type: str, requested_aspect_ratio: str | None, model_config: dict) -> str:
    if requested_aspect_ratio:
        return requested_aspect_ratio
    material_default = MATERIAL_CONFIG.get(material_type, {}).get("default_aspect_ratio")
    if material_default:
        return material_default
    return model_config.get("defaults", {}).get("aspect_ratio", "")


def infer_material_type_from_filename(filename: str) -> str:
    lower = filename.lower()
    for key in [
        "logo-animation",
        "feature-animation",
        "short-video",
        "motion-loop",
        "landing-hero",
        "product-banner",
        "hero-banner",
        "browser-illustration",
        "feature-illustration",
        "product-visual",
        "linkedin-feed-portrait",
        "linkedin-feed-square",
        "linkedin-feed",
        "linkedin-card",
        "x-feed-portrait",
        "x-feed-square",
        "x-feed",
        "x-card",
        "og-card",
        "banner",
        "poster",
        "wordmark",
        "icon",
        "social",
        "gif",
        "animation",
        "lockup",
    ]:
        if key in lower:
            return key
    suffix = Path(filename).suffix.lower()
    if suffix in SUPPORTED_VIDEO_EXTS:
        return "short-video"
    if suffix == ".gif":
        return "gif"
    return "logo"


def media_tag(path: Path) -> str:
    ext = path.suffix.lower()
    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    if ext in SUPPORTED_VIDEO_EXTS:
        b64 = base64.b64encode(path.read_bytes()).decode()
        return (
            f'<video controls loop muted playsinline preload="metadata">'
            f'<source src="data:{mime};base64,{b64}" type="{mime}"></video>'
        )
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f'<img src="data:{mime};base64,{b64}" alt="{path.name}">'


def convert_video_to_gif(video_path: Path) -> Path | None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("WARNING: ffmpeg not found; skipping GIF conversion.", file=sys.stderr)
        return None
    gif_path = video_path.with_suffix(".gif")
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(video_path),
        "-vf",
        "fps=12,scale=960:-1:flags=lanczos",
        str(gif_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("WARNING: GIF conversion failed.", file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return None
    print(f"Converted GIF: {gif_path.name}")
    return gif_path


def run_child_script(script: Path, args: list[str]) -> None:
    env = build_env()
    result = subprocess.run([sys.executable, str(script)] + args, env=env, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)
    if result.stderr:
        print(result.stderr, file=sys.stderr)


def cmd_bootstrap(args):
    manifest = load_manifest()
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    added = 0
    for path in sorted(brand_dir.iterdir()):
        match = re.match(r"(v\d+)", path.stem)
        if not match or path.suffix.lower() not in SUPPORTED_MEDIA_EXTS:
            continue
        vid = match.group(1)
        material_type = infer_material_type_from_filename(path.name)
        generation_mode = MATERIAL_CONFIG.get(material_type, {}).get("generation_mode", "image")
        if vid in manifest["versions"]:
            entry = manifest["versions"][vid]
            if path.name not in entry.get("files", []):
                entry.setdefault("files", []).append(path.name)
            continue
        manifest["versions"][vid] = {
            "prompt": "",
            "model": "",
            "mode": "",
            "material_type": material_type,
            "generation_mode": generation_mode,
            "aspect_ratio": "",
            "duration": None,
            "tag": re.sub(r"^v\d+-?", "", path.stem),
            "files": [path.name],
            "reference_images": [],
            "reference_count": 0,
            "reference_dir": "",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(path.stat().st_mtime)),
            "score": None,
            "notes": "",
            "status": None,
        }
        added += 1
    save_manifest(manifest)
    print(f"Bootstrap complete: {added} new versions added, {len(manifest['versions'])} total in manifest")


def build_plan_critique_payload(args, *, brand_dir: Path, wrapper: dict, plan: dict) -> dict:
    report = validate_material_plan_dict(plan)
    preview_args = argparse.Namespace(
        prompt=getattr(args, "prompt", None),
        plan=str(Path(args.plan).expanduser().resolve()) if getattr(args, "plan", None) else "",
        material_type=getattr(args, "material_type", None),
        generation_mode=getattr(args, "generation_mode", "auto"),
        mode=getattr(args, "mode", "auto"),
        model=getattr(args, "model", None),
        aspect_ratio=getattr(args, "aspect_ratio", None),
        resolution=getattr(args, "resolution", None),
        duration=getattr(args, "duration", None),
        tag=getattr(args, "tag", None),
        image=getattr(args, "image", None),
        reference_dir=getattr(args, "reference_dir", None),
        motion_reference=getattr(args, "motion_reference", None),
        motion_mode=getattr(args, "motion_mode", None),
        character_orientation=getattr(args, "character_orientation", None),
        keep_original_sound=getattr(args, "keep_original_sound", False),
        preset=getattr(args, "preset", None),
        negative_prompt=getattr(args, "negative_prompt", None),
        style=getattr(args, "style", None),
        make_gif=getattr(args, "make_gif", False),
        profile=getattr(args, "profile", None),
        identity=getattr(args, "identity", None),
        disable_brand_guardrails=getattr(args, "disable_brand_guardrails", False),
        allow_blocking=True,
    )
    scratchpad_preview = assemble_generation_scratchpad(preview_args, brand_dir=brand_dir, plan_wrapper=wrapper, plan=plan)
    return {
        "schema_type": "plan_critique",
        "schema_version": 1,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "state": {
            "status": "needs_work" if (report.get("errors") or (scratchpad_preview.get("checks") or {}).get("blocking")) else "approved_for_scratchpad",
            "owner": "critic_agent",
            "next_owner": "visual_composer",
        },
        "plan_path": str(Path(args.plan).expanduser().resolve()),
        "plan": plan,
        "plan_validation": report,
        "prompt_review": scratchpad_preview.get("prompt_review") or {},
        "checks": scratchpad_preview.get("checks") or {},
        "next_step": "Run build-generation-scratchpad when blocking issues are fixed.",
    }


def cmd_critique_plan(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    wrapper, plan = load_plan_payload(Path(args.plan).expanduser().resolve())
    workflow_id = resolve_workflow_id(wrapper, plan)
    critique = build_plan_critique_payload(args, brand_dir=brand_dir, wrapper=wrapper, plan=plan)
    critique["workflow_id"] = workflow_id
    report = critique["plan_validation"]
    output_path = Path(args.output).expanduser().resolve() if args.output else save_plan_critique(
        brand_dir,
        critique,
        label=f"{plan.get('material_type','material')}-{plan.get('mode','mode')}-critique",
    )
    if args.output:
        output_path.write_text(json.dumps(critique, indent=2) + "\n")
    profile_path, identity_path, profile, identity = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))
    persist_plan_critique_to_blackboard(brand_dir, profile, identity, critique, output_path=output_path, workflow_id=workflow_id)
    has_blocking = bool((critique.get("checks") or {}).get("blocking"))
    if args.format == "json":
        print(json.dumps({**critique, "output": str(output_path)}, indent=2))
        if has_blocking:
            sys.exit(1)
        return
    print(f"Plan critique: {output_path}\n")
    print(f"Status: {'ok' if report['ok'] and not critique['checks'].get('blocking') else 'needs work'}")
    if report['errors']:
        print("\nPlan errors:")
        for item in report['errors']:
            print(f"- {item}")
    if report['warnings']:
        print("\nPlan warnings:")
        for item in report['warnings']:
            print(f"- {item}")
    prompt_review = critique['prompt_review']
    if prompt_review.get('issues'):
        print("\nPrompt issues:")
        for item in prompt_review['issues']:
            print(f"- {item}")
    if prompt_review.get('recommendations'):
        print("\nRecommendations:")
        for item in prompt_review['recommendations']:
            print(f"- {item}")
    if has_blocking:
        print("\nBlocking issues:")
        for item in critique['checks']['blocking']:
            print(f"- {item}")
        print("\n⛔ Critique has blocking issues. Fix the plan and re-run critique-plan before proceeding.")
        print("   The pipeline will not continue to build-generation-scratchpad until blocking issues are resolved.")
        sys.exit(1)


def cmd_build_generation_scratchpad(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    wrapper, plan = load_plan_payload(Path(args.plan).expanduser().resolve()) if getattr(args, "plan", None) else ({}, {})
    workflow_id = resolve_workflow_id(wrapper, plan)
    payload = assemble_generation_scratchpad(args, brand_dir=brand_dir, plan_wrapper=wrapper, plan=plan)
    payload["workflow_id"] = workflow_id
    critique = build_plan_critique_payload(args, brand_dir=brand_dir, wrapper=wrapper, plan=plan) if plan else {}
    if critique:
        critique["workflow_id"] = workflow_id
    payload["plan_critique"] = critique
    if critique:
        payload["checks"]["blocking"] = dedupe_keep_order(list(payload["checks"].get("blocking") or []) + list((critique.get("checks") or {}).get("blocking") or []))
        payload["checks"]["warnings"] = dedupe_keep_order(list(payload["checks"].get("warnings") or []) + list((critique.get("checks") or {}).get("warnings") or []))
    output_path = Path(args.output).expanduser().resolve() if args.output else save_generation_scratchpad(
        brand_dir,
        payload,
        label=f"{payload.get('material_type','material')}-{payload.get('workflow_mode','mode')}-generation",
    )
    if args.output:
        output_path.write_text(json.dumps(payload, indent=2) + "\n")
    profile_path, identity_path, profile, identity = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))
    persist_generation_scratchpad_to_blackboard(brand_dir, profile, identity, payload, output_path=output_path, workflow_id=workflow_id)
    if args.format == "json":
        print(json.dumps({**payload, "output": str(output_path)}, indent=2))
    else:
        print(f"Generation scratchpad: {output_path}\n")
        print(f"Material: {payload.get('material_type')}\nModel: {(payload.get('execution') or {}).get('model')}\nMode: {payload.get('workflow_mode')}")
        if (payload.get('checks') or {}).get('blocking'):
            print("\nBlocking issues:")
            for item in (payload.get('checks') or {}).get('blocking') or []:
                print(f"- {item}")
        if (payload.get('checks') or {}).get('warnings'):
            print("\nWarnings:")
            for item in (payload.get('checks') or {}).get('warnings') or []:
                print(f"- {item}")
    if (payload.get('checks') or {}).get('blocking') and not getattr(args, 'allow_blocking', False):
        sys.exit(1)


def cmd_generate(args):
    if not getattr(args, "scratchpad", None):
        print("ERROR: generate now requires --scratchpad. Build one first with build-generation-scratchpad.", file=sys.stderr)
        sys.exit(1)
    scratchpad_path = Path(args.scratchpad).expanduser().resolve()
    payload = load_json_file(scratchpad_path)
    payload["_scratchpad_path"] = str(scratchpad_path)

    max_iterations = getattr(args, "max_iterations", 1) or 1
    max_iterations = min(max(max_iterations, 1), 3)
    skip_vlm = getattr(args, "skip_vlm", False)

    all_vids: list[str] = []
    current_payload = payload

    for iteration in range(max_iterations):
        iteration_label = f" (iteration {iteration + 1}/{max_iterations})" if max_iterations > 1 else ""
        print(f"\n{'=' * 60}\nGenerating{iteration_label}...\n{'=' * 60}")

        vid = execute_generation_scratchpad(current_payload)
        all_vids.append(vid)

        # Skip VLM critique on last iteration or if disabled
        if skip_vlm or iteration >= max_iterations - 1:
            break

        # --- VLM Critique (Hole 2) ---
        brand_dir = Path(current_payload["brand_dir"]).expanduser().resolve()
        manifest = load_manifest()
        entry = manifest["versions"].get(vid, {})
        image_files = [brand_dir / f for f in entry.get("files", []) if Path(f).suffix.lower() in SUPPORTED_IMAGE_EXTS]
        if not image_files or not image_files[0].exists():
            print("No image file to VLM-critique; stopping iteration loop.")
            break

        brief = current_payload.get("effective_prompt") or ""
        board = load_blackboard(brand_dir)
        brand_dna = board.get("brand_dna") or {}

        print(f"\nRunning VLM critique on {vid}...")
        vlm_result = run_vlm_critique(image_files[0], brief, brand_dna)

        # Save VLM critique alongside the auto-review
        vlm_path = brand_dir / "reviews" / f"{vid}-vlm-critique.json"
        vlm_path.parent.mkdir(parents=True, exist_ok=True)
        vlm_path.write_text(json.dumps(vlm_result, indent=2) + "\n")
        manifest["versions"][vid]["vlm_critique_path"] = str(vlm_path)
        manifest["versions"][vid]["vlm_critique"] = {
            "approved": vlm_result.get("approved", False),
            "p1_count": len(vlm_result.get("p1") or []),
            "p2_count": len(vlm_result.get("p2") or []),
            "palette_match": vlm_result.get("palette_match", 0),
            "logo_visible": vlm_result.get("logo_visible", False),
            "vlm_available": vlm_result.get("vlm_available", False),
        }
        save_manifest(manifest)

        # Update blackboard with VLM critique decision
        profile_path = current_payload.get("profile_path")
        identity_path = current_payload.get("identity_path")
        _, _, profile, identity = load_brand_memory(brand_dir, profile_path, identity_path)
        bb = load_blackboard(brand_dir, profile, identity)
        append_blackboard_decision(
            bb,
            agent="critic_agent",
            decision=f"VLM critique of {vid}: {'approved' if vlm_result.get('approved') else 'needs refinement'} "
                     f"(P1: {len(vlm_result.get('p1') or [])}, palette: {vlm_result.get('palette_match', 'n/a')})",
            confidence=0.85 if vlm_result.get("vlm_available") else 0.3,
            severity="P1" if vlm_result.get("p1") else ("P2" if vlm_result.get("p2") else None),
            data={"vlm_critique_path": str(vlm_path), "approved": vlm_result.get("approved", False)},
        )
        save_blackboard(brand_dir, bb)

        if not vlm_result.get("vlm_available"):
            print("VLM not available; stopping iteration loop.")
            break

        if vlm_result.get("approved"):
            print(f"✅ VLM approved {vid}. No further iterations needed.")
            break

        # --- Refine prompt for next iteration (Hole 3) ---
        print(f"🔄 VLM flagged issues on {vid}. Refining prompt for iteration {iteration + 2}...")
        if vlm_result.get("p1"):
            print(f"   P1 issues: {'; '.join(str(i) for i in vlm_result['p1'][:3])}")
        if vlm_result.get("refinement_suggestion"):
            print(f"   Suggestion: {vlm_result['refinement_suggestion']}")

        refined_prompt = refine_prompt_from_vlm_critique(
            current_payload.get("effective_prompt") or "",
            vlm_result,
        )
        # Build a new payload with the refined prompt for the next iteration
        current_payload = dict(current_payload)
        current_payload["effective_prompt"] = refined_prompt
        current_payload["_iteration"] = iteration + 1
        current_payload["_previous_vid"] = vid
        current_payload["_vlm_critique"] = vlm_result

    # Compare all generated versions
    cmd_compare(argparse.Namespace(versions=all_vids, favorites=False, top=None, output=None))


def cmd_pipeline(args):
    from pipeline_runner import PipelineRunner  # type: ignore

    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    _, _, profile, identity = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))

    runner = PipelineRunner(
        brand_dir=brand_dir,
        profile=profile,
        identity=identity,
        max_iterations=getattr(args, "max_iterations", 1) or 1,
        skip_vlm=bool(getattr(args, "skip_vlm", False)),
        skip_route=bool(getattr(args, "skip_route", False)),
    )
    result = runner.run(args)
    payload = result.to_dict()
    if getattr(args, "format", "json") == "json":
        print(json.dumps(payload, indent=2))
        if result.stopped_at not in {"complete", "critique"}:
            sys.exit(1)
        return

    print("Pipeline result\n")
    print(f"Workflow ID: {result.workflow_id}")
    print(f"Stopped at: {result.stopped_at or 'unknown'}")
    print(f"Reason: {result.stop_reason or 'n/a'}")
    if result.route:
        print(f"Route: {result.route.route_key} ({result.route.method}, score={result.route.score:.2f})")
    if result.plan_draft and result.plan_draft.output_path:
        print(f"Plan draft: {result.plan_draft.output_path}")
    if result.critique and result.critique.output_path:
        print(f"Critique: {result.critique.output_path}")
    if result.scratchpad and result.scratchpad.output_path:
        print(f"Scratchpad: {result.scratchpad.output_path}")
    if result.result:
        print(f"Generated: {result.result.version_id}")
        if result.result.image_paths:
            print(f"Files: {', '.join(result.result.image_paths)}")
    if result.stopped_at not in {"complete", "critique"}:
        sys.exit(1)


def cmd_feedback(args):
    manifest = load_manifest()
    brand_dir = get_brand_dir()
    vid = args.version
    if vid not in manifest["versions"]:
        print(f"ERROR: {vid} not in manifest. Run 'bootstrap' first?", file=sys.stderr)
        sys.exit(1)
    entry = manifest["versions"][vid]
    if args.score is not None:
        entry["score"] = args.score
    if args.notes:
        entry["notes"] = (entry["notes"] + "\n" if entry.get("notes") else "") + args.notes
    if args.status:
        entry["status"] = args.status
    if args.prompt:
        entry["prompt"] = args.prompt
    if args.status == "favorite" and vid not in manifest.get("reference_versions", []):
        manifest.setdefault("reference_versions", []).append(vid)
    if args.lock:
        for frag in args.lock:
            if frag not in manifest.get("locked_fragments", []):
                manifest.setdefault("locked_fragments", []).append(frag)
    save_manifest(manifest)
    memory = load_iteration_memory(brand_dir)
    memory = capture_feedback_into_iteration_memory(memory, vid, entry, args.notes, args.score, args.status)
    save_iteration_memory(brand_dir, memory)
    star = "★" * (entry.get("score") or 0) + "☆" * (5 - (entry.get("score") or 0))
    status_icon = {"favorite": "♥", "rejected": "✗"}.get(entry.get("status"), "")
    print(f"{vid} {star} {status_icon} - updated")


def cmd_show(args):
    manifest = load_manifest()
    versions = manifest["versions"]
    if args.version:
        version = versions.get(args.version)
        if not version:
            print(f"Not found: {args.version}")
            sys.exit(1)
        payload = {
            "version": args.version,
            "entry": version,
            "summary": {
                "total_versions": len(versions),
                "scored_versions": sum(1 for v in versions.values() if v.get("score") is not None),
                "favorites": sum(1 for v in versions.values() if v.get("status") == "favorite"),
            },
        }
        print(json.dumps(payload, indent=2))
        return

    items = list(versions.items())
    filter_mode = "all"
    if args.favorites:
        items = [(k, v) for k, v in items if v.get("status") == "favorite"]
        filter_mode = "favorites"
    elif args.top:
        items = [(k, v) for k, v in items if v.get("score")]
        items.sort(key=lambda x: (-(x[1].get("score") or 0), -_version_sort_key(x[0])))
        items = items[: args.top]
        filter_mode = "top"
    elif args.latest:
        items = sorted(items, key=lambda x: _version_sort_key(x[0]), reverse=True)[: args.latest]
        filter_mode = "latest"
    else:
        items = sorted(items, key=lambda x: _version_sort_key(x[0]))
    if not items:
        print("No versions match filter.")
        return

    if args.format == "json":
        payload = {
            "filter": {
                "mode": filter_mode,
                "favorites": bool(args.favorites),
                "top": args.top,
                "latest": args.latest,
            },
            "summary": {
                "total_versions": len(versions),
                "matched_versions": len(items),
                "scored_versions": sum(1 for v in versions.values() if v.get("score") is not None),
                "favorites": sum(1 for v in versions.values() if v.get("status") == "favorite"),
                "locked_fragments": list(manifest.get("locked_fragments") or []),
            },
            "versions": [{"version": vid, **version} for vid, version in items],
        }
        print(json.dumps(payload, indent=2))
        return

    print(f"{'VER':<8} {'SCORE':<8} {'STATUS':<10} {'TYPE':<20} {'GEN':<8} {'MODE':<12} {'REFS':<6} {'MODEL':<12} {'TAG':<16}")
    print("-" * 132)
    for vid, version in items:
        score = "★" * (version.get("score") or 0) if version.get("score") else "—"
        print(
            f"{vid:<8} {score:<8} {(version.get('status') or ''):<10} "
            f"{(version.get('material_type') or ''):<20} {(version.get('generation_mode') or ''):<8} "
            f"{(version.get('mode') or ''):<12} {str(version.get('reference_count') or 0):<6} "
            f"{(version.get('model') or ''):<12} {(version.get('tag') or '')[:16]:<16}"
        )
    print(f"\n{len(versions)} versions, {sum(1 for v in versions.values() if v.get('score') is not None)} scored, {sum(1 for v in versions.values() if v.get('status') == 'favorite')} favorites")
    if manifest.get("locked_fragments"):
        print(f"\nLocked fragments: {', '.join(manifest['locked_fragments'])}")

def _version_sort_key(vid: str) -> int:
    match = re.match(r"v(\d+)", vid)
    return int(match.group(1)) if match else 0


def cmd_compare(args):
    manifest = load_manifest()
    brand_dir = get_brand_dir()
    if args.favorites:
        vids = [k for k, v in manifest["versions"].items() if v.get("status") == "favorite"]
    elif args.top:
        scored = [(k, v) for k, v in manifest["versions"].items() if v.get("score")]
        scored.sort(key=lambda x: -(x[1].get("score") or 0))
        vids = [k for k, _ in scored[: args.top]]
    else:
        vids = args.versions
    if not vids:
        print("No versions to compare. Specify versions or use --favorites/--top N")
        sys.exit(1)

    cards_html = []
    for vid in sorted(vids, key=_version_sort_key):
        version = manifest["versions"].get(vid)
        if not version:
            print(f"WARNING: {vid} not in manifest, skipping", file=sys.stderr)
            continue
        media_file = None
        preferred_exts = [".png", ".jpg", ".jpeg", ".gif", ".mp4", ".webm", ".mov", ".svg", ".webp"]
        for ext in preferred_exts:
            for name in version.get("files", []):
                fp = brand_dir / name
                if fp.exists() and fp.suffix.lower() == ext:
                    media_file = fp
                    break
            if media_file:
                break
        if not media_file:
            for name in version.get("files", []):
                fp = brand_dir / name
                if fp.exists():
                    media_file = fp
                    break
        media_html = media_tag(media_file) if media_file and media_file.exists() else '<div class="no-media">No media</div>'
        score = version.get("score")
        stars = ("★" * score + "☆" * (5 - score)) if score else "unscored"
        status = version.get("status") or ""
        prompt = (version.get("prompt") or "—").replace("<", "&lt;").replace(">", "&gt;")
        notes = (version.get("notes") or "").replace("<", "&lt;").replace(">", "&gt;")
        # Diagnostic fields
        prompt_len = version.get("prompt_char_count") or len(version.get("prompt") or "")
        workflow_id = version.get("workflow_id") or ""
        scratchpad_path = version.get("generation_scratchpad") or ""
        critic = version.get("critic_summary") or {}
        critic_issues = critic.get("issues") or []
        prompt_review = version.get("prompt_review") or {}
        pr_ok = prompt_review.get("ok", True)
        pr_warnings = prompt_review.get("warnings") or []
        ref_count = version.get("reference_count") or 0
        aspect = version.get("aspect_ratio") or ""
        # Build diagnostic HTML
        diag_parts = []
        diag_parts.append(f"prompt: {prompt_len} chars")
        diag_parts.append(f"refs: {ref_count}")
        if aspect:
            diag_parts.append(f"aspect: {aspect}")
        if workflow_id:
            diag_parts.append(f"wf: {workflow_id[:12]}")
        if not pr_ok:
            diag_parts.append(f"⚠ prompt review failed")
        if pr_warnings:
            diag_parts.append(f"⚠ {len(pr_warnings)} prompt warnings")
        if critic_issues:
            diag_parts.append(f"⚠ {len(critic_issues)} critic issues")
        diag_html = f'<div class="diag">{" · ".join(diag_parts)}</div>'
        # Critic issues detail
        critic_html = ""
        if critic_issues:
            escaped_issues = [str(i).replace("<", "&lt;").replace(">", "&gt;") for i in critic_issues[:3]]
            critic_html = '<div class="critic-issues">' + "<br>".join(f"• {i}" for i in escaped_issues) + '</div>'
        cards_html.append(f'''
    <div class="card {status}">
      <div class="media expandable" role="button" tabindex="0" aria-label="Expand {vid}" data-version="{vid}">
        <div class="expand-chip">Click to expand</div>
        {media_html}
      </div>
      <div class="meta">
        <div class="version">{vid} <span class="score">{stars}</span></div>
        <div class="info">{version.get('material_type','')} · {version.get('generation_mode','')} · {version.get('model','')}</div>
        {diag_html}
        {critic_html}
        <div class="prompt">{prompt}</div>
        {"<div class='notes'>" + notes + "</div>" if notes else ""}
      </div>
    </div>''')

    html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Brand Material Comparison</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ font-family: system-ui, -apple-system, sans-serif; background: #1a1a1a; color: #eee; margin: 2rem; }}
  body.modal-open {{ overflow: hidden; }}
  h1 {{ font-size: 1.5rem; font-weight: 600; margin-bottom: 0.4rem; }}
  .subhead {{ color: #9b9b9b; margin-bottom: 1.4rem; font-size: 0.92rem; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 1.5rem; }}
  .card {{ background: #2a2a2a; border-radius: 12px; overflow: hidden; transition: transform 0.15s, box-shadow 0.15s; box-shadow: 0 10px 24px rgba(0,0,0,0.18); }}
  .card:hover {{ transform: translateY(-2px); box-shadow: 0 14px 28px rgba(0,0,0,0.24); }}
  .media {{ position: relative; background: #111; }}
  .media.expandable {{ cursor: zoom-in; outline: none; }}
  .media.expandable:focus-visible {{ box-shadow: inset 0 0 0 2px #f5a623; }}
  .media img, .media video {{ width: 100%; display: block; background: #111; }}
  .media video {{ max-height: 420px; object-fit: contain; }}
  .expand-chip {{ position: absolute; top: 0.7rem; right: 0.7rem; z-index: 2; background: rgba(0,0,0,0.58); color: #fff; font-size: 0.72rem; padding: 0.35rem 0.55rem; border-radius: 999px; pointer-events: none; letter-spacing: 0.02em; }}
  .no-media {{ height: 220px; display: flex; align-items: center; justify-content: center; background: #333; color: #666; }}
  .meta {{ padding: 1rem; }}
  .version {{ font-size: 1.1rem; font-weight: 700; }}
  .score {{ color: #f5a623; font-size: 0.95rem; }}
  .info {{ font-size: 0.8rem; color: #888; margin-top: 0.25rem; }}
  .diag {{ font-size: 0.75rem; color: #7a7a7a; margin-top: 0.3rem; font-family: ui-monospace, 'SF Mono', monospace; }}
  .critic-issues {{ font-size: 0.75rem; color: #e8a040; margin-top: 0.3rem; line-height: 1.3; }}
  .prompt {{ font-size: 0.82rem; color: #aaa; margin-top: 0.5rem; line-height: 1.4; max-height: 6em; overflow-y: auto; }}
  .notes {{ font-size: 0.82rem; color: #8f8; margin-top: 0.5rem; font-style: italic; }}
  .card.favorite {{ border: 2px solid #f5a623; }}
  .card.rejected {{ opacity: 0.45; }}
  .lightbox {{ position: fixed; inset: 0; background: rgba(7,7,7,0.82); display: none; align-items: center; justify-content: center; padding: 2rem; z-index: 9999; }}
  .lightbox.open {{ display: flex; }}
  .lightbox-panel {{ position: relative; width: min(92vw, 1600px); max-height: 92vh; background: #111; border-radius: 18px; box-shadow: 0 32px 80px rgba(0,0,0,0.4); overflow: hidden; }}
  .lightbox-topbar {{ display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: 0.9rem 1rem; background: rgba(255,255,255,0.03); border-bottom: 1px solid rgba(255,255,255,0.08); }}
  .lightbox-title {{ font-size: 0.95rem; color: #ddd; }}
  .lightbox-actions {{ display: flex; gap: 0.75rem; align-items: center; }}
  .lightbox-close {{ appearance: none; border: 0; background: rgba(255,255,255,0.08); color: #fff; padding: 0.55rem 0.8rem; border-radius: 999px; cursor: pointer; font: inherit; }}
  .lightbox-media {{ display: grid; place-items: center; padding: 1rem; max-height: calc(92vh - 72px); overflow: auto; }}
  .lightbox-media img, .lightbox-media video {{ max-width: 100%; max-height: calc(92vh - 120px); width: auto; height: auto; display: block; background: #111; }}
</style></head>
<body>
<h1>Brand Material Comparison — {len(vids)} versions</h1>
<div class="subhead">Click any preview to expand it. Press Esc to close.</div>
<div class="grid">{"".join(cards_html)}</div>
<div class="lightbox" id="lightbox" aria-hidden="true">
  <div class="lightbox-panel" role="dialog" aria-modal="true" aria-label="Expanded media preview">
    <div class="lightbox-topbar">
      <div class="lightbox-title" id="lightbox-title">Preview</div>
      <div class="lightbox-actions">
        <button class="lightbox-close" id="lightbox-close" type="button">Close</button>
      </div>
    </div>
    <div class="lightbox-media" id="lightbox-media"></div>
  </div>
</div>
<script>
  const lightbox = document.getElementById('lightbox');
  const lightboxMedia = document.getElementById('lightbox-media');
  const lightboxTitle = document.getElementById('lightbox-title');
  const lightboxClose = document.getElementById('lightbox-close');

  function closeLightbox() {{
    lightbox.classList.remove('open');
    lightbox.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('modal-open');
    lightboxMedia.innerHTML = '';
  }}

  function openLightboxFrom(mediaEl) {{
    const version = mediaEl.dataset.version || 'Preview';
    const img = mediaEl.querySelector('img');
    const video = mediaEl.querySelector('video');
    lightboxMedia.innerHTML = '';
    lightboxTitle.textContent = version;
    if (img) {{
      const full = document.createElement('img');
      full.src = img.src;
      full.alt = img.alt || version;
      lightboxMedia.appendChild(full);
    }} else if (video) {{
      const full = document.createElement('video');
      full.src = video.currentSrc || (video.querySelector('source') && video.querySelector('source').src) || '';
      full.controls = true;
      full.autoplay = true;
      full.loop = true;
      full.muted = true;
      full.playsInline = true;
      lightboxMedia.appendChild(full);
    }} else {{
      return;
    }}
    lightbox.classList.add('open');
    lightbox.setAttribute('aria-hidden', 'false');
    document.body.classList.add('modal-open');
  }}

  document.querySelectorAll('.media.expandable').forEach((mediaEl) => {{
    mediaEl.addEventListener('click', () => openLightboxFrom(mediaEl));
    mediaEl.addEventListener('keydown', (event) => {{
      if (event.key === 'Enter' || event.key === ' ') {{
        event.preventDefault();
        openLightboxFrom(mediaEl);
      }}
    }});
  }});

  lightboxClose.addEventListener('click', closeLightbox);
  lightbox.addEventListener('click', (event) => {{
    if (event.target === lightbox) closeLightbox();
  }});
  document.addEventListener('keydown', (event) => {{
    if (event.key === 'Escape') closeLightbox();
  }});
</script>
</body></html>'''
    out = Path(args.output).expanduser() if args.output else brand_dir / "compare.html"
    out.write_text(html)
    print(f"Comparison board: {out} ({len(cards_html)} versions)")
    if sys.platform == "darwin":
        subprocess.run(["open", str(out)], check=False)


def cmd_diagnose(args):
    """Compare diagnostic metadata for two or more versions side-by-side."""
    manifest = load_manifest()
    vids = args.versions
    if not vids or len(vids) < 1:
        raise SystemExit("Specify at least one version to diagnose, e.g.: diagnose v14 v15")
    rows: list[dict] = []
    for vid in vids:
        v = manifest["versions"].get(vid)
        if not v:
            print(f"WARNING: {vid} not in manifest", file=sys.stderr)
            continue
        prompt_len = v.get("prompt_char_count") or len(v.get("prompt") or "")
        critic = v.get("critic_summary") or {}
        pr = v.get("prompt_review") or {}
        rows.append({
            "version": vid,
            "material_type": v.get("material_type") or "",
            "model": v.get("model") or "",
            "mode": v.get("mode") or "",
            "aspect_ratio": v.get("aspect_ratio") or "",
            "prompt_chars": prompt_len,
            "prompt_budget_ok": prompt_len <= 1800 if role_pack_material_key(v.get("material_type")) in INTERFACE_MATERIAL_KEYS else "n/a",
            "ref_count": v.get("reference_count") or 0,
            "refs": v.get("reference_images") or [],
            "workflow_id": v.get("workflow_id") or "",
            "scratchpad": v.get("generation_scratchpad") or "",
            "prompt_review_ok": pr.get("ok", True),
            "prompt_review_warnings": pr.get("warnings") or [],
            "critic_issues": critic.get("issues") or [],
            "score": v.get("score"),
            "notes": v.get("notes") or "",
            "status": v.get("status") or "",
            "raw_prompt_chars": len(v.get("raw_prompt") or ""),
            "prelude_chars": len(v.get("prompt_prelude") or ""),
        })
    if args.format == "json":
        print(json.dumps(rows, indent=2))
        return
    for row in rows:
        print(f"=== {row['version']} ===")
        print(f"  material: {row['material_type']}  model: {row['model']}  mode: {row['mode']}  aspect: {row['aspect_ratio']}")
        print(f"  prompt: {row['prompt_chars']} chars (raw: {row['raw_prompt_chars']}, prelude: {row['prelude_chars']})")
        if row['prompt_budget_ok'] != "n/a":
            print(f"  budget ok: {'✓' if row['prompt_budget_ok'] else '✗ OVER BUDGET'}")
        print(f"  refs: {row['ref_count']}  {row['refs']}")
        if row['workflow_id']:
            print(f"  workflow: {row['workflow_id']}")
        if row['scratchpad']:
            print(f"  scratchpad: {row['scratchpad']}")
        if not row['prompt_review_ok']:
            print(f"  ⚠ prompt review FAILED")
        if row['prompt_review_warnings']:
            for w in row['prompt_review_warnings']:
                print(f"    ⚠ {w}")
        if row['critic_issues']:
            for issue in row['critic_issues']:
                print(f"    ⚠ critic: {issue}")
        if row['score'] is not None:
            print(f"  score: {row['score']}/5")
        if row['notes']:
            print(f"  notes: {row['notes'][:200]}")
        if row['status']:
            print(f"  status: {row['status']}")
        print()


def cmd_evolve(args):
    manifest = load_manifest()
    scored = [(k, v) for k, v in manifest["versions"].items() if v.get("score") and v.get("prompt")]
    if not scored:
        print("No scored versions with prompts. Score some versions first.")
        sys.exit(1)
    scored.sort(key=lambda x: -(x[1]["score"] or 0))
    print("=== Brand Prompt Evolution Analysis ===\n")
    print("Top scoring versions:")
    for vid, version in scored[:5]:
        stars = "★" * version["score"]
        prompt = version["prompt"]
        print(f"  {vid} ({stars}) [{version.get('material_type','')}]: \"{prompt[:100]}{'...' if len(prompt) > 100 else ''}\"")
    low = [x for x in scored if x[1]["score"] <= 2]
    if low:
        print("\nLow scoring (avoid these patterns):")
        for vid, version in low[:3]:
            print(f"  {vid} ({'★' * version['score']}): \"{version['prompt'][:80]}\"")
            if version.get("notes"):
                print(f"    Notes: {version['notes'][:100]}")
    if manifest.get("locked_fragments"):
        print("\nLocked fragments (keep these):")
        for frag in manifest["locked_fragments"]:
            print(f"  - {frag}")
    print("\nUse 'feedback VERSION --lock \"fragment\"' to lock good prompt fragments.")


def cmd_inspire(args):
    if args.sources or args.clear or args.show or args.brand:
        return cmd_configure_inspiration(args)
    brand_dir = get_brand_dir()
    inspo_dir = brand_dir / "inspiration"
    inspo_dir.mkdir(parents=True, exist_ok=True)
    category = (args.category or "symbol").lower()
    url = args.url or INSPIRE_URLS.get(category, INSPIRE_URLS["symbol"])
    if args.list_only:
        files = sorted(inspo_dir.glob("*"))
        if not files:
            print(f"No inspiration files in {inspo_dir}")
            print(f"Browse {url} and save screenshots there.")
            return
        print(f"Inspiration assets ({len(files)}):")
        for path in files:
            print(f"  {path.name}")
        return
    print(f"Opening {url}")
    print(f"Save references to: {inspo_dir}/")
    print("Tips:")
    print("  - Use scripts/collect_inspiration.py for automated capture from Logo System or any URL")
    print("  - Capture references for logos, posters, banners, storyboards, or motion styleframes")
    if sys.platform == "darwin":
        subprocess.run(["open", url], check=False)


def cmd_extract_brand(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    output_json = Path(args.output_json).expanduser() if args.output_json else brand_dir / "brand-profile.json"
    output_markdown = Path(args.output_markdown).expanduser() if args.output_markdown else brand_dir / "brand-profile.md"
    identity_json = Path(args.output_identity_json).expanduser() if args.output_identity_json else brand_dir / "brand-identity.json"
    identity_markdown = Path(args.output_identity_markdown).expanduser() if args.output_identity_markdown else brand_dir / "brand-identity.md"
    cmd = [
        "--project-root", str(Path(args.project_root).expanduser().resolve()),
        "--output-json", str(output_json.resolve()),
        "--output-markdown", str(output_markdown.resolve()),
    ]
    if args.brand_name:
        cmd += ["--brand-name", args.brand_name]
    if args.homepage_url:
        cmd += ["--homepage-url", args.homepage_url]
    if args.notes_file:
        cmd += ["--notes-file", str(Path(args.notes_file).expanduser().resolve())]
    if args.reference_dir:
        cmd += ["--reference-dir", str(Path(args.reference_dir).expanduser().resolve())]
    if args.design_tokens_json:
        cmd += ["--design-tokens-json", str(Path(args.design_tokens_json).expanduser().resolve())]
    if args.design_memory_path:
        cmd += ["--design-memory-path", str(Path(args.design_memory_path).expanduser().resolve())]
    run_child_script(EXTRACT_BRAND_PY, cmd)

    build_cmd = [
        "--profile", str(output_json.resolve()),
        "--output-json", str(identity_json.resolve()),
        "--output-markdown", str(identity_markdown.resolve()),
    ]
    run_child_script(BUILD_IDENTITY_PY, build_cmd)


def cmd_build_identity(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    profile = Path(args.profile).expanduser() if args.profile else brand_dir / "brand-profile.json"
    output_json = Path(args.output_json).expanduser() if args.output_json else brand_dir / "brand-identity.json"
    output_markdown = Path(args.output_markdown).expanduser() if args.output_markdown else brand_dir / "brand-identity.md"
    cmd = [
        "--profile", str(profile.resolve()),
        "--output-json", str(output_json.resolve()),
        "--output-markdown", str(output_markdown.resolve()),
    ]
    run_child_script(BUILD_IDENTITY_PY, cmd)


def cmd_describe_brand(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    profile = Path(args.profile).expanduser() if args.profile else brand_dir / "brand-profile.json"
    output = Path(args.output).expanduser() if args.output else brand_dir / "brand-description-prompts.md"
    cmd = ["--profile", str(profile.resolve()), "--output", str(output.resolve())]
    if args.identity:
        cmd += ["--identity", str(Path(args.identity).expanduser().resolve())]
    run_child_script(DESCRIBE_BRAND_PY, cmd)


def cmd_show_identity(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    profile_path, identity_path, profile, identity = load_brand_memory(brand_dir, args.profile, args.identity)
    summary = summarize_identity(profile, identity)
    if args.format == "json":
        print(json.dumps({
            "files": {"profile": str(profile_path), "identity": str(identity_path)},
            "summary": summary,
        }, indent=2))
        return

    print("Brand identity summary\n")
    print(f"Brand: {summary['brand_name'] or 'n/a'}")
    print(f"Summary: {summary['summary'] or 'n/a'}")
    print(f"Homepage: {summary['homepage_url'] or 'n/a'}")
    print(f"Profile: {profile_path}")
    print(f"Identity: {identity_path}")
    print()
    print(f"Tone words: {', '.join(summary['tone_words']) or 'n/a'}")
    print(f"Brand anchors: {', '.join(summary['brand_anchors']) or 'n/a'}")
    print(f"Palette direction: {', '.join(summary['palette_direction']) or 'n/a'}")
    print(f"Typography cues: {', '.join(summary['typography_cues']) or 'n/a'}")
    print(f"Shape language: {', '.join(summary['shape_language']) or 'n/a'}")
    print(f"Approved graphic devices: {', '.join(summary['approved_graphic_devices']) or 'n/a'}")
    print(f"Forbidden elements: {', '.join(summary['forbidden_elements']) or 'n/a'}")
    print(f"Semantic palette roles: {', '.join(summary['semantic_palette_roles']) or 'n/a'}")
    print(f"Component cues: {', '.join(summary['component_cues']) or 'n/a'}")
    print(f"Framework cues: {', '.join(summary['framework_cues']) or 'n/a'}")
    print(f"Spacing scale: {', '.join(str(item) for item in summary['spacing_scale']) or 'n/a'}")
    print(f"Design-memory source: {summary['design_memory_source'] or 'n/a'}")
    print(f"Design-memory principles: {', '.join(summary['design_memory_principles'][:6]) or 'n/a'}")
    print(f"Design-memory components: {', '.join(summary['design_memory_components'][:6]) or 'n/a'}")
    print(f"Material prompt snippets: {', '.join(summary['material_prompt_snippet_keys']) or 'n/a'}")
    print(f"Material set templates: {', '.join(summary['material_set_template_keys']) or 'n/a'}")
    print(f"Inspiration translation rule: {summary['inspiration_translation_rule'] or 'n/a'}")
    print(f"Non-interface rule: {summary['non_interface_rule'] or 'n/a'}")
    print(f"Copy rule: {summary['copy_rule'] or 'n/a'}")
    print(f"Has imported tokens: {'yes' if summary['token_sources']['has_tokens'] else 'no'}")
    if args.show_prelude:
        print("\nGlobal brand guardrail prelude:\n")
        print(summary["prompt_prelude"] or "n/a")


def summarize_messaging_state(identity: dict) -> dict:
    messaging = identity.get("messaging") or {}
    copy_bank = messaging.get("approved_copy_bank") or {}
    voice = messaging.get("voice") or {}
    return {
        "tagline": messaging.get("tagline") or "",
        "elevator": messaging.get("elevator") or "",
        "voice_description": voice.get("description") or "",
        "value_propositions": list(messaging.get("value_propositions") or []),
        "copy_bank_counts": {
            "headlines": len(copy_bank.get("headlines") or []),
            "slogans": len(copy_bank.get("slogans") or []),
            "subheadlines": len(copy_bank.get("subheadlines") or []),
            "cta_pairs": len(copy_bank.get("cta_pairs") or []),
        },
        "positioning_insights": list(messaging.get("positioning_insights") or []),
        "copy_insights": list(messaging.get("copy_insights") or []),
    }


def build_session_summary_payload(brand_dir: Path, profile: dict, identity: dict, *, limit: int = 5) -> dict:
    manifest = load_manifest()
    board = load_blackboard(brand_dir, profile, identity)
    memory = load_iteration_memory(brand_dir)
    versions = manifest.get("versions") or {}
    sorted_versions = sorted(versions.items(), key=lambda item: _version_sort_key(item[0]), reverse=True)
    workflow_lookup = {
        str(item.get("version") or ""): str(item.get("workflow_id") or "")
        for item in (board.get("generated_assets") or [])
        if item.get("version")
    }
    recent_versions = []
    recent_feedback = []
    for vid, entry in sorted_versions[: max(1, limit)]:
        item = {
            "version": vid,
            "timestamp": entry.get("timestamp") or "",
            "material_type": entry.get("material_type") or "",
            "generation_mode": entry.get("generation_mode") or "",
            "mode": entry.get("mode") or "",
            "model": entry.get("model") or "",
            "tag": entry.get("tag") or "",
            "score": entry.get("score"),
            "status": entry.get("status") or "",
            "notes": entry.get("notes") or "",
            "files": list(entry.get("files") or []),
            "workflow_id": workflow_lookup.get(vid, ""),
        }
        recent_versions.append(item)
        if item["score"] is not None or item["status"] or item["notes"]:
            recent_feedback.append({
                "version": vid,
                "score": item["score"],
                "status": item["status"],
                "notes": item["notes"],
                "workflow_id": item["workflow_id"],
            })
    workspace_kind = "saved_brand"
    session_key = None
    brand_key = infer_brand_key_from_path(brand_dir)
    brand_gen_dir = get_brand_gen_dir()
    if brand_gen_dir:
        sessions_root = (brand_gen_dir / "sessions").resolve()
        try:
            rel = brand_dir.resolve().relative_to(sessions_root)
            if len(rel.parts) >= 2 and rel.parts[1] == "brand-materials":
                workspace_kind = "session"
                session_key = rel.parts[0]
        except Exception:
            pass
    session_context = ((identity.get("session_context") if isinstance(identity, dict) else None) or (profile.get("session_context") if isinstance(profile, dict) else None) or {})
    return {
        "brand_dir": str(brand_dir),
        "workspace": {
            "kind": workspace_kind,
            "session": session_key,
            "active_brand": brand_key or resolve_active_brand_key(brand_gen_dir),
            "seeded_from_brand": session_context.get("seeded_from_brand") or "",
        },
        "brand": {
            "name": ((identity.get("brand") or {}).get("name") or profile.get("brand_name") or "").strip(),
            "summary": ((identity.get("brand") or {}).get("summary") or profile.get("description") or "").strip(),
        },
        "generated": {
            "count": len(versions),
            "favorites": sum(1 for entry in versions.values() if entry.get("status") == "favorite"),
            "scored": sum(1 for entry in versions.values() if entry.get("score") is not None),
            "recent_versions": recent_versions,
            "recent_feedback": recent_feedback,
        },
        "messaging": summarize_messaging_state(identity),
        "iteration_memory": {
            "brand_notes": list(memory.get("brand_notes") or [])[-5:],
            "messaging_notes": list(memory.get("messaging_notes") or [])[-5:],
            "copy_notes": list(memory.get("copy_notes") or [])[-5:],
            "positive_examples": list(memory.get("positive_examples") or [])[-5:],
            "negative_examples": list(memory.get("negative_examples") or [])[-5:],
            "material_notes": {
                key: list(items or [])[-3:]
                for key, items in (memory.get("material_notes") or {}).items()
                if items
            },
        },
        "blackboard": {
            "active_brief": board.get("active_brief") or {},
            "artifacts": board.get("artifacts") or {},
            "recent_decisions": list(board.get("decisions") or [])[-5:],
            "reference_analysis": board.get("reference_analysis") or {},
        },
    }


def cmd_show_session_summary(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    _, _, profile, identity = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))
    payload = build_session_summary_payload(brand_dir, profile, identity, limit=max(1, int(getattr(args, "limit", 5) or 5)))
    if args.format == "json":
        print(json.dumps(payload, indent=2))
        return

    print("Current workspace summary\n")
    print(f"Brand: {payload['brand']['name'] or 'n/a'}")
    workspace = payload['workspace']
    label = workspace.get('kind') or 'workspace'
    if workspace.get('session'):
        label += f" ({workspace['session']})"
    print(f"Workspace: {label}")
    if workspace.get('seeded_from_brand'):
        print(f"Seeded from: {workspace['seeded_from_brand']}")
    print(f"Brand dir: {payload['brand_dir']}")

    generated = payload['generated']
    print(f"\nGenerated versions: {generated['count']} total, {generated['scored']} scored, {generated['favorites']} favorites")
    if generated['recent_versions']:
        print("Recent versions:")
        for item in generated['recent_versions']:
            score = f" score={item['score']}" if item['score'] is not None else ""
            status = f" {item['status']}" if item['status'] else ""
            workflow = f" workflow={item['workflow_id']}" if item.get('workflow_id') else ""
            print(f"- {item['version']} ({item['material_type'] or 'material'}, {item['timestamp'] or 'n/a'}){score}{status}{workflow}")
    if generated['recent_feedback']:
        print("\nRecent feedback:")
        for item in generated['recent_feedback']:
            parts = [item['version']]
            if item['score'] is not None:
                parts.append(f"score={item['score']}")
            if item['status']:
                parts.append(item['status'])
            if item['notes']:
                parts.append(item['notes'][:140])
            print(f"- {' | '.join(parts)}")

    messaging = payload['messaging']
    print("\nMessaging:")
    print(f"- Tagline: {messaging['tagline'] or 'n/a'}")
    if messaging['elevator']:
        print(f"- Elevator: {messaging['elevator'][:180]}{'…' if len(messaging['elevator']) > 180 else ''}")
    if messaging['voice_description']:
        print(f"- Voice: {messaging['voice_description']}")
    if messaging['value_propositions']:
        print(f"- Value props: {len(messaging['value_propositions'])}")
    counts = messaging['copy_bank_counts']
    print(f"- Copy bank: {counts['headlines']} headlines, {counts['slogans']} slogans, {counts['subheadlines']} subheadlines, {counts['cta_pairs']} CTA pairs")

    iteration = payload['iteration_memory']
    if any(iteration.get(key) for key in ['brand_notes', 'messaging_notes', 'copy_notes']):
        print("\nRecent iteration notes:")
        for label, key in [("Brand", "brand_notes"), ("Messaging", "messaging_notes"), ("Copy", "copy_notes")]:
            items = iteration.get(key) or []
            if items:
                print(f"- {label}: {' | '.join(items[-3:])}")

    blackboard = payload['blackboard']
    artifacts = blackboard.get('artifacts') or {}
    if artifacts:
        print("\nLatest artifacts:")
        for label, key in [("Plan draft", "latest_plan_draft"), ("Critique", "latest_plan_critique"), ("Scratchpad", "latest_generation_scratchpad"), ("Version", "latest_generated_version"), ("Auto review", "latest_auto_review")]:
            if artifacts.get(key):
                print(f"- {label}: {artifacts[key]}")
    decisions = blackboard.get('recent_decisions') or []
    if decisions:
        print("\nRecent blackboard decisions:")
        for item in decisions[-3:]:
            sev = f" [{item.get('severity')}]" if item.get('severity') else ""
            print(f"- {item.get('timestamp')} {item.get('agent')}{sev}: {item.get('decision')}")

def cmd_show_blackboard(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    _, _, profile, identity = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))
    board = load_blackboard(brand_dir, profile, identity)
    if args.format == "json":
        print(json.dumps(board, indent=2))
        return
    print("Brand blackboard\n")
    print(f"Brand: {(board.get('brand_dna') or {}).get('brand_name') or 'n/a'}")
    active = board.get("active_brief") or {}
    print(f"Active brief: {(active.get('material_type') or 'none')} ({active.get('stage') or 'idle'})")
    if active:
        print(f"Purpose: {active.get('purpose') or 'n/a'}")
        print(f"Mechanic: {active.get('system_mechanic') or 'n/a'}")
    latest = board.get("artifacts") or {}
    print(f"Latest plan draft: {latest.get('latest_plan_draft') or 'n/a'}")
    print(f"Latest critique: {latest.get('latest_plan_critique') or 'n/a'}")
    print(f"Latest scratchpad: {latest.get('latest_generation_scratchpad') or 'n/a'}")
    print(f"Latest version: {latest.get('latest_generated_version') or 'n/a'}")
    print(f"Latest auto review: {latest.get('latest_auto_review') or 'n/a'}")
    if board.get("reference_assignments"):
        print("\nReference assignments:")
        for role, item in (board.get("reference_assignments") or {}).items():
            print(f"- {role}: {item.get('source_name') or item.get('source_key') or 'n/a'}")
    reference_analysis = board.get("reference_analysis") or {}
    if reference_analysis:
        print("\nReference analysis:")
        print(f"- Source count: {reference_analysis.get('source_count') or 0}")
        print(f"- Consistency: {reference_analysis.get('consistency_score') or 0}")
        if reference_analysis.get("reference_set_hash"):
            print(f"- Hash: {reference_analysis.get('reference_set_hash')}")
        product_palette = ((reference_analysis.get("product_observations") or {}).get("palette") or [])[:4]
        if product_palette:
            print(f"- Observed product palette: {', '.join(product_palette)}")
        mechanics = ((reference_analysis.get("inspiration_observations") or {}).get("mechanics") or [])[:3]
        if mechanics:
            print(f"- Inspiration mechanics: {', '.join(mechanics)}")
        print("- Details: run `show-reference-analysis`")
    decisions = board.get("decisions") or []
    if decisions:
        print("\nRecent decisions:")
        for item in decisions[-5:]:
            sev = f" [{item.get('severity')}]" if item.get("severity") else ""
            print(f"- {item.get('timestamp')} {item.get('agent')}{sev}: {item.get('decision')}")


def cmd_show_workflow_lineage(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    board = load_blackboard(brand_dir)
    workflow_id = str(args.workflow_id)
    lineage = get_workflow_lineage(board, workflow_id)
    lineage["artifacts"] = collect_workflow_artifacts(brand_dir, workflow_id)
    lineage["brand_dir"] = str(brand_dir)
    if args.format == "json":
        print(json.dumps(lineage, indent=2))
        return
    print("Workflow lineage\n")
    print(f"Workflow ID: {workflow_id}")
    print(f"Brand dir: {brand_dir}")
    decisions = lineage.get("decisions") or []
    assets = lineage.get("assets") or []
    print(f"Decisions: {len(decisions)}")
    print(f"Generated assets: {len(assets)}")
    artifacts = lineage.get("artifacts") or {}
    print(
        "Artifacts: "
        f"{len(artifacts.get('plan_drafts') or [])} drafts, "
        f"{len(artifacts.get('plan_critiques') or [])} critiques, "
        f"{len(artifacts.get('generation_scratchpads') or [])} scratchpads"
    )
    if decisions:
        print("\nDecisions:")
        for item in decisions[-10:]:
            print(f"- [{item.get('timestamp') or 'n/a'}] {item.get('agent') or 'agent'}: {item.get('decision') or ''}")
    if assets:
        print("\nGenerated assets:")
        for item in assets[-10:]:
            files = ", ".join(item.get("files") or []) or "n/a"
            print(f"- {item.get('version') or 'n/a'} ({item.get('material_type') or 'material'}) -> {files}")
    for bucket in ("plan_drafts", "plan_critiques", "generation_scratchpads"):
        items = artifacts.get(bucket) or []
        if not items:
            continue
        print(f"\n{bucket.replace('_', ' ').title()}:")
        for item in items:
            print(f"- {item.get('path')}")


def cmd_show_reference_analysis(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    _, _, profile, identity = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))
    board = load_blackboard(brand_dir, profile, identity)
    analysis = board.get("reference_analysis") or {}
    if getattr(args, "refresh_reference_analysis", False):
        reference_paths = [Path(item.get("path")).expanduser().resolve() for item in (board.get("reference_assignments") or {}).values() if item.get("path")]
        role_pack_roles = [
            {
                "role": role,
                "path": item.get("path") or "",
                "source_key": item.get("source_key") or "",
                "source_name": item.get("source_name") or "",
            }
            for role, item in (board.get("reference_assignments") or {}).items()
            if item.get("path")
        ]
        analysis = ensure_reference_analysis(
            brand_dir,
            profile=profile,
            identity=identity,
            reference_paths=reference_paths,
            role_pack_roles=role_pack_roles,
            material_type=((board.get("active_brief") or {}).get("material_type") or None),
            refresh_extraction=True,
        )
    if args.format == "json":
        print(json.dumps(analysis, indent=2))
        return

    if not analysis:
        print("No cached reference analysis found.")
        print("Build a generation scratchpad first, or run build-generation-scratchpad without --skip-extraction.")
        return

    product = analysis.get("product_observations") or {}
    inspiration = analysis.get("inspiration_observations") or {}
    print("Reference analysis\n")
    print(f"Source count: {analysis.get('source_count') or 0}")
    print(f"Reference set hash: {analysis.get('reference_set_hash') or 'n/a'}")
    print(f"Consistency score: {analysis.get('consistency_score') or 0}")
    if product.get("palette"):
        print(f"\nObserved product palette: {', '.join(product.get('palette')[:6])}")
    if product.get("typography_cues"):
        print(f"Observed product typography: {', '.join(product.get('typography_cues')[:6])}")
    if product.get("component_cues"):
        print(f"Observed product component cues: {', '.join(product.get('component_cues')[:6])}")
    if inspiration.get("mechanics"):
        print(f"\nInspiration mechanics: {', '.join(inspiration.get('mechanics')[:6])}")
    if inspiration.get("composition_patterns"):
        print(f"Inspiration composition patterns: {', '.join(inspiration.get('composition_patterns')[:4])}")
    if inspiration.get("texture_patterns"):
        print(f"Inspiration texture patterns: {', '.join(inspiration.get('texture_patterns')[:6])}")
    warnings = analysis.get("warnings") or []
    if warnings:
        print("\nWarnings:")
        for item in warnings:
            print(f"- {item}")
    per_image = analysis.get("per_image") or []
    if per_image:
        print("\nPer-image:")
        for item in per_image:
            source = item.get("source_name") or item.get("source_key") or Path(item.get("path") or "").name or "ref"
            print(f"- {item.get('role') or item.get('bucket') or 'reference'}: {source}")
            if item.get("dominant_colors"):
                print(f"  palette: {', '.join((item.get('dominant_colors') or [])[:4])}")
            if item.get("composition"):
                print(f"  composition: {item.get('composition')}")
            if item.get("transferable_mechanics"):
                print(f"  mechanics: {', '.join((item.get('transferable_mechanics') or [])[:3])}")


def cmd_route_request(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    _, _, profile, identity = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))
    payload = build_route_payload(args, brand_dir, profile, identity)
    board = load_blackboard(brand_dir, profile, identity)
    append_blackboard_decision(
        board,
        agent="brand_director",
        decision=f"Routed request for {payload.get('material_type') or 'brand material'} to {payload.get('route_label')}.",
        confidence=float(payload.get("score") or 0.0),
        data={
            "route_key": payload.get("route_key"),
            "goal": payload.get("goal"),
            "request": payload.get("request"),
            "score_vector": payload.get("score_vector") or {},
            "method": payload.get("method") or "default",
        },
    )
    save_blackboard(brand_dir, board)
    if args.format == "json":
        print(json.dumps(payload, indent=2))
        return
    print("Workflow route\n")
    print(f"Material: {payload.get('material_type') or 'n/a'}")
    print(f"Route: {payload.get('route_label')}")
    print(f"Specialists: {', '.join(payload.get('specialists') or []) or 'n/a'}")
    print(f"Plan first: {'yes' if payload.get('should_plan_first') else 'no'}")
    if payload.get("required_assets"):
        print(f"Required assets: {', '.join(payload['required_assets'])}")
    if payload.get("required_questions"):
        print("Questions:")
        for item in payload["required_questions"]:
            print(f"- {item}")
    if payload.get("next_commands"):
        print("Next commands:")
        for item in payload["next_commands"]:
            print(f"- {item}")
    if payload.get("notes"):
        print(f"Notes: {payload['notes']}")


def cmd_resolve_prompt(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    profile_path, identity_path, profile, identity = load_brand_memory(brand_dir, args.profile, args.identity)
    brand_gen_dir = get_brand_gen_dir()
    active_brand = resolve_context_brand_key(
        brand_dir=brand_dir,
        profile_path=profile_path,
        identity_path=identity_path,
        profile=profile,
        identity=identity,
        brand_gen_dir=brand_gen_dir,
    )
    role_pack_override = None
    plan = None
    if getattr(args, "plan", None):
        _, plan = load_plan_payload(Path(args.plan).expanduser().resolve())
        role_pack_override = build_role_pack_override_from_plan(plan)
    raw_prompt = args.prompt or (plan.get("prompt_seed") if plan else "") or ""
    if not raw_prompt.strip():
        print("ERROR: resolve-prompt requires --prompt or --plan with a prompt_seed.", file=sys.stderr)
        sys.exit(1)
    board = load_blackboard(brand_dir, profile, identity)
    reference_analysis = board.get("reference_analysis") or {}
    if getattr(args, "refresh_reference_analysis", False):
        role_pack_roles = (role_pack_override or {}).get("roles") or []
        ref_paths = [Path(item["path"]).expanduser().resolve() for item in role_pack_roles if item.get("path")]
        reference_analysis = ensure_reference_analysis(
            brand_dir,
            profile=profile,
            identity=identity,
            reference_paths=ref_paths,
            role_pack_roles=role_pack_roles,
            material_type=args.material_type or (plan.get("material_type") if plan else None),
            refresh_extraction=True,
        )
    context = build_effective_prompt(
        profile,
        identity,
        raw_prompt,
        brand_gen_dir=brand_gen_dir,
        active_brand=active_brand,
        brand_dir=brand_dir,
        material_type=args.material_type or (plan.get("material_type") if plan else None),
        workflow_mode=args.mode if args.mode != "auto" else (plan.get("mode") if plan else "auto"),
        disable_brand_guardrails=args.disable_brand_guardrails,
        role_pack_override=role_pack_override,
        reference_analysis=reference_analysis,
    )
    resolved = context["resolved_prompt"]
    if args.format == "json":
        print(json.dumps({
            "profile": str(profile_path),
            "identity": str(identity_path),
            "brand_prelude": context["brand_prelude"],
            "iteration_memory_snippet": context.get("iteration_memory_snippet", ""),
            "material_prompt_key": context["material_prompt_key"],
            "material_prompt_variant": context["material_prompt_variant"],
            "material_prompt_snippet": context["material_prompt_snippet"],
            "reference_role_pack": context["reference_role_pack"],
            "reference_role_pack_priority": context["reference_role_pack_priority"],
            "reference_role_pack_prefer_unique_sources": context["reference_role_pack_prefer_unique_sources"],
            "reference_role_pack_paths": context["reference_role_pack_paths"],
            "reference_role_pack_motion_paths": context["reference_role_pack_motion_paths"],
            "reference_role_pack_snippet": context["reference_role_pack_snippet"],
            "reference_role_pack_required_roles": context["reference_role_pack_required_roles"],
            "reference_role_pack_missing_roles": context["reference_role_pack_missing_roles"],
            "reference_role_pack_missing_required_roles": context["reference_role_pack_missing_required_roles"],
            "reference_analysis": context.get("reference_analysis", {}),
            "reference_analysis_snippet": context.get("reference_analysis_snippet", ""),
            "inspiration_doctrine": context["inspiration_doctrine"],
            "token_block": context["token_block"],
            "inspiration_sources": context["inspiration_sources"],
            "skipped_inspiration_sources": context["skipped_inspiration_sources"],
            "raw_prompt": raw_prompt,
            "resolved_prompt": resolved,
        }, indent=2))
        return

    print("Resolved prompt\n")
    if context["brand_prelude"]:
        print(f"Prelude source profile: {profile_path}")
        print(f"Prelude source identity: {identity_path}")
        print("\nBrand prelude:\n")
        print(context["brand_prelude"])
    if context.get("iteration_memory_snippet"):
        print("\nIteration memory:\n")
        print(context["iteration_memory_snippet"])
    if context["material_prompt_snippet"]:
        variant = f"/{context['material_prompt_variant']}" if context["material_prompt_variant"] else ""
        print(f"\nMaterial doctrine snippet ({context['material_prompt_key']}{variant}):\n")
        print(context["material_prompt_snippet"])
    if context["reference_role_pack_snippet"]:
        print("\nReference role pack:\n")
        print(context["reference_role_pack_snippet"])
    if context.get("reference_analysis_snippet"):
        print("\nReference analysis:\n")
        print(context["reference_analysis_snippet"])
    if context["inspiration_doctrine"]:
        print("\nInspiration doctrine:\n")
        print(context["inspiration_doctrine"])
        if context["inspiration_sources"]:
            print(f"\nSources: {', '.join(context['inspiration_sources'])}")
    if context["token_block"]:
        print("\nToken block:\n")
        print(context["token_block"])
    if not (context["brand_prelude"] or context["inspiration_doctrine"] or context["token_block"]):
        print("No brand guardrail prelude or inspiration doctrine found.\n")
    print("\nResolved prompt:\n")
    print(resolved)


def cmd_review_prompt(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    profile_path, identity_path, profile, identity = load_brand_memory(brand_dir, args.profile, args.identity)
    brand_gen_dir = get_brand_gen_dir()
    active_brand = resolve_context_brand_key(
        brand_dir=brand_dir,
        profile_path=profile_path,
        identity_path=identity_path,
        profile=profile,
        identity=identity,
        brand_gen_dir=brand_gen_dir,
    )
    role_pack_override = None
    plan = None
    if getattr(args, "plan", None):
        _, plan = load_plan_payload(Path(args.plan).expanduser().resolve())
        role_pack_override = build_role_pack_override_from_plan(plan)
    raw_prompt = args.prompt or (plan.get("prompt_seed") if plan else "") or ""
    if not raw_prompt.strip():
        print("ERROR: review-prompt requires --prompt or --plan with a prompt_seed.", file=sys.stderr)
        sys.exit(1)
    material_type = args.material_type or (plan.get("material_type") if plan else None)
    workflow_mode = args.mode if args.mode != "auto" else (plan.get("mode") if plan else "auto")
    board = load_blackboard(brand_dir, profile, identity)
    reference_analysis = board.get("reference_analysis") or {}
    if getattr(args, "refresh_reference_analysis", False):
        role_pack_roles = (role_pack_override or {}).get("roles") or []
        ref_paths = [Path(item["path"]).expanduser().resolve() for item in role_pack_roles if item.get("path")]
        reference_analysis = ensure_reference_analysis(
            brand_dir,
            profile=profile,
            identity=identity,
            reference_paths=ref_paths,
            role_pack_roles=role_pack_roles,
            material_type=material_type,
            refresh_extraction=True,
        )
    context = build_effective_prompt(
        profile,
        identity,
        raw_prompt,
        brand_gen_dir=brand_gen_dir,
        active_brand=active_brand,
        brand_dir=brand_dir,
        material_type=material_type,
        workflow_mode=workflow_mode,
        disable_brand_guardrails=args.disable_brand_guardrails,
        role_pack_override=role_pack_override,
        reference_analysis=reference_analysis,
    )
    review = review_prompt_architecture(
        profile,
        identity,
        raw_prompt,
        context,
        material_type=material_type,
        workflow_mode=workflow_mode,
        token_block=context.get("token_block", ""),
    )
    scratchpad = save_prompt_review_scratchpad(
        brand_dir,
        {
            "profile": str(profile_path),
            "identity": str(identity_path),
            "material_type": material_type,
            "mode": workflow_mode,
            **review,
        },
        label=f"{material_type or 'material'}-{workflow_mode or 'mode'}-review",
    )
    if args.format == "json":
        print(json.dumps({
            "profile": str(profile_path),
            "identity": str(identity_path),
            "material_type": material_type,
            "mode": workflow_mode,
            "scratchpad": str(scratchpad),
            **review,
        }, indent=2))
        return

    print("Prompt review\n")
    print(f"Material: {material_type or 'n/a'}")
    print(f"Mode: {workflow_mode}")
    if review["issues"]:
        print("\nIssues:")
        for item in review["issues"]:
            print(f"- {item}")
    if review["recommendations"]:
        print("\nRecommendations:")
        for item in review["recommendations"]:
            print(f"- {item}")
    if review["compact_role_pack"]:
        print("\nReference translation summary:\n")
        print(review["compact_role_pack"])
    print(f"\nScratchpad: {scratchpad}")
    print("\nRefined prompt:\n")
    print(review["refined_prompt"])


def select_plan_roles(candidates: dict, picks: dict[str, str]) -> tuple[list[dict], list[str]]:
    selected: list[dict] = []
    missing_required: list[str] = []
    used_sources: set[str] = set()
    prefer_unique_sources = candidates.get("prefer_unique_sources", True)
    for role in candidates.get("priority") or ROLE_PACK_TAG_PRIORITY:
        role_candidates = candidates.get("candidates", {}).get(role) or []
        pick_value = picks.get(role)
        picked = None
        if pick_value:
            pick_path = Path(pick_value).expanduser()
            if pick_path.exists():
                picked = {
                    "role": role,
                    "role_help": next((item.get("role_help") for item in role_candidates if item.get("role_help")), ""),
                    "source_key": f"custom-{pick_path.stem}",
                    "source_name": pick_path.name,
                    "notes": "custom explicit path",
                    "path": str(pick_path.resolve()),
                    "asset_kind": path_media_kind(pick_path),
                    "used_role_asset": True,
                }
            else:
                for item in role_candidates:
                    if item["source_key"] == pick_value:
                        picked = dict(item)
                        break
        else:
            preferred_candidates = [
                item for item in role_candidates
                if not item.get("translation_only") and source_risk_rank(item.get("direct_generation_risk")) < source_risk_rank("high")
            ] or [
                item for item in role_candidates if source_risk_rank(item.get("direct_generation_risk")) < source_risk_rank("high")
            ] or [
                item for item in role_candidates if not item.get("translation_only")
            ] or role_candidates
            for item in preferred_candidates:
                if not prefer_unique_sources or item["source_key"] not in used_sources:
                    picked = dict(item)
                    break
            if not picked and preferred_candidates:
                picked = dict(preferred_candidates[0])

        if not picked:
            if role in (candidates.get("required_roles") or []):
                missing_required.append(role)
            continue
        selected.append(picked)
        if prefer_unique_sources:
            used_sources.add(picked["source_key"])
    return selected, missing_required


def cmd_suggest_role_pack(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    candidates = suggest_reference_role_pack(brand_dir, args.material_type)
    if args.format == "json":
        print(json.dumps(candidates, indent=2))
        return
    print(f"Reference-role suggestions for {args.material_type}\n")
    print(f"Material key: {candidates.get('material_key') or 'n/a'}")
    print(f"Priority: {', '.join(candidates.get('priority') or []) or 'n/a'}")
    print(f"Required: {', '.join(candidates.get('required_roles') or []) or 'n/a'}")
    print(f"Prefer unique sources: {'yes' if candidates.get('prefer_unique_sources', True) else 'no'}")
    if candidates.get("selection_note"):
        print(f"Selection note: {candidates['selection_note']}")
    for role in candidates.get("priority") or []:
        print(f"\n[{role}]")
        for item in (candidates.get("candidates", {}).get(role) or [])[: args.top]:
            suffix_bits = []
            if item.get("used_role_asset"):
                suffix_bits.append("role-asset")
            if item.get("translation_only"):
                suffix_bits.append("translation-only")
            if item.get("direct_generation_risk"):
                suffix_bits.append(f"risk={item['direct_generation_risk']}")
            suffix = f" {' '.join(suffix_bits)}" if suffix_bits else ""
            print(f"- {item['source_key']}: {item['source_name']} ({Path(item['path']).name}, {item['asset_kind']}{suffix})")
            if item.get("notes"):
                print(f"  {item['notes']}")
            translation = default_reference_translation(role, item)
            if translation.get("summary"):
                print(f"  translate: {translation['summary']}")


def cmd_plan_material(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    _, plan, missing_required = build_material_plan_from_args(args, brand_dir)
    plans_dir = brand_dir / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.output).expanduser().resolve() if args.output else plans_dir / f"{slugify(args.material_type)}-{slugify(args.mode)}-plan.json"
    output_path.write_text(json.dumps(plan, indent=2) + "\n")
    if args.format == "json":
        print(json.dumps(plan, indent=2))
        return
    print(f"Material plan written to: {output_path}\n")
    print(f"Material: {plan['material_type']}")
    print(f"Mode: {plan['mode']}")
    print(f"Purpose: {plan.get('purpose') or 'n/a'}")
    print(f"Surface: {plan.get('target_surface') or 'n/a'}")
    print(f"Product truth: {plan.get('product_truth_expression') or 'n/a'}")
    print(f"Branding rule: {(plan.get('brand_anchor_policy') or {}).get('rule') or 'n/a'}")
    print(f"Mechanic: {plan['system_mechanic'] or 'n/a'}")
    print(f"Preserve: {', '.join(plan['preserve']) or 'n/a'}")
    print(f"Push: {', '.join(plan['push']) or 'n/a'}")
    print(f"Ban: {', '.join(plan['ban']) or 'n/a'}")
    print("\nSelected roles:")
    for item in ((plan.get("role_pack") or {}).get("selected_roles") or []):
        print(f"- {item['role']}: {item['source_key']} ({Path(item['path']).name})")
        translation = (item.get("translation") or {}).get("summary")
        if translation:
            print(f"  translate: {translation}")
    if missing_required:
        print(f"\nMissing required roles: {', '.join(missing_required)}")
    print("\nPrompt seed:\n")
    print(plan["prompt_seed"])


def cmd_plan_draft(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    _, plan, missing_required = build_material_plan_from_args(args, brand_dir)
    selected_role_names = [str(item.get("role") or "").strip() for item in ((plan.get("role_pack") or {}).get("selected_roles") or []) if str(item.get("role") or "").strip()]
    workflow_id = resolve_workflow_id(plan)
    draft = {
        "schema_type": "plan_draft",
        "schema_version": 1,
        "workflow_id": workflow_id,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "state": {
            "status": "drafted",
            "owner": "brand_director",
            "next_owner": "critic_agent",
        },
        "plan": plan,
        "derived": {
            "selected_role_names": selected_role_names,
            "missing_required_roles": missing_required,
        },
        "next_step": "Run critique-plan on this draft before building a generation scratchpad.",
    }
    output_path = Path(args.output).expanduser().resolve() if args.output else save_plan_draft(
        brand_dir,
        draft,
        label=f"{args.material_type}-{args.mode}-plan-draft",
    )
    if args.output:
        output_path.write_text(json.dumps(draft, indent=2) + "\n")
    profile_path, identity_path, profile, identity = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))
    persist_plan_draft_to_blackboard(brand_dir, profile, identity, draft, output_path=output_path, workflow_id=workflow_id)
    if args.format == "json":
        print(json.dumps({**draft, "output": str(output_path)}, indent=2))
        return
    print(f"Plan draft written to: {output_path}\n")
    print(f"Material: {plan['material_type']}")
    print(f"Mode: {plan['mode']}")
    print(f"Mechanic: {plan['system_mechanic'] or 'n/a'}")
    print(f"Missing required roles: {', '.join(missing_required) or 'none'}")
    print("\nNext step:")
    print(draft["next_step"])


def extract_plan_payload(payload: dict) -> dict:
    if payload.get("schema_type") == "plan_draft" and isinstance(payload.get("plan"), dict):
        return payload["plan"]
    return payload


def load_plan_payload(path: Path) -> tuple[dict, dict]:
    payload = load_json_file(path)
    return payload, extract_plan_payload(payload)


def assemble_generation_scratchpad(
    args,
    *,
    brand_dir: Path,
    plan_wrapper: dict,
    plan: dict,
) -> dict:
    requested_material_type = args.material_type or plan.get("material_type") or "logo"
    material_type = normalize_material_type(requested_material_type)
    tag = args.tag or plan.get("tag") or requested_material_type or "brand"
    raw_prompt = args.prompt or plan.get("prompt_seed") or ""
    if not raw_prompt.strip():
        raise SystemExit("ERROR: build-generation-scratchpad requires --prompt or --plan with a prompt_seed.")

    plan_role_pack_override = build_role_pack_override_from_plan(plan) if plan else None
    plan_reference_paths = [Path(item["path"]).expanduser().resolve() for item in ((plan.get("role_pack") or {}).get("selected_roles") or []) if path_media_kind(item.get("path", "")) == "image"]
    reference_paths = expand_reference_paths(getattr(args, "image", None), getattr(args, "reference_dir", None))
    reference_paths = dedupe_paths(reference_paths + plan_reference_paths)
    requested_mode = args.mode if getattr(args, "mode", "auto") != "auto" else (plan.get("mode") or "auto")
    workflow_mode = resolve_workflow_mode(requested_mode, reference_paths)
    generation_mode = resolve_generation_mode(material_type, getattr(args, "generation_mode", "auto"))

    profile_path, identity_path, profile_data, identity_data = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))
    brand_gen_dir = get_brand_gen_dir()
    active_brand = resolve_context_brand_key(
        brand_dir=brand_dir,
        profile_path=profile_path,
        identity_path=identity_path,
        profile=profile_data,
        identity=identity_data,
        brand_gen_dir=brand_gen_dir,
    )
    pre_prompt_reference_paths = dedupe_paths(
        list(reference_paths)
        + [Path(item["path"]).expanduser().resolve() for item in ((plan_role_pack_override or {}).get("roles") or []) if path_media_kind(item.get("path", "")) == "image"]
    )
    reference_analysis = ensure_reference_analysis(
        brand_dir,
        profile=profile_data,
        identity=identity_data,
        reference_paths=pre_prompt_reference_paths,
        role_pack_roles=(plan_role_pack_override or {}).get("roles") or [],
        material_type=material_type,
        skip_extraction=bool(getattr(args, "skip_extraction", False)),
        refresh_extraction=bool(getattr(args, "refresh_reference_analysis", False)),
    )
    prompt_context = build_effective_prompt(
        profile_data,
        identity_data,
        raw_prompt,
        brand_gen_dir=brand_gen_dir,
        active_brand=active_brand,
        brand_dir=brand_dir,
        material_type=material_type,
        workflow_mode=workflow_mode,
        disable_brand_guardrails=getattr(args, "disable_brand_guardrails", False),
        role_pack_override=plan_role_pack_override,
        reference_analysis=reference_analysis,
    )

    role_pack_paths = [Path(path) for path in prompt_context.get("reference_role_pack_paths", [])]
    role_pack_motion_paths = [Path(path) for path in prompt_context.get("reference_role_pack_motion_paths", [])]
    selected_role_names = [str(item.get("role") or "").strip() for item in (prompt_context.get("reference_role_pack") or []) if str(item.get("role") or "").strip()]
    required_roles = prompt_context.get("reference_role_pack_required_roles") or []
    missing_required_roles = [role for role in required_roles if role not in selected_role_names]
    motion_reference = Path(args.motion_reference).expanduser().resolve() if getattr(args, "motion_reference", None) else None
    all_context_refs = dedupe_paths(list(reference_paths) + role_pack_paths)

    blocking_issues: list[str] = []
    warnings: list[str] = []
    if workflow_mode in {"reference", "hybrid"} and not reference_paths:
        blocking_issues.append(f"Mode '{workflow_mode}' requires at least one reference asset.")
    if motion_reference and not reference_paths:
        blocking_issues.append("--motion-reference requires at least one --image start frame or reference asset.")
    if missing_required_roles:
        blocking_issues.append("Missing required role refs: " + ", ".join(missing_required_roles))
    if required_roles and len(selected_role_names) < 2:
        blocking_issues.append("This material requires at least two role-pack references before generation.")

    # --- Hole 5 fix: Check inspiration pipeline status ---
    inspiration_status = check_inspiration_pipeline_status(brand_gen_dir, active_brand, workflow_mode)
    if not inspiration_status["ok"]:
        for w in inspiration_status.get("warnings", []):
            warnings.append(f"Inspiration: {w}")
        for s in inspiration_status.get("suggestions", []):
            warnings.append(f"  → {s}")
    for warning in (reference_analysis.get("warnings") or []):
        warnings.append(f"Reference analysis: {warning}")

    model = args.model or resolve_default_model(
        material_type,
        generation_mode,
        workflow_mode,
        all_context_refs,
        prompt_context["material_prompt_key"],
        has_motion_reference=bool(motion_reference),
    )
    model_config = MODELS.get(generation_mode, {}).get(model)
    if not model_config:
        blocking_issues.append(f"Model '{model}' is not available for {generation_mode} generation.")
        model_config = {}
    elif motion_reference and not model_supports_motion_reference(model_config):
        blocking_issues.append(f"Model '{model}' does not support motion references.")

    aspect_ratio = resolve_default_aspect_ratio(material_type, getattr(args, "aspect_ratio", None), model_config or {})
    prompt_review = review_prompt_architecture(
        profile_data,
        identity_data,
        raw_prompt,
        prompt_context,
        material_type=material_type,
        workflow_mode=workflow_mode,
        token_block=prompt_context.get("token_block", ""),
    )
    reference_tag_context = build_reference_tag_context(
        model,
        generation_mode,
        reference_paths,
        prompt_context.get("reference_role_pack") or [],
    )
    effective_prompt = prompt_review["refined_prompt"]
    tagged_prompt_suffix = reference_tag_context.get("prompt_suffix", "").strip()
    if tagged_prompt_suffix:
        effective_prompt = f"{effective_prompt.rstrip()}\n\n{tagged_prompt_suffix}"
    supports_reference_images = model_supports_reference_images(model_config, generation_mode) if model_config else False
    passed_refs = list(all_context_refs)
    if model_config and not supports_reference_images and all_context_refs:
        passed_refs = []
        warnings.append(f"Model '{model}' does not accept image refs in the current wrapper; refs are used for prompt routing/context only.")
    if model_config and model_supports_reference_tags(model_config) and reference_tag_context.get("passed_refs"):
        passed_refs = dedupe_paths(reference_tag_context["passed_refs"])
    if generation_mode == "video" and len(passed_refs) > 1:
        warnings.append("Video generation supports one start frame; only the first reference asset will be passed to the model.")
        passed_refs = passed_refs[:1]
    if generation_mode == "video" and getattr(args, "duration", None) and model_config and not (model_config.get("field_map", {}) or {}).get("duration") and "duration" not in (model_config.get("defaults", {}) or {}):
        warnings.append(f"Model '{model}' does not expose duration control; --duration will be ignored.")

    payload = {
        "schema_type": "generation_scratchpad",
        "schema_version": 1,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "state": {
            "status": "blocked" if blocking_issues else "ready_to_generate",
            "owner": "visual_composer",
            "next_owner": "generator",
        },
        "brand_dir": str(brand_dir),
        "plan_path": getattr(args, "plan", None) or "",
        "plan_wrapper": plan_wrapper,
        "plan": plan,
        "material_type": material_type,
        "tag": tag,
        "workflow_mode": workflow_mode,
        "generation_mode": generation_mode,
        "profile_path": str(profile_path),
        "identity_path": str(identity_path),
        "raw_prompt": raw_prompt,
        "prompt_context": prompt_context,
        "prompt_review": prompt_review,
        "effective_prompt": effective_prompt,
        "reference_context": {
            "explicit_reference_paths": [str(path) for path in reference_paths],
            "role_pack_paths": [str(path) for path in role_pack_paths],
            "role_pack_motion_paths": [str(path) for path in role_pack_motion_paths],
            "all_context_refs": [str(path) for path in all_context_refs],
            "passed_reference_paths": [str(path) for path in passed_refs],
            "reference_tags": reference_tag_context.get("reference_tags", []),
            "required_roles": required_roles,
            "selected_role_names": selected_role_names,
            "missing_required_roles": missing_required_roles,
            "analysis_reference_set_hash": reference_analysis.get("reference_set_hash") or "",
        },
        "execution": {
            "model": model,
            "aspect_ratio": aspect_ratio,
            "resolution": getattr(args, "resolution", None),
            "duration": getattr(args, "duration", None),
            "preset": getattr(args, "preset", None),
            "negative_prompt": getattr(args, "negative_prompt", None),
            "style": getattr(args, "style", None),
            "make_gif": bool(getattr(args, "make_gif", False)),
            "motion_reference": str(motion_reference) if motion_reference else "",
            "motion_mode": getattr(args, "motion_mode", None),
            "character_orientation": getattr(args, "character_orientation", None),
            "keep_original_sound": bool(getattr(args, "keep_original_sound", False)),
            "supports_reference_images": supports_reference_images,
            "reference_tags": reference_tag_context.get("reference_tags", []),
        },
        "checks": {
            "blocking": blocking_issues,
            "warnings": warnings + prompt_review.get("recommendations", []),
        },
    }
    return payload


def build_structural_auto_critic(payload: dict) -> dict:
    material_key = role_pack_material_key(payload.get("material_type") or "")
    review = {"p1": [], "p2": [], "p3": [], "clean": []}
    plan = payload.get("plan") or {}
    brand_policy = plan.get("brand_anchor_policy") or {}
    passed_refs = (((payload.get("reference_context") or {}).get("passed_reference_paths")) or [])
    prompt_review = payload.get("prompt_review") or {}
    if material_key in INTERFACE_MATERIAL_KEYS and not passed_refs:
        review["p1"].append("Product-led material has no passed proof references; it may drift away from real product truth.")
    if brand_policy.get("logo_mode") == "required":
        profile_assets = (load_json_file(Path(payload.get("profile_path") or "")) if payload.get("profile_path") else {}).get("brand_assets") or {}
        if not any(str(profile_assets.get(key) or "").strip() for key in ("icon", "wordmark", "lockup")):
            review["p1"].append("Logo-required material has no approved brand asset in brand memory.")
    review["p2"].extend(prompt_review.get("issues") or [])
    review["p3"].extend((payload.get("checks") or {}).get("warnings") or [])
    if (payload.get("checks") or {}).get("blocking"):
        review["p1"].extend((payload.get("checks") or {}).get("blocking") or [])
    if not review["p1"]:
        review["clean"].append("Scratchpad passed the structural generator gate.")
    if passed_refs:
        review["clean"].append("Generation included explicit reference context.")
    return review


def run_auto_brand_review(brand_dir: Path, version_id: str) -> tuple[str, bool]:
    reviews_dir = brand_dir / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    output = reviews_dir / f"{version_id}-auto-review.md"
    result = subprocess.run(
        [sys.executable, str(BUILD_REVIEW_PACKET_PY), "--brand-dir", str(brand_dir.resolve()), "--version", version_id, "--output", str(output.resolve())],
        capture_output=True,
        text=True,
    )
    return str(output), result.returncode == 0


# ---------------------------------------------------------------------------
# VLM Critic — Hole 2 fix: Actually look at the generated image
# ---------------------------------------------------------------------------

VLM_CRITIQUE_SYSTEM = """\
You are a brand material critic. You receive:
1. A generated image
2. The brand brief / prompt that produced it
3. The brand DNA (palette hex values, approved devices, forbidden elements)

Evaluate the image and return a JSON object with these keys:
- "approved": boolean — true only if all P1 checks pass
- "p1": list of blocking issues (wrong palette, hallucinated UI, missing logo when required, invented text)
- "p2": list of should-fix issues (composition, hierarchy, whitespace, brand fit)
- "p3": list of nice-to-have polish items
- "clean": list of things that are working well
- "palette_match": float 0-1 — how well the dominant colors match the brand hex values
- "logo_visible": boolean — whether the brand mark/logo is recognizable
- "hallucinated_elements": list of UI elements or text that appear invented
- "composition_notes": string — brief composition assessment
- "refinement_suggestion": string — one concrete change for the next iteration
"""

REFERENCE_ANALYSIS_SYSTEM = """\
You analyze a single brand reference image for an agent-driven brand system.

Return JSON only. Focus on observable visual mechanics, not marketing claims.
When the image is product truth, describe what is actually visible in the product/UI.
When the image is inspiration, describe transferable mechanics rather than literal brand identity.
"""


def _extract_json_dict(text: str) -> dict | None:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    if not cleaned:
        return None
    try:
        data = json.loads(cleaned)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def _run_vlm_json(image_path: Path, system_prompt: str, user_text: str, *, max_tokens: int = 1024) -> dict | None:
    if not image_path.exists():
        return None
    img_bytes = image_path.read_bytes()
    img_b64 = base64.b64encode(img_bytes).decode("utf-8")
    mime = mimetypes.guess_type(str(image_path))[0] or "image/jpeg"

    env = build_env()
    anthropic_key = env.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        try:
            import httpx
            resp = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": anthropic_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": max_tokens,
                    "system": system_prompt,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": mime, "data": img_b64}},
                            {"type": "text", "text": user_text},
                        ],
                    }],
                },
                timeout=60.0,
            )
            if resp.status_code == 200:
                body = resp.json()
                text = "".join(block.get("text", "") for block in body.get("content", []))
                parsed = _extract_json_dict(text)
                if parsed is not None:
                    return dict(parsed, vlm_provider="anthropic")
        except Exception as exc:
            print(f"VLM (Claude) error: {exc}", file=sys.stderr)

    openai_key = env.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if openai_key:
        try:
            import httpx
            resp = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                json={
                    "model": "gpt-4o",
                    "max_tokens": max_tokens,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": [
                            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}},
                            {"type": "text", "text": user_text},
                        ]},
                    ],
                },
                timeout=60.0,
            )
            if resp.status_code == 200:
                body = resp.json()
                text = body.get("choices", [{}])[0].get("message", {}).get("content", "")
                parsed = _extract_json_dict(text)
                if parsed is not None:
                    return dict(parsed, vlm_provider="openai")
        except Exception as exc:
            print(f"VLM (OpenAI) error: {exc}", file=sys.stderr)

    return None


def _reference_analysis_stub(item: dict, deterministic: dict, reason: str) -> dict:
    return {
        "path": str(item["path"]),
        "role": item.get("role") or "",
        "bucket": item.get("bucket") or "",
        "source_key": item.get("source_key") or "",
        "source_name": item.get("source_name") or "",
        "dominant_colors": deterministic.get("dominant_colors") or [],
        "lighting_style": deterministic.get("brightness_label") or "",
        "composition": deterministic.get("aspect_ratio") or "",
        "typography_cues": [],
        "texture_patterns": deterministic.get("texture_patterns") or [],
        "spatial_rhythm": deterministic.get("spatial_rhythm") or "",
        "mood_keywords": [],
        "notable_elements": [],
        "transferable_mechanics": [],
        "role_relevance": "unknown",
        "confidence": 0.0,
        "vlm_available": False,
        "vlm_unavailable_reason": reason,
        "deterministic": deterministic,
    }


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def run_vlm_reference_analysis(item: dict, brand_context: str) -> dict:
    image_path = Path(item["path"])
    deterministic = extract_reference_image_stats(image_path)
    bucket = item.get("bucket") or "reference"
    role = item.get("role") or bucket
    focus = (
        "Treat this as product truth. Extract actual palette, typography, component cues, and proof-bearing UI patterns that should remain truthful."
        if bucket == "product"
        else "Treat this as inspiration. Extract transferable mechanics only: composition, spacing rhythm, texture treatment, framing, and presentation logic. Do not treat foreign logos or copy as brand truth."
    )
    user_text = (
        f"## Role\n{role}\n\n"
        f"## Bucket\n{bucket}\n\n"
        f"## Brand context\n{brand_context[:1200]}\n\n"
        f"## Deterministic cues\n"
        f"Dominant colors: {', '.join(deterministic.get('dominant_colors') or []) or 'n/a'}\n"
        f"Brightness: {deterministic.get('brightness_label') or 'n/a'}\n"
        f"Contrast: {deterministic.get('contrast_label') or 'n/a'}\n"
        f"Aspect ratio: {deterministic.get('aspect_ratio') or 'n/a'}\n"
        f"Spatial rhythm: {deterministic.get('spatial_rhythm') or 'n/a'}\n\n"
        f"{focus}\n\n"
        "Return JSON only with keys: composition, lighting_style, typography_cues, texture_patterns, "
        "spatial_rhythm, mood_keywords, notable_elements, transferable_mechanics, role_relevance, confidence."
    )
    parsed = _run_vlm_json(image_path, REFERENCE_ANALYSIS_SYSTEM, user_text, max_tokens=700)
    if parsed is None:
        return _reference_analysis_stub(item, deterministic, "No VLM API key available or response was invalid")
    return {
        "path": str(image_path),
        "role": role,
        "bucket": bucket,
        "source_key": item.get("source_key") or "",
        "source_name": item.get("source_name") or "",
        "dominant_colors": deterministic.get("dominant_colors") or [],
        "lighting_style": str(parsed.get("lighting_style") or deterministic.get("brightness_label") or "").strip(),
        "composition": str(parsed.get("composition") or deterministic.get("aspect_ratio") or "").strip(),
        "typography_cues": dedupe_keep_order([str(value).strip() for value in (parsed.get("typography_cues") or []) if str(value).strip()][:6]),
        "texture_patterns": dedupe_keep_order(
            [str(value).strip() for value in (deterministic.get("texture_patterns") or []) if str(value).strip()] +
            [str(value).strip() for value in (parsed.get("texture_patterns") or []) if str(value).strip()]
        )[:6],
        "spatial_rhythm": str(parsed.get("spatial_rhythm") or deterministic.get("spatial_rhythm") or "").strip(),
        "mood_keywords": dedupe_keep_order([str(value).strip() for value in (parsed.get("mood_keywords") or []) if str(value).strip()][:6]),
        "notable_elements": dedupe_keep_order([str(value).strip() for value in (parsed.get("notable_elements") or []) if str(value).strip()][:8]),
        "transferable_mechanics": dedupe_keep_order([str(value).strip() for value in (parsed.get("transferable_mechanics") or []) if str(value).strip()][:8]),
        "role_relevance": str(parsed.get("role_relevance") or "").strip() or "medium",
        "confidence": _clamp(_safe_float(parsed.get("confidence"), 0.65)),
        "vlm_available": True,
        "vlm_provider": parsed.get("vlm_provider") or "",
        "deterministic": deterministic,
    }


def aggregate_reference_dna(analyses: list[dict], reference_inputs: list[dict], *, reference_set_hash: str) -> dict:
    role_weights = {"product": 2.0, "inspiration": 1.0, "reference": 1.0}
    product_items = [item for item in analyses if item.get("bucket") == "product"]
    inspiration_items = [item for item in analyses if item.get("bucket") == "inspiration"]
    all_items = list(analyses)

    def weighted_tokens(items: list[dict], field: str, *, limit: int = 6) -> list[str]:
        values: list[tuple[str, float]] = []
        for item in items:
            weight = role_weights.get(item.get("bucket") or "reference", 1.0) * max(_safe_float(item.get("confidence"), 0.3), 0.25)
            raw_values = item.get(field) or []
            if isinstance(raw_values, str):
                raw_values = [raw_values]
            for value in raw_values:
                values.append((str(value), weight))
        return _token_frequency_ranked(values, limit=limit)

    def weighted_majority_field(items: list[dict], field: str, default: str = "") -> str:
        values: list[tuple[str, float]] = []
        for item in items:
            weight = role_weights.get(item.get("bucket") or "reference", 1.0) * max(_safe_float(item.get("confidence"), 0.3), 0.25)
            raw = str(item.get(field) or "").strip()
            if raw:
                values.append((raw, weight))
        return _weighted_majority(values, default)

    palette_votes: list[tuple[str, float]] = []
    for item in product_items or all_items:
        weight = role_weights.get(item.get("bucket") or "reference", 1.0) * max(_safe_float(item.get("confidence"), 0.4), 0.25)
        for color in (item.get("dominant_colors") or [])[:4]:
            palette_votes.append((str(color), weight))

    product_palette = _token_frequency_ranked(palette_votes, limit=6)
    inspiration_palette = _token_frequency_ranked(
        [(str(color), max(_safe_float(item.get("confidence"), 0.3), 0.25))
         for item in inspiration_items for color in (item.get("dominant_colors") or [])[:4]],
        limit=6,
    )

    available_flags = [1.0 if item.get("vlm_available") else 0.0 for item in analyses]
    confidence_values = [_safe_float(item.get("confidence"), 0.0) for item in analyses]
    consistency_basis = []
    for field in ("composition", "spatial_rhythm", "lighting_style"):
        values = [str(item.get(field) or "").strip().lower() for item in analyses if str(item.get(field) or "").strip()]
        if values:
            top = max(values.count(value) for value in set(values))
            consistency_basis.append(top / len(values))
    consistency_basis.append(_average(available_flags))
    consistency_basis.append(_average(confidence_values))
    consistency_score = round(_clamp(_average(consistency_basis)), 2) if consistency_basis else 0.0

    warnings: list[str] = []
    if len(analyses) >= 2 and consistency_score < 0.45:
        warnings.append("Reference set pulls in multiple directions; keep inspiration translated and favor the product-truth refs.")
    if not product_items:
        warnings.append("No product-truth refs detected; observed palette/mechanics are advisory only.")
    product_temp = _palette_temperature(product_palette)
    inspiration_temp = _palette_temperature(inspiration_palette)
    if product_items and inspiration_items and product_temp != "neutral" and inspiration_temp != "neutral" and product_temp != inspiration_temp:
        warnings.append(f"Inspiration refs skew {inspiration_temp} while product refs skew {product_temp}; treat inspiration as mechanics, not palette truth.")

    product_observations = {
        "palette": product_palette,
        "palette_confidence": round(_clamp(0.45 + 0.15 * len(product_items) + 0.25 * consistency_score), 2) if product_items else 0.0,
        "typography_cues": weighted_tokens(product_items, "typography_cues", limit=6),
        "component_cues": weighted_tokens(product_items, "notable_elements", limit=6),
        "mood_keywords": weighted_tokens(product_items, "mood_keywords", limit=5),
        "lighting_style": weighted_majority_field(product_items, "lighting_style"),
    }
    inspiration_observations = {
        "mechanics": weighted_tokens(inspiration_items, "transferable_mechanics", limit=6),
        "composition_patterns": weighted_tokens(inspiration_items, "composition", limit=4),
        "texture_patterns": weighted_tokens(inspiration_items, "texture_patterns", limit=6),
        "mood_keywords": weighted_tokens(inspiration_items, "mood_keywords", limit=5),
        "palette": inspiration_palette,
    }

    return {
        "schema_type": "reference_analysis",
        "schema_version": REFERENCE_ANALYSIS_VERSION,
        "reference_set_hash": reference_set_hash,
        "source_count": len(reference_inputs),
        "product_observations": product_observations,
        "inspiration_observations": inspiration_observations,
        "consistency_score": consistency_score,
        "warnings": warnings,
        "per_image": analyses,
    }


def build_reference_analysis_snippet(reference_analysis: dict, material_type: str | None = None) -> str:
    if not isinstance(reference_analysis, dict):
        return ""
    product = reference_analysis.get("product_observations") or {}
    inspiration = reference_analysis.get("inspiration_observations") or {}
    warnings = reference_analysis.get("warnings") or []
    lines: list[str] = []
    palette = product.get("palette") or []
    palette_confidence = float(product.get("palette_confidence") or 0.0)
    if palette and palette_confidence >= 0.45:
        lines.append(
            "Observed product refs reinforce palette around "
            + ", ".join(str(color) for color in palette[:4])
            + "."
        )
    mechanics = inspiration.get("mechanics") or []
    if mechanics:
        lines.append(
            "Observed inspiration refs suggest transferable mechanics such as "
            + sentence_join([str(item) for item in mechanics[:3]])
            + "."
        )
    composition_patterns = inspiration.get("composition_patterns") or []
    if composition_patterns and role_pack_material_key(material_type) in INTERFACE_MATERIAL_KEYS:
        lines.append(
            "Presentation framing cues from refs: "
            + sentence_join([str(item) for item in composition_patterns[:2]])
            + "."
        )
    if warnings:
        lines.append("Reference-analysis caution: " + str(warnings[0]))
    return "\n".join(lines).strip()


def reference_analysis_review_notes(reference_analysis: dict) -> tuple[list[str], list[str]]:
    issues: list[str] = []
    recommendations: list[str] = []
    if not isinstance(reference_analysis, dict):
        return issues, recommendations
    consistency = float(reference_analysis.get("consistency_score") or 0.0)
    warnings = [str(item).strip() for item in (reference_analysis.get("warnings") or []) if str(item).strip()]
    if consistency and consistency < 0.45:
        issues.append("Reference set is visually inconsistent; the prompt should favor one clear product-truth path.")
        recommendations.append("Reduce the number of conflicting references or explicitly state which refs only control framing.")
    for warning in warnings[:2]:
        if warning not in recommendations:
            recommendations.append(warning)
    return issues, recommendations


def ensure_reference_analysis(
    brand_dir: Path,
    *,
    profile: dict,
    identity: dict,
    reference_paths: list[Path],
    role_pack_roles: list[dict],
    material_type: str | None = None,
    skip_extraction: bool = False,
    refresh_extraction: bool = False,
) -> dict:
    reference_inputs = build_reference_analysis_inputs(reference_paths, role_pack_roles)
    if not reference_inputs:
        return {}
    board = load_blackboard(brand_dir, profile, identity)
    existing = board.get("reference_analysis") or {}
    signature_parts = [f"{item['role']}|{item['bucket']}|{item['path']}|{_image_content_signature(item['path'])}" for item in reference_inputs]
    signature_parts.append(f"material:{role_pack_material_key(material_type)}")
    reference_set_hash = hashlib.sha256("\n".join(signature_parts).encode("utf-8")).hexdigest()[:20]
    if not refresh_extraction and existing.get("reference_set_hash") == reference_set_hash and existing.get("schema_version") == REFERENCE_ANALYSIS_VERSION:
        return existing
    if skip_extraction:
        return {}

    summary = summarize_identity(profile, identity)
    brand_context = (
        f"Brand: {summary.get('brand_name') or 'n/a'}\n"
        f"Summary: {summary.get('summary') or 'n/a'}\n"
        f"Palette direction: {', '.join(summary.get('palette_direction') or []) or 'n/a'}\n"
        f"Typography cues: {', '.join(summary.get('typography_cues') or []) or 'n/a'}\n"
        f"Approved devices: {', '.join(summary.get('approved_graphic_devices') or []) or 'n/a'}"
    )
    analyses = [run_vlm_reference_analysis(item, brand_context) for item in reference_inputs]
    aggregated = aggregate_reference_dna(analyses, reference_inputs, reference_set_hash=reference_set_hash)
    board["reference_analysis"] = aggregated
    append_blackboard_decision(
        board,
        agent="brand_director",
        decision=f"Auto-extracted reference analysis from {len(reference_inputs)} refs.",
        confidence=0.66 if any(item.get("vlm_available") for item in analyses) else 0.42,
        severity="P2" if (aggregated.get("warnings") or []) else "P3",
        data={"reference_set_hash": reference_set_hash, "material_type": material_type or ""},
    )
    save_blackboard(brand_dir, board)
    return aggregated


def run_vlm_critique(image_path: Path, brief: str, brand_dna: dict) -> dict:
    """Run a Vision-Language Model critique on a generated image.

    Tries Claude (via the Anthropic SDK) first, then falls back to
    OpenAI's GPT-4o vision, then returns a stub if neither is available.
    """
    palette = ", ".join(str(c) for c in (brand_dna.get("palette_direction") or [])[:6])
    approved = "; ".join(str(d) for d in (brand_dna.get("approved_graphic_devices") or [])[:4])
    forbidden = "; ".join(str(d) for d in (brand_dna.get("forbidden_elements") or [])[:4])

    user_text = (
        f"## Brand DNA\nPalette: {palette}\nApproved devices: {approved}\n"
        f"Forbidden: {forbidden}\n\n## Brief\n{brief[:1500]}\n\n"
        "Analyze the attached image against the brand DNA and brief. Return JSON only."
    )

    parsed = _run_vlm_json(image_path, VLM_CRITIQUE_SYSTEM, user_text, max_tokens=1024)
    if parsed is None:
        return _vlm_stub("No VLM API key available (set ANTHROPIC_API_KEY or OPENAI_API_KEY)")
    return _parse_vlm_json(json.dumps(parsed))


def _parse_vlm_json(text: str) -> dict:
    """Extract JSON from VLM response text."""
    data = _extract_json_dict(text)
    if isinstance(data, dict):
        data.setdefault("approved", not bool(data.get("p1")))
        data.setdefault("p1", [])
        data.setdefault("p2", [])
        data.setdefault("p3", [])
        data.setdefault("clean", [])
        data.setdefault("refinement_suggestion", "")
        data["vlm_available"] = True
        return data
    return _vlm_stub(f"VLM returned unparseable response: {text[:200]}")


def _vlm_stub(reason: str) -> dict:
    """Return a stub critique when VLM is unavailable."""
    return {
        "approved": False,
        "p1": [],
        "p2": [],
        "p3": [],
        "clean": [],
        "palette_match": 0.0,
        "logo_visible": False,
        "hallucinated_elements": [],
        "composition_notes": "",
        "refinement_suggestion": "",
        "vlm_available": False,
        "vlm_unavailable_reason": reason,
    }


# ---------------------------------------------------------------------------
# Iteration loop helper — Hole 3 fix: generate → VLM critique → refine → re-generate
# ---------------------------------------------------------------------------

def refine_prompt_from_vlm_critique(effective_prompt: str, vlm_critique: dict) -> str:
    """Produce a refined prompt by incorporating VLM critique feedback."""
    suggestion = (vlm_critique.get("refinement_suggestion") or "").strip()
    p1_items = vlm_critique.get("p1") or []
    hallucinated = vlm_critique.get("hallucinated_elements") or []

    additions: list[str] = []
    if hallucinated:
        additions.append(f"Remove these hallucinated elements: {', '.join(str(h) for h in hallucinated[:3])}.")
    if p1_items:
        for issue in p1_items[:2]:
            additions.append(f"Fix: {issue}")
    if suggestion and suggestion not in effective_prompt:
        additions.append(suggestion)

    if not additions:
        return effective_prompt

    refinement_block = " ".join(additions)
    return f"{effective_prompt}\n\nRefinements from visual review: {refinement_block}"


# ---------------------------------------------------------------------------
# Inspiration pipeline auto-check — Hole 5 fix
# ---------------------------------------------------------------------------

def check_inspiration_pipeline_status(brand_gen_dir: Path | None, active_brand: str | None, workflow_mode: str | None) -> dict:
    """Check whether the inspiration pipeline is properly configured for the current mode.

    Returns a dict with status info and any warnings.
    """
    resolved = brand_gen_dir or get_brand_gen_dir()
    brand_key = active_brand or (resolve_active_brand_key(resolved) if resolved else None)
    warnings: list[str] = []
    suggestions: list[str] = []

    if workflow_mode not in ("hybrid", "inspiration"):
        return {"ok": True, "warnings": [], "suggestions": [], "mode": workflow_mode or "reference"}

    if not resolved or not brand_key:
        warnings.append("No .brand-gen workspace or active brand found; inspiration pipeline cannot load.")
        suggestions.append("Run: python3 mcp/brand_iterate.py init --brand-name <name>")
        return {"ok": False, "warnings": warnings, "suggestions": suggestions, "mode": workflow_mode or ""}

    config = load_brand_gen_config(resolved)
    inspiration_config = load_inspirations_config(brand_key, resolved)
    sources = inspiration_config.get("sources") or []
    index = load_inspiration_index(resolved).get("sources", {})

    if not sources:
        warnings.append(f"Brand '{brand_key}' has no inspiration sources configured.")
        suggestions.append(f"Run: python3 mcp/brand_iterate.py inspire {brand_key} --sources linear,vercel,raycast")

    incomplete = []
    for key in sources:
        item = index.get(key)
        if not item or item.get("status") != "complete":
            incomplete.append(key)
    if incomplete:
        warnings.append(f"Inspiration sources not yet extracted: {', '.join(incomplete)}")
        suggestions.append(f"Run: python3 mcp/brand_iterate.py extract-inspiration --sources {','.join(incomplete)}")

    if not config.get("inspirationMode") and workflow_mode == "inspiration":
        warnings.append("inspirationMode is off but workflow mode is 'inspiration'; tokens will not be injected.")
        suggestions.append("Run: python3 mcp/brand_iterate.py inspiration-mode on")

    return {
        "ok": len(warnings) == 0,
        "warnings": warnings,
        "suggestions": suggestions,
        "mode": workflow_mode or "",
        "sources_configured": len(sources),
        "sources_ready": len(sources) - len(incomplete),
    }


# ---------------------------------------------------------------------------
# Smarter routing — Hole 6 fix: LLM-assisted route classification
# ---------------------------------------------------------------------------

def classify_workflow_route_smart(material_type: str | None, goal: str = "", request: str = "", has_motion_reference: bool = False, set_scope: bool = False) -> dict:
    """Enhanced route classification using LLM when available, falling back to keyword matching."""
    # Try LLM-based classification first
    env = build_env()
    api_key = env.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY") or env.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")

    if api_key and (goal or request):
        try:
            result = _llm_classify_route(material_type, goal, request, has_motion_reference, set_scope, env)
            if result:
                return result
        except Exception as exc:
            print(f"LLM routing fallback: {exc}", file=sys.stderr)

    rules = load_workflow_router_rules()
    routes = rules.get("routes") or []
    route = next((item for item in routes if item.get("key") == "generative_explore"), {}) or {
        "key": "generative_explore",
        "label": "generative explore",
        "specialists": ["brand_director", "visual_composer", "critic_agent"],
        "required_assets": [],
        "next_commands": [],
        "notes": "",
    }
    return {
        "route_key": "generative_explore",
        "route": route,
        "material_key": role_pack_material_key(material_type),
        "llm_routed": False,
        "score": 0.0,
        "method": "default",
        "score_vector": {},
    }


def _llm_classify_route(material_type: str | None, goal: str, request: str, has_motion_reference: bool, set_scope: bool, env: dict) -> dict | None:
    """Use a small LLM call to classify the workflow route."""
    rules = load_workflow_router_rules()
    routes = rules.get("routes") or []
    route_descriptions = "\n".join(
        f"- {r['key']}: {r.get('notes', '')} (specialists: {', '.join(r.get('specialists', []))})"
        for r in routes
    )

    classify_prompt = (
        f"Classify this brand material request into exactly one route key.\n\n"
        f"Available routes:\n{route_descriptions}\n\n"
        f"Request:\n- Material type: {material_type or 'not specified'}\n"
        f"- Goal: {goal or 'not specified'}\n"
        f"- Request: {request or 'not specified'}\n"
        f"- Has motion reference: {has_motion_reference}\n"
        f"- Set scope: {set_scope}\n\n"
        f"Return ONLY the route key (e.g. 'reference_translate'). No explanation."
    )

    route_keys = {r["key"] for r in routes}

    # Try Anthropic
    anthropic_key = env.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        try:
            import httpx
            resp = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": anthropic_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={
                    "model": "claude-haiku-4-20250514",
                    "max_tokens": 50,
                    "messages": [{"role": "user", "content": classify_prompt}],
                },
                timeout=10.0,
            )
            if resp.status_code == 200:
                text = "".join(b.get("text", "") for b in resp.json().get("content", [])).strip().lower()
                for key in route_keys:
                    if key in text:
                        route = next((r for r in routes if r["key"] == key), None)
                        if route:
                            return {
                                "route_key": key,
                                "route": route,
                                "material_key": role_pack_material_key(material_type),
                                "llm_routed": True,
                            }
        except Exception:
            pass

    # Try OpenAI
    openai_key = env.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if openai_key:
        try:
            import httpx
            resp = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                json={
                    "model": "gpt-4o-mini",
                    "max_tokens": 50,
                    "messages": [{"role": "user", "content": classify_prompt}],
                },
                timeout=10.0,
            )
            if resp.status_code == 200:
                text = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip().lower()
                for key in route_keys:
                    if key in text:
                        route = next((r for r in routes if r["key"] == key), None)
                        if route:
                            return {
                                "route_key": key,
                                "route": route,
                                "material_key": role_pack_material_key(material_type),
                                "llm_routed": True,
                            }
        except Exception:
            pass

    return None


def execute_generation_scratchpad(payload: dict, workflow_id: str | None = None) -> str:
    if payload.get("schema_type") != "generation_scratchpad":
        raise SystemExit("Scratchpad is not a generation_scratchpad payload.")
    blocking = (((payload.get("checks") or {}).get("blocking")) or [])
    if blocking:
        raise SystemExit("Generation scratchpad has blocking issues. Fix them or rebuild the scratchpad before generating.")

    brand_dir = Path(payload["brand_dir"]).expanduser().resolve()
    brand_dir.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    vnum = next_version_num(manifest)
    vid = f"v{vnum}"

    execution = payload.get("execution") or {}
    generation_mode = payload.get("generation_mode") or "image"
    model = execution.get("model") or ""
    model_config = MODELS.get(generation_mode, {}).get(model)
    if not model_config:
        raise SystemExit(f"Model '{model}' is not available for {generation_mode} generation.")
    ext = model_config.get("output_format", "png" if generation_mode == "image" else "mp4")
    slug = str(payload.get("tag") or payload.get("material_type") or "brand").replace(" ", "-").lower()
    out_file = brand_dir / f"{vid}-{slug}.{ext}"
    effective_prompt = payload.get("effective_prompt") or ""

    cmd = [sys.executable, str(GENERATE_PY), generation_mode, "-m", model, "-p", effective_prompt, "-o", str(out_file)]
    if execution.get("aspect_ratio"):
        cmd += ["--aspect-ratio", str(execution["aspect_ratio"])]
    if execution.get("resolution"):
        cmd += ["--resolution", str(execution["resolution"])]
    if execution.get("preset"):
        cmd += ["--preset", str(execution["preset"])]
    if execution.get("style"):
        cmd += ["--style", str(execution["style"])]
    if execution.get("negative_prompt"):
        cmd += ["--negative-prompt", str(execution["negative_prompt"])]
    if generation_mode == "video" and execution.get("duration"):
        cmd += ["--duration", str(execution["duration"])]
    if execution.get("motion_reference"):
        cmd += ["--motion-reference", str(execution["motion_reference"])]
    if execution.get("motion_mode"):
        cmd += ["--motion-mode", str(execution["motion_mode"])]
    if execution.get("character_orientation"):
        cmd += ["--character-orientation", str(execution["character_orientation"])]
    if execution.get("keep_original_sound"):
        cmd += ["--keep-original-sound"]
    for ref in (payload.get("reference_context") or {}).get("passed_reference_paths", []):
        cmd += ["-i", str(ref)]
    for tag in execution.get("reference_tags", []) or []:
        cmd += ["--reference-tag", tag]

    env = build_env()
    print(f"Generating {vid} ({payload.get('material_type')}, {generation_mode}, {model}, mode={payload.get('workflow_mode')})...")
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        raise SystemExit(result.returncode)

    files = [out_file.name]
    staged_sources = [Path(path) for path in ((payload.get("reference_context") or {}).get("all_context_refs") or [])]
    motion_reference = execution.get("motion_reference") or ""
    if motion_reference:
        staged_sources.append(Path(motion_reference))
    staged_refs = stage_reference_assets(vid, staged_sources, brand_dir)

    gif_file = None
    if generation_mode == "video" and (execution.get("make_gif") or payload.get("material_type") == "gif"):
        gif_file = convert_video_to_gif(out_file)
        if gif_file is not None:
            files.append(gif_file.name)

    manifest["versions"][vid] = {
        "prompt": effective_prompt,
        "raw_prompt": payload.get("raw_prompt") or "",
        "prompt_prelude": "\n\n".join(
            part for part in [
                ((payload.get("prompt_context") or {}).get("brand_prelude") or ""),
                ((payload.get("prompt_context") or {}).get("material_prompt_snippet") or ""),
                ((payload.get("prompt_context") or {}).get("reference_role_pack_snippet") or ""),
                ((payload.get("prompt_context") or {}).get("inspiration_doctrine") or ""),
            ] if part
        ),
        "material_prompt_key": (payload.get("prompt_context") or {}).get("material_prompt_key", ""),
        "material_prompt_variant": (payload.get("prompt_context") or {}).get("material_prompt_variant", ""),
        "material_prompt_snippet": (payload.get("prompt_context") or {}).get("material_prompt_snippet", ""),
        "reference_role_pack": (payload.get("prompt_context") or {}).get("reference_role_pack", []),
        "reference_role_pack_priority": (payload.get("prompt_context") or {}).get("reference_role_pack_priority", []),
        "reference_role_pack_prefer_unique_sources": (payload.get("prompt_context") or {}).get("reference_role_pack_prefer_unique_sources", True),
        "reference_role_pack_required_roles": (payload.get("prompt_context") or {}).get("reference_role_pack_required_roles", []),
        "reference_role_pack_missing_roles": (payload.get("prompt_context") or {}).get("reference_role_pack_missing_roles", []),
        "reference_role_pack_missing_required_roles": (payload.get("reference_context") or {}).get("missing_required_roles", []),
        "reference_tags": execution.get("reference_tags", []),
        "token_block": (payload.get("prompt_context") or {}).get("token_block", ""),
        "model": model,
        "mode": payload.get("workflow_mode") or "",
        "material_type": payload.get("material_type") or "",
        "generation_mode": generation_mode,
        "aspect_ratio": execution.get("aspect_ratio") or "",
        "duration": execution.get("duration"),
        "tag": payload.get("tag") or "",
        "files": files,
        "reference_images": staged_refs,
        "reference_count": len(staged_refs),
        "reference_dir": "",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "score": None,
        "notes": "",
        "status": None,
        "prompt_review": dict(payload.get("prompt_review") or {}, scratchpad=(payload.get("prompt_review") or {}).get("scratchpad") or ""),
        "generation_scratchpad": payload.get("_scratchpad_path") or "",
        "workflow_id": workflow_id or "",
        "prompt_char_count": len(effective_prompt),
    }
    manifest["versions"][vid]["critic_summary"] = build_structural_auto_critic(payload)
    save_manifest(manifest)
    auto_review_path, auto_review_ok = run_auto_brand_review(brand_dir, vid)
    manifest["versions"][vid]["auto_review_path"] = auto_review_path if auto_review_ok else ""
    save_manifest(manifest)
    profile_path = payload.get("profile_path") or None
    identity_path = payload.get("identity_path") or None
    _, _, profile, identity = load_brand_memory(brand_dir, profile_path, identity_path)
    persist_generated_asset_to_blackboard(
        brand_dir,
        profile,
        identity,
        version_id=vid,
        entry=manifest["versions"][vid],
        scratchpad_path=payload.get("_scratchpad_path") or "",
        auto_review_path=manifest["versions"][vid].get("auto_review_path") or "",
        critic_summary=manifest["versions"][vid].get("critic_summary") or {},
        workflow_id=workflow_id,
    )
    print(f"Done: {vid} -> {out_file.name}")
    return vid


def cmd_ideate_material(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    _, _, profile, identity = load_brand_memory(brand_dir, args.profile, args.identity)
    candidates = suggest_reference_role_pack(brand_dir, args.material_type)
    tracks = default_idea_tracks(args.material_type)
    questions = default_alignment_questions(args.material_type)
    brand_name = ((identity.get("brand") or {}).get("name") or profile.get("brand_name") or "the brand").strip()
    for track in tracks:
        recommended_roles = {}
        for role in (candidates.get("priority") or []):
            items = candidates.get("candidates", {}).get(role) or []
            if items:
                recommended_roles[role] = items[0]["source_key"]
        track["recommended_roles"] = recommended_roles
        if args.goal:
            track["why"] = f"{track['why']} This is especially relevant if the goal is: {args.goal}."
    out = {
        "brand": brand_name,
        "material_type": args.material_type,
        "mode": args.mode,
        "goal": args.goal or "",
        "use_surface": args.use_surface or "",
        "concern": args.concern or "",
        "tracks": tracks,
        "alignment_questions": questions,
        "next_step": f"Pick one track, then run: plan-material --material-type {args.material_type} --mode {args.mode} --mechanic \"<chosen mechanic>\" ...",
    }
    if args.format == "json":
        print(json.dumps(out, indent=2))
        return
    print(f"{brand_name} {args.material_type} ideation\n")
    if args.goal:
        print(f"Goal: {args.goal}")
    if args.use_surface:
        print(f"Surface: {args.use_surface}")
    if args.concern:
        print(f"Concern: {args.concern}")
    print("")
    for idx, track in enumerate(tracks, 1):
        print(f"{idx}. {track['name']}")
        print(f"   mechanic: {track['mechanic']}")
        print(f"   why: {track['why']}")
        print(f"   preserve: {', '.join(track['preserve'])}")
        print(f"   push: {', '.join(track['push'])}")
        print(f"   ban: {', '.join(track['ban'])}")
        if track.get("recommended_roles"):
            print(f"   refs: {', '.join(f'{k}={v}' for k, v in track['recommended_roles'].items())}")
        print("")
    print("Alignment questions:")
    for item in questions:
        print(f"- {item}")
    print(f"\nNext step:\n{out['next_step']}")


def cmd_ideate_copy(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    _, _, profile, identity = load_brand_memory(brand_dir, args.profile, args.identity)
    payload = derive_copy_candidates(profile, identity, args.material_type, goal=args.goal or "", surface=args.surface or "", brand_dir=brand_dir)
    if args.format == "json":
        print(json.dumps(payload, indent=2))
        return
    print(f"{payload['brand_name']} copy ideation — {payload['material_type']}\n")
    if payload["goal"]:
        print(f"Goal: {payload['goal']}")
    if payload["surface"]:
        print(f"Surface: {payload['surface']}")
    messaging = payload.get("messaging") or {}
    if messaging.get("tagline") or messaging.get("elevator"):
        print("\nMessaging context:")
        if messaging.get("tagline"):
            print(f"- Tagline: {messaging['tagline']}")
        if messaging.get("elevator"):
            print(f"- Elevator: {messaging['elevator']}")
        if messaging.get("iteration_notes"):
            print("- Messaging notes:")
            for item in messaging["iteration_notes"]:
                print(f"  - {item}")
    print("\nHeadline candidates:")
    for item in payload["headlines"]:
        print(f"- {item}")
    print("\nSlogan candidates:")
    for item in payload["slogans"]:
        print(f"- {item}")
    print("\nSubheadline candidates:")
    for item in payload["subheadlines"]:
        print(f"- {item}")
    print("\nCTA pairs:")
    for item in payload["cta_pairs"]:
        print(f"- {item['primary']} / {item['secondary']}")
    print("\nVisual angles:")
    for item in payload["visual_angles"]:
        print(f"- {item}")
    print("\nAvoid:")
    for item in payload["anti_patterns"]:
        print(f"- {item}")


def cmd_update_messaging(args):
    """Update the messaging section of the active brand identity."""
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    _, identity_path, profile, identity = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))
    messaging = identity.get("messaging") or {}
    copy_bank = messaging.get("approved_copy_bank") or {}
    changed = False

    if args.tagline:
        messaging["tagline"] = args.tagline.strip()
        changed = True
    if args.elevator:
        messaging["elevator"] = args.elevator.strip()
        changed = True
    if args.voice_description:
        voice = messaging.get("voice") or {}
        voice["description"] = args.voice_description.strip()
        messaging["voice"] = voice
        changed = True
    if args.add_value_prop:
        props = messaging.get("value_propositions") or []
        for prop in args.add_value_prop:
            prop = prop.strip()
            if prop and prop not in props:
                props.append(prop)
        messaging["value_propositions"] = props
        changed = True
    if args.add_headline:
        headlines = copy_bank.get("headlines") or []
        for h in args.add_headline:
            h = h.strip()
            if h and h not in headlines:
                headlines.append(h)
        copy_bank["headlines"] = headlines
        changed = True
    if args.add_slogan:
        slogans = copy_bank.get("slogans") or []
        for s in args.add_slogan:
            s = s.strip()
            if s and s not in slogans:
                slogans.append(s)
        copy_bank["slogans"] = slogans
        changed = True
    if args.add_subheadline:
        subs = copy_bank.get("subheadlines") or []
        for s in args.add_subheadline:
            s = s.strip()
            if s and s not in subs:
                subs.append(s)
        copy_bank["subheadlines"] = subs
        changed = True

    if not changed:
        print("No messaging updates provided. Use --tagline, --elevator, --add-headline, etc.")
        return

    messaging["approved_copy_bank"] = copy_bank
    identity["messaging"] = messaging
    identity["schema_version"] = max(identity.get("schema_version", 1), 2)
    identity_path.write_text(json.dumps(identity, indent=2) + "\n")
    memory = load_iteration_memory(brand_dir)
    note_parts: list[str] = []
    if args.tagline:
        note_parts.append(f"Approved tagline: {args.tagline.strip()}")
    if args.elevator:
        note_parts.append(f"Approved elevator: {args.elevator.strip()}")
    if args.voice_description:
        note_parts.append(f"Voice direction: {args.voice_description.strip()}")
    if args.add_value_prop:
        note_parts.extend([f"Value prop: {item.strip()}" for item in args.add_value_prop if str(item).strip()])
    if note_parts:
        for item in note_parts[-5:]:
            memory = add_iteration_note(memory, item, bucket="messaging_notes")
        save_iteration_memory(brand_dir, memory)
    print(f"Messaging updated in {identity_path}")
    if args.format == "json":
        print(json.dumps(messaging, indent=2))
    else:
        if messaging.get("tagline"):
            print(f"Tagline: {messaging['tagline']}")
        if messaging.get("elevator"):
            print(f"Elevator: {messaging['elevator'][:120]}...")
        if messaging.get("value_propositions"):
            print(f"Value props: {len(messaging['value_propositions'])}")
        if copy_bank.get("headlines"):
            print(f"Headlines: {len(copy_bank['headlines'])}")
        if copy_bank.get("slogans"):
            print(f"Slogans: {len(copy_bank['slogans'])}")


def cmd_ideate_messaging(args):
    """Assemble brand context for messaging ideation. The calling agent generates the angles."""
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    _, _, profile, identity = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))
    brand_name = ((identity.get("brand") or {}).get("name") or profile.get("brand_name") or "Brand").strip()
    summary = ((identity.get("brand") or {}).get("summary") or profile.get("description") or "").strip()
    tone_words = (identity.get("identity_core") or {}).get("tone_words") or profile.get("keywords") or []
    identity_core = identity.get("identity_core") or {}
    messaging = identity.get("messaging") or {}
    memory = load_iteration_memory(brand_dir)
    copy_notes = memory.get("copy_notes") or []
    brand_notes = memory.get("brand_notes") or []
    messaging_notes = memory.get("messaging_notes") or []

    # Assemble full brand context for the calling agent to reason over
    context: dict = {
        "brand_name": brand_name,
        "summary": summary,
        "tone_words": tone_words[:10],
    }

    # Identity core signals
    if identity_core.get("approved_primitives"):
        context["visual_primitives"] = identity_core["approved_primitives"][:4]
    if identity_core.get("brand_truth_rules"):
        context["brand_truth_rules"] = identity_core["brand_truth_rules"][:3]
    if identity_core.get("forbidden_elements"):
        context["forbidden_elements"] = identity_core["forbidden_elements"][:3]

    # Current messaging state (what exists already)
    current: dict = {}
    if messaging.get("tagline"):
        current["tagline"] = messaging["tagline"]
    if messaging.get("elevator"):
        current["elevator"] = messaging["elevator"]
    if messaging.get("voice"):
        current["voice"] = messaging["voice"]
    if messaging.get("value_propositions"):
        current["value_propositions"] = messaging["value_propositions"]
    copy_bank = messaging.get("approved_copy_bank") or {}
    if copy_bank.get("headlines"):
        current["approved_headlines"] = copy_bank["headlines"]
    if copy_bank.get("slogans"):
        current["approved_slogans"] = copy_bank["slogans"]

    # Iteration history — what the team has said about messaging so far
    iteration: dict = {}
    if messaging_notes:
        iteration["messaging_notes"] = messaging_notes[-8:]
    if copy_notes:
        iteration["copy_notes"] = copy_notes[-5:]
    if brand_notes:
        iteration["brand_notes"] = brand_notes[-5:]
    # Include positioning/copy insights promoted from previous sessions
    if messaging.get("positioning_insights"):
        iteration["positioning_insights"] = messaging["positioning_insights"][-5:]
    if messaging.get("copy_insights"):
        iteration["copy_insights"] = messaging["copy_insights"][-5:]

    payload: dict = {
        "brand_context": context,
        "current_messaging": current if current else None,
        "iteration_history": iteration if iteration else None,
        "instructions": (
            "Generate 3-5 positioning angles for this brand. Each angle should have: "
            "a short label, a tagline (≤10 words), an elevator pitch (1-2 sentences), "
            "and a voice direction (1 sentence). Make each angle genuinely different — "
            "vary the framing, audience, and emotional register. Be specific to this product. "
            "Avoid: revolutionize, transform, unlock, empower, seamless, elevate, or any generic startup language."
        ),
        "next_steps": [
            "Pick an angle and run: update-messaging --tagline '<tagline>' --elevator '<elevator>'",
            "Or record a note: update-iteration-memory --kind messaging --note '<insight>'",
            "After iterating, promote to brand identity: promote-messaging",
        ],
    }

    if args.format == "json":
        print(json.dumps(payload, indent=2))
        return

    # Human-readable summary
    print(f"Messaging ideation context for {brand_name}\n")
    print(f"Summary: {summary}")
    if tone_words:
        print(f"Tone: {', '.join(tone_words[:8])}")
    if current:
        print(f"\nCurrent messaging:")
        if current.get("tagline"):
            print(f"  Tagline: {current['tagline']}")
        if current.get("elevator"):
            print(f"  Elevator: {current['elevator'][:120]}...")
        if current.get("voice", {}).get("description"):
            print(f"  Voice: {current['voice']['description'][:100]}...")
        if current.get("value_propositions"):
            print(f"  Value props: {len(current['value_propositions'])}")
        if current.get("approved_headlines"):
            print(f"  Headlines: {len(current['approved_headlines'])}")
    if iteration:
        print(f"\nIteration history:")
        for key in ("messaging_notes", "copy_notes", "brand_notes", "positioning_insights", "copy_insights"):
            items = iteration.get(key) or []
            if items:
                print(f"  {key} ({len(items)}):")
                for note in items[-3:]:
                    print(f"    - {note}")
    print(f"\nThe agent should now generate 3-5 positioning angles from this context.")


def cmd_promote_messaging(args):
    """Promote session messaging (copy_notes + identity messaging) to the saved brand."""
    brand_gen_dir = get_brand_gen_dir()
    if not brand_gen_dir:
        raise SystemExit("No .brand-gen directory found.")
    brand_dir = get_brand_dir()
    config = load_brand_gen_config(brand_gen_dir)
    active_brand = resolve_active_brand_key(brand_gen_dir)
    if not active_brand:
        raise SystemExit("No active brand. Run: use <brand>")
    saved_identity_path = brand_gen_dir / "brands" / active_brand / "brand-identity.json"
    if not saved_identity_path.exists():
        raise SystemExit(f"Saved brand identity not found: {saved_identity_path}")

    # Load session identity and saved identity
    _, _, _, session_identity = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))
    saved_identity = load_json_file(saved_identity_path)

    # Merge messaging from session into saved brand
    session_messaging = session_identity.get("messaging") or {}
    saved_messaging = saved_identity.get("messaging") or {}

    if not session_messaging and not args.include_copy_notes:
        print("No messaging to promote. Run update-messaging first or use --include-copy-notes.")
        return

    # Promote structured messaging fields
    for field in ("tagline", "elevator"):
        if session_messaging.get(field):
            saved_messaging[field] = session_messaging[field]
    if session_messaging.get("voice"):
        saved_messaging["voice"] = session_messaging["voice"]
    if session_messaging.get("value_propositions"):
        existing = saved_messaging.get("value_propositions") or []
        for prop in session_messaging["value_propositions"]:
            if prop not in existing:
                existing.append(prop)
        saved_messaging["value_propositions"] = existing

    # Promote copy bank entries
    session_bank = session_messaging.get("approved_copy_bank") or {}
    saved_bank = saved_messaging.get("approved_copy_bank") or {}
    for bucket in ("headlines", "slogans", "subheadlines"):
        session_items = session_bank.get(bucket) or []
        saved_items = saved_bank.get(bucket) or []
        for item in session_items:
            if item not in saved_items:
                saved_items.append(item)
        if saved_items:
            saved_bank[bucket] = saved_items
    if session_bank.get("cta_pairs"):
        saved_bank["cta_pairs"] = session_bank["cta_pairs"]
    saved_messaging["approved_copy_bank"] = saved_bank

    # Optionally promote iteration notes as messaging insights (kept separate by type)
    if args.include_copy_notes:
        memory = load_iteration_memory(brand_dir)
        messaging_notes = list(memory.get("messaging_notes") or [])
        copy_notes = list(memory.get("copy_notes") or [])
        if messaging_notes:
            existing = saved_messaging.get("positioning_insights") or []
            for note in messaging_notes:
                if note not in existing:
                    existing.append(note)
            saved_messaging["positioning_insights"] = existing[-15:]
        if copy_notes:
            existing = saved_messaging.get("copy_insights") or []
            for note in copy_notes:
                if note not in existing:
                    existing.append(note)
            saved_messaging["copy_insights"] = existing[-15:]

    saved_identity["messaging"] = saved_messaging
    saved_identity["schema_version"] = max(saved_identity.get("schema_version", 1), 2)
    saved_identity_path.write_text(json.dumps(saved_identity, indent=2) + "\n")
    print(f"Messaging promoted to {saved_identity_path}")
    if saved_messaging.get("tagline"):
        print(f"  Tagline: {saved_messaging['tagline']}")
    if saved_messaging.get("elevator"):
        print(f"  Elevator: {saved_messaging['elevator'][:80]}...")
    if saved_messaging.get("value_propositions"):
        print(f"  Value props: {len(saved_messaging['value_propositions'])}")
    bank = saved_messaging.get("approved_copy_bank") or {}
    for bucket in ("headlines", "slogans", "subheadlines"):
        items = bank.get(bucket) or []
        if items:
            print(f"  {bucket.title()}: {len(items)}")


def cmd_show_iteration_memory(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    memory = load_iteration_memory(brand_dir)
    json_path, md_path = iteration_memory_paths(brand_dir)
    if args.format == "json":
        print(json.dumps({"paths": {"json": str(json_path), "markdown": str(md_path)}, "memory": memory}, indent=2))
        return
    print(f"Iteration memory JSON: {json_path}")
    print(f"Iteration memory markdown: {md_path}\n")
    print(render_iteration_memory_markdown(memory))


def cmd_update_iteration_memory(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    memory = load_iteration_memory(brand_dir)
    material_type = args.material_type or ""
    if args.note:
        if args.kind == "material":
            memory = add_iteration_note(memory, args.note, material_type=material_type, bucket="material")
        elif args.kind == "copy":
            memory = add_iteration_note(memory, args.note, bucket="copy_notes")
        elif args.kind == "messaging":
            memory = add_iteration_note(memory, args.note, bucket="messaging_notes")
        else:
            memory = add_iteration_note(memory, args.note, bucket="brand_notes")
    if args.negative:
        memory["negative_examples"].append({
            "version": args.version or "note",
            "material_type": material_type,
            "summary": args.negative,
            "score": args.score,
            "status": "rejected" if args.score is not None and args.score <= 2 else "",
        })
        memory["negative_examples"] = memory["negative_examples"][-20:]
    if args.positive:
        memory["positive_examples"].append({
            "version": args.version or "note",
            "material_type": material_type,
            "summary": args.positive,
            "score": args.score,
            "status": "favorite" if args.score is not None and args.score >= 4 else "",
        })
        memory["positive_examples"] = memory["positive_examples"][-20:]
    json_path, md_path = save_iteration_memory(brand_dir, memory)
    if args.format == "json":
        print(json.dumps({"json": str(json_path), "markdown": str(md_path), "memory": memory}, indent=2))
        return
    print(f"Updated iteration memory:\n- {json_path}\n- {md_path}")


def preferred_material_engine(material_type: str) -> str:
    return "generate"


def cmd_plan_set(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    _, identity_path, profile, identity = load_brand_memory(brand_dir, args.profile, args.identity)
    template_key = (args.template or "product-core").strip().lower().replace("-", "_")
    template = MATERIAL_SET_TEMPLATES.get(template_key)
    if not template:
        raise SystemExit(f"Unknown set template '{args.template}'. Available: {', '.join(sorted(k.replace('_', '-') for k in MATERIAL_SET_TEMPLATES))}")
    brand_name = ((identity.get("brand") or {}).get("name") or profile.get("brand_name") or "brand").strip()
    set_slug = slugify(args.set_name or f"{brand_name}-{template_key}")
    goal = args.goal or template.get("description") or f"Build a {template_key.replace('_', ' ')} material set for {brand_name}."
    set_surface = args.surface or "multi-surface brand set"
    plans_dir = brand_dir / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    materials: list[dict] = []
    for item in template.get("materials") or []:
        material_type = item["material_type"]
        policy = normalize_material_brand_policy(material_type, identity=identity)
        plan, missing_required = create_material_plan(
            brand_dir=brand_dir,
            identity_path=identity_path,
            identity=identity,
            material_type=material_type,
            mode=args.mode,
            mechanic=item.get("mechanic") or "",
            preserve=[],
            push=[],
            ban=[],
            picks={},
            purpose=item.get("purpose") or policy.get("purpose") or "",
            target_surface=item.get("target_surface") or args.surface or policy.get("target_surface") or "",
            product_truth_expression=item.get("product_truth_expression") or policy.get("product_truth_expression") or "",
            abstraction_level=item.get("abstraction_level") or policy.get("abstraction_level") or "",
            set_membership={
                "set_name": set_slug,
                "set_role": item.get("role") or policy.get("role") or "",
                "template": template_key,
            },
        )
        plan_path = plans_dir / f"{set_slug}-{slugify(material_type)}.json"
        plan_path.write_text(json.dumps(plan, indent=2) + "\n")
        materials.append(
            {
                "material_type": material_type,
                "material_key": role_pack_material_key(material_type),
                "role": item.get("role") or policy.get("role") or "",
                "target_surface": plan.get("target_surface") or "",
                "product_truth_expression": plan.get("product_truth_expression") or "",
                "abstraction_level": plan.get("abstraction_level") or "",
                "preferred_engine": preferred_material_engine(material_type),
                "plan_path": str(plan_path),
                "missing_required_roles": missing_required,
                "brand_anchor_rule": (plan.get("brand_anchor_policy") or {}).get("rule") or "",
            }
        )
    payload = {
        "version": 1,
        "set_name": set_slug,
        "brand_name": brand_name,
        "brand_dir": str(brand_dir),
        "identity_path": str(identity_path),
        "template": template_key,
        "goal": goal,
        "surface": set_surface,
        "set_brand_rule": "Every material must either show the stored logo/wordmark or satisfy its explicit clearly-branded anchor rule before it belongs in the set.",
        "inspiration_translation": {
            "rule": "Use agency inspiration only as translated mechanics for composition, motif logic, application attitude, or motion pacing. Brand truth remains the identity source."
        },
        "materials": materials,
    }
    sets_dir = brand_dir / "sets"
    sets_dir.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.output).expanduser().resolve() if args.output else sets_dir / f"{set_slug}.json"
    output_path.write_text(json.dumps(payload, indent=2) + "\n")
    report = validate_set_manifest_dict(payload)
    if args.format == "json":
        print(json.dumps({"set": payload, "validation": report}, indent=2))
        return
    print(f"Material set written to: {output_path}\n")
    print(f"Brand: {brand_name}")
    print(f"Template: {template_key}")
    print(f"Goal: {goal}")
    print(f"Surface: {set_surface}")
    print(f"Validation: {'ok' if report['ok'] else 'needs work'} ({report['score']}/{report['max_score']})")
    print("\nMaterials:")
    for item in materials:
        print(f"- {item['material_type']}: {item['role']} [{item['preferred_engine']}]")
        print(f"  surface: {item['target_surface']}")
        print(f"  product truth: {item['product_truth_expression']}")
        print(f"  brand rule: {item['brand_anchor_rule']}")
        print(f"  plan: {item['plan_path']}")
    if report["warnings"]:
        print("\nWarnings:")
        for warning in report["warnings"]:
            print(f"- {warning}")


def cmd_validate_brand_fit(args):
    if not args.plan and not args.set:
        raise SystemExit("Specify --plan or --set.")
    if args.plan:
        _, plan = load_plan_payload(Path(args.plan).expanduser().resolve())
        report = validate_material_plan_dict(plan)
    else:
        payload = load_json_file(Path(args.set).expanduser().resolve())
        report = validate_set_manifest_dict(payload)
    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(f"Status: {'ok' if report['ok'] else 'needs work'}")
        print(f"Score: {report['score']}/{report['max_score']}")
        if report["errors"]:
            print("\nErrors:")
            for item in report["errors"]:
                print(f"- {item}")
        if report["warnings"]:
            print("\nWarnings:")
            for item in report["warnings"]:
                print(f"- {item}")
    if args.strict and (report["errors"] or report["warnings"]):
        sys.exit(1)


def cmd_validate_set(args):
    payload = load_json_file(Path(args.set).expanduser().resolve())
    report = validate_set_manifest_dict(payload)
    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(f"Set validation: {'ok' if report['ok'] else 'needs work'}")
        print(f"Score: {report['score']}/{report['max_score']}")
        if report["errors"]:
            print("\nErrors:")
            for item in report["errors"]:
                print(f"- {item}")
        if report["warnings"]:
            print("\nWarnings:")
            for item in report["warnings"]:
                print(f"- {item}")
    if args.strict and (report["errors"] or report["warnings"]):
        sys.exit(1)


def _generate_set_member(item: dict, model_override: str | None, aspect_override: str | None) -> dict:
    """Generate a single set member. Designed to run in a thread pool."""
    material_type = item.get("material_type") or ""
    plan_path = item.get("plan_path") or ""
    try:
        scratch_cmd = [sys.executable, str(Path(__file__).resolve()), "build-generation-scratchpad", "--plan", plan_path, "--format", "json"]
        if model_override:
            scratch_cmd += ["--model", model_override]
        if aspect_override:
            scratch_cmd += ["--aspect-ratio", aspect_override]
        scratch_result = subprocess.run(scratch_cmd, capture_output=True, text=True, timeout=120)
        if scratch_result.returncode != 0:
            return {"material_type": material_type, "ok": False, "error": f"Scratchpad build failed: {scratch_result.stderr[:300]}"}
        scratch_payload = json.loads(scratch_result.stdout)
        scratchpad_path = scratch_payload["output"]
        gen_cmd = [sys.executable, str(Path(__file__).resolve()), "generate", "--scratchpad", scratchpad_path, "--skip-vlm"]
        gen_result = subprocess.run(gen_cmd, capture_output=True, text=True, timeout=300)
        if gen_result.returncode != 0:
            return {"material_type": material_type, "ok": False, "error": f"Generation failed: {gen_result.stderr[:300]}"}
        return {"material_type": material_type, "ok": True, "stdout": gen_result.stdout}
    except subprocess.TimeoutExpired:
        return {"material_type": material_type, "ok": False, "error": "Timed out"}
    except Exception as exc:
        return {"material_type": material_type, "ok": False, "error": str(exc)}


def cmd_generate_set(args):
    payload = load_json_file(Path(args.set).expanduser().resolve())
    report = validate_set_manifest_dict(payload)
    if not report["ok"]:
        raise SystemExit("Set validation failed. Run validate-set or validate-brand-fit first and fix the errors.")
    only = {item.strip() for item in (args.only or []) if item.strip()}
    skip = {item.strip() for item in (args.skip or []) if item.strip()}
    parallel = getattr(args, "parallel", False)
    max_workers = min(getattr(args, "workers", 3) or 3, 5)

    to_generate: list[dict] = []
    skipped: list[str] = []
    for item in payload.get("materials") or []:
        material_type = item.get("material_type") or ""
        if only and material_type not in only:
            continue
        if material_type in skip:
            skipped.append(f"{material_type}: skipped by user")
            continue
        engine = item.get("preferred_engine") or "generate"
        if engine != "generate":
            skipped.append(f"{material_type}: preferred engine is {engine}")
            continue
        to_generate.append(item)

    generated: list[str] = []
    failed: list[str] = []

    if parallel and len(to_generate) > 1:
        print(f"Generating {len(to_generate)} materials in parallel (max {max_workers} workers)...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    _generate_set_member,
                    item,
                    getattr(args, "model", None),
                    getattr(args, "aspect_ratio", None),
                ): item
                for item in to_generate
            }
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result["ok"]:
                    generated.append(result["material_type"])
                    if result.get("stdout"):
                        print(result["stdout"])
                else:
                    failed.append(f"{result['material_type']}: {result['error']}")
                    print(f"FAILED: {result['material_type']}: {result['error']}", file=sys.stderr)
    else:
        # Sequential (original behavior)
        for item in to_generate:
            material_type = item.get("material_type") or ""
            plan_path = item.get("plan_path") or ""
            scratch_cmd = [sys.executable, str(Path(__file__).resolve()), "build-generation-scratchpad", "--plan", plan_path, "--format", "json"]
            if args.model:
                scratch_cmd += ["--model", args.model]
            if args.aspect_ratio:
                scratch_cmd += ["--aspect-ratio", args.aspect_ratio]
            scratch_result = subprocess.run(scratch_cmd, capture_output=True, text=True)
            if scratch_result.returncode != 0:
                if scratch_result.stdout:
                    print(scratch_result.stdout)
                if scratch_result.stderr:
                    print(scratch_result.stderr, file=sys.stderr)
                raise SystemExit(scratch_result.returncode)
            scratch_payload = json.loads(scratch_result.stdout)
            scratchpad_path = scratch_payload["output"]
            cmd = [sys.executable, str(Path(__file__).resolve()), "generate", "--scratchpad", scratchpad_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.stdout:
                print(result.stdout)
            if result.returncode != 0:
                if result.stderr:
                    print(result.stderr, file=sys.stderr)
                raise SystemExit(result.returncode)
            generated.append(material_type)

    print(f"\nGenerated from set: {', '.join(generated) or 'none'}")
    if failed:
        print("Failed:")
        for item in failed:
            print(f"- {item}")
    if skipped:
        print("Skipped:")
        for item in skipped:
            print(f"- {item}")


def cmd_validate_identity(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    profile_path, identity_path, profile, identity = load_brand_memory(brand_dir, args.profile, args.identity)
    report = validate_identity_summary(profile_path, identity_path, profile, identity)

    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print("Brand identity validation\n")
        print(f"Status: {'ok' if report['ok'] else 'needs work'}")
        print(f"Score: {report['score']}/{report['max_score']}")
        print(f"Profile: {profile_path}")
        print(f"Identity: {identity_path}\n")
        print("Checks:")
        for key, passed in report["checks"].items():
            print(f"- {key}: {'pass' if passed else 'missing'}")
        if report["errors"]:
            print("\nErrors:")
            for item in report["errors"]:
                print(f"- {item}")
        if report["warnings"]:
            print("\nWarnings:")
            for item in report["warnings"]:
                print(f"- {item}")
    if args.strict and (report["errors"] or report["warnings"]):
        sys.exit(1)


def cmd_parse_design_memory(args):
    cmd = ["parse", "--path", args.path, "--format", args.format]
    if args.output_json:
        cmd += ["--output-json", args.output_json]
    run_child_script(DESIGN_MEMORY_LITE_PY, cmd)


def cmd_extract_css_variables(args):
    cmd = ["extract-css", "--path", args.path, "--format", args.format, "--max-files", str(args.max_files)]
    if args.output_json:
        cmd += ["--output-json", args.output_json]
    run_child_script(DESIGN_MEMORY_LITE_PY, cmd)


def cmd_diff_design_memory(args):
    cmd = ["diff", "--before", args.before, "--after", args.after, "--format", args.format]
    if args.output_json:
        cmd += ["--output-json", args.output_json]
    run_child_script(DESIGN_MEMORY_LITE_PY, cmd)


def cmd_init(args):
    brand_gen_dir = Path(args.brand_gen_dir).expanduser().resolve() if args.brand_gen_dir else (get_brand_gen_dir() or (REPO_ROOT / ".brand-gen"))
    if args.legacy_brand_dir:
        legacy_dir = Path(args.legacy_brand_dir).expanduser().resolve()
    else:
        candidate = get_legacy_brand_dir()
        legacy_dir = candidate.resolve() if candidate.exists() else None
    cmd = ["--brand-gen-dir", str(brand_gen_dir)]
    if args.brand_name:
        cmd += ["--brand-name", args.brand_name]
    if legacy_dir:
        cmd += ["--legacy-brand-dir", str(legacy_dir)]
    run_child_script(REPO_ROOT / "scripts" / "init_brand_gen.py", cmd)


def cmd_start_testing(args):
    brand_gen_dir = Path(args.brand_gen_dir).expanduser().resolve() if args.brand_gen_dir else (get_brand_gen_dir() or (REPO_ROOT / ".brand-gen"))
    brand_gen_dir.mkdir(parents=True, exist_ok=True)
    (brand_gen_dir / "sessions").mkdir(parents=True, exist_ok=True)
    session_key = slugify(args.session_name or args.working_name or args.brand or f"session-{time.strftime('%Y%m%d-%H%M%S')}")
    session_root = brand_gen_dir / "sessions" / session_key
    brand_dir = session_root / "brand-materials"
    brand_dir.mkdir(parents=True, exist_ok=True)
    for child in ["plans", "sets", "examples", "reviews", "references", "product-screens", "inspiration", "motion-references"]:
        (brand_dir / child).mkdir(parents=True, exist_ok=True)

    seeded_from = ""
    if args.brand:
        source_dir = brand_gen_dir / "brands" / args.brand
        if not source_dir.exists():
            raise SystemExit(f"Brand '{args.brand}' not found under {brand_gen_dir / 'brands'}")
        for path in source_dir.rglob('*'):
            rel = path.relative_to(source_dir)
            target = brand_dir / rel
            if path.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target)
        seeded_from = args.brand

    profile_path = brand_dir / "brand-profile.json"
    if profile_path.exists():
        profile_payload = load_json_file(profile_path)
    else:
        working_name = args.working_name or args.brand or "Working Brand"
        profile_payload = {
            "profile_version": 2,
            "brand_name": working_name,
            "description": args.goal or "Session brand under active exploration.",
            "project_root": str(brand_dir),
            "keywords": [],
            "color_candidates": [],
            "font_candidates": [],
            "radius_tokens": [],
            "logo_candidates": [],
            "brand_assets": {
                "icon": "",
                "wordmark": "",
                "lockup": "",
                "icon_candidates": [],
                "wordmark_candidates": [],
                "lockup_candidates": [],
                "allow_synthetic_lockup": False,
            },
            "design_language": {},
            "brand_guardrail_prelude": "",
        }
    profile_payload["session_context"] = {
        "type": "testing-session",
        "session_key": session_key,
        "seeded_from_brand": seeded_from,
        "goal": args.goal or "",
        "notes": "Build brand memory from reverse interviews, references, and iteration before promoting to a saved brand.",
    }
    profile_path.write_text(json.dumps(profile_payload, indent=2) + "\n")

    identity_path = brand_dir / "brand-identity.json"
    if not identity_path.exists():
        cmd = [sys.executable, str(BUILD_IDENTITY_PY), "--profile", str(profile_path), "--output-json", str(identity_path), "--output-markdown", str(brand_dir / "brand-identity.md")]
        subprocess.run(cmd, check=False)
    if identity_path.exists():
        identity_payload = load_json_file(identity_path)
        identity_payload["session_context"] = {
            "type": "testing-session",
            "session_key": session_key,
            "seeded_from_brand": seeded_from,
            "goal": args.goal or "",
        }
        identity_path.write_text(json.dumps(identity_payload, indent=2) + "\n")

    profile = load_json_file(profile_path)
    identity = load_json_file(identity_path)
    board = load_blackboard(brand_dir, profile, identity)
    append_blackboard_decision(
        board,
        agent="brand_director",
        decision=f"Started testing session '{session_key}'{' seeded from ' + seeded_from if seeded_from else ''}.",
        confidence=0.95,
        data={"goal": args.goal or "", "seeded_from_brand": seeded_from},
    )
    save_blackboard(brand_dir, board)

    config = load_brand_gen_config(brand_gen_dir)
    config["activeSession"] = session_key
    save_brand_gen_config(config, brand_gen_dir)
    print(f"Testing session: {session_key}")
    print(f"Session brand dir: {brand_dir}")
    if seeded_from:
        print(f"Seeded from brand: {seeded_from}")
    print("\nNext:")
    print(f"- Run the main skill in {REPO_ROOT / 'skills' / 'brand-gen' / 'SKILL.md'}")
    print(f"- Reverse interview into: {REPO_ROOT / 'prompts' / 'start-brand-testing.md'}")
    print("- Then route-request -> plan-draft -> critique-plan -> build-generation-scratchpad -> generate --scratchpad")


def cmd_use(args):
    brand_gen_dir = get_brand_gen_dir() or (REPO_ROOT / ".brand-gen")
    brand_dirs = list_brand_dirs(brand_gen_dir)
    if args.list_only:
        class _Args:
            format = "text"
        return cmd_list_brands(_Args())
    if not args.brand:
        raise SystemExit("Specify a brand key or use --list.")
    wanted = args.brand.strip()
    available = {path.name: path for path in brand_dirs}
    if wanted not in available:
        raise SystemExit(f"Brand '{wanted}' not found. Available: {', '.join(sorted(available)) or 'none'}")
    config = load_brand_gen_config(brand_gen_dir)
    config["active"] = wanted
    config["activeSession"] = None
    save_brand_gen_config(config, brand_gen_dir)
    print(f"Active brand: {wanted}")


def cmd_list_brands(args):
    brand_gen_dir = get_brand_gen_dir()
    if not brand_gen_dir:
        print("No .brand-gen directory found.")
        return
    active = resolve_active_brand_key(brand_gen_dir)
    items = []
    for brand_dir in list_brand_dirs(brand_gen_dir):
        profile = brand_dir / "brand-profile.json"
        identity = brand_dir / "brand-identity.json"
        inspirations = load_inspirations_config(brand_dir.name, brand_gen_dir)
        report = validate_identity_summary(profile, identity, load_json_file(profile), load_json_file(identity))
        items.append({
            "key": brand_dir.name,
            "active": brand_dir.name == active,
            "profile": profile.exists(),
            "identity": identity.exists(),
            "score": f"{report['score']}/{report['max_score']}",
            "warnings": len(report["warnings"]),
            "inspiration_sources": len(inspirations.get("sources", [])),
        })
    if args.format == "json":
        print(json.dumps(items, indent=2))
        return
    print(f"{'':<2} {'BRAND':<20} {'PROFILE':<8} {'IDENTITY':<9} {'VALID':<8} {'WARN':<5} {'INSP'}")
    print("-" * 80)
    for item in items:
        marker = "*" if item["active"] else " "
        print(f"{marker:<2} {item['key']:<20} {str(item['profile']):<8} {str(item['identity']):<9} {item['score']:<8} {item['warnings']:<5} {item['inspiration_sources']}")


def cmd_extract_inspiration(args):
    brand_gen_dir = get_brand_gen_dir()
    if not brand_gen_dir:
        raise SystemExit("No .brand-gen directory found. Run: brand_iterate.py init")
    cmd = [
        "--brand-gen-dir", str(brand_gen_dir),
        "--workers", str(args.workers),
        "--timeout", str(args.timeout),
    ]
    if args.category:
        cmd += ["--category", args.category]
    if args.limit:
        cmd += ["--limit", str(args.limit)]
    if args.force:
        cmd += ["--force"]
    for source in args.source or []:
        cmd += ["--source", source]
    run_child_script(REPO_ROOT / "scripts" / "batch_extract_inspiration.py", cmd)


def cmd_inspiration_mode(args):
    brand_gen_dir = get_brand_gen_dir() or (REPO_ROOT / ".brand-gen")
    config = load_brand_gen_config(brand_gen_dir)
    if args.state:
        state = args.state.lower()
        if state not in {"on", "off"}:
            raise SystemExit("State must be 'on' or 'off'.")
        config["inspirationMode"] = state == "on"
        save_brand_gen_config(config, brand_gen_dir)
    print(f"inspirationMode: {'on' if config.get('inspirationMode') else 'off'}")


def cmd_configure_inspiration(args):
    brand_gen_dir = get_brand_gen_dir()
    if not brand_gen_dir:
        raise SystemExit("No .brand-gen directory found. Run: brand_iterate.py init")
    brand = args.brand or args.category or resolve_active_brand_key(brand_gen_dir)
    if not brand:
        raise SystemExit("No brand specified and no active brand set.")
    brand_dir = brand_gen_dir / "brands" / brand
    if not brand_dir.exists():
        raise SystemExit(f"Brand '{brand}' not found under {brand_gen_dir / 'brands'}")

    index = load_inspiration_index(brand_gen_dir).get("sources", {})
    config = load_inspirations_config(brand, brand_gen_dir)

    if args.clear:
        config["sources"] = []
        save_inspirations_config(config, brand, brand_gen_dir)
        print(f"Cleared inspiration sources for {brand}")
        return

    if args.sources:
        sources = [item.strip() for chunk in args.sources for item in chunk.split(",") if item.strip()]
        warnings = []
        for source in sources:
            if source not in index:
                warnings.append(f"{source}: not indexed")
            elif index[source].get("status") != "complete":
                warnings.append(f"{source}: status={index[source].get('status') or 'unknown'}")
        config["sources"] = sources
        save_inspirations_config(config, brand, brand_gen_dir)
        print(f"Inspiration sources for {brand}: {', '.join(sources) or 'none'}")
        if warnings:
            warn("; ".join(warnings))
        return

    show_payload = {
        "brand": brand,
        "config": config,
        "available_indexed_sources": sorted(index.keys()),
    }
    if args.format == "json":
        print(json.dumps(show_payload, indent=2))
    else:
        print(f"Brand: {brand}")
        print(f"Sources: {', '.join(config.get('sources', [])) or 'none'}")
        print(f"Mode: {config.get('mode', 'principles')}")


def cmd_shotlist(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    output = Path(args.output).expanduser() if args.output else brand_dir / "PRODUCT-SHOTLIST.md"
    cmd = ["plan", "--output", str(output.resolve())]
    if args.product_name:
        cmd += ["--product-name", args.product_name]
    if args.goal:
        cmd += ["--goal", args.goal]
    run_child_script(PRODUCT_SCREENS_PY, cmd)


def cmd_capture_product(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    out_dir = Path(args.out_dir).expanduser() if args.out_dir else brand_dir / "product-screens"
    cmd = ["capture", "--out-dir", str(out_dir.resolve()), "--count", str(args.count), "--scroll-px", str(args.scroll_px)]
    if args.url:
        cmd += ["--url", args.url]
    if args.label:
        cmd += ["--label", args.label]
    for shot in args.shot or []:
        cmd += ["--shot", shot]
    if args.session:
        cmd += ["--session", args.session]
    if args.open_folder:
        cmd.append("--open-folder")
    run_child_script(PRODUCT_SCREENS_PY, cmd)


def cmd_explore_brand(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    output = Path(args.output).expanduser() if args.output else brand_dir / "brand-concept-directions.md"
    output_json = Path(args.output_json).expanduser() if args.output_json else brand_dir / "brand-concept-directions.json"
    cmd = ["--output", str(output.resolve()), "--output-json", str(output_json.resolve()), "--top", str(args.top)]
    if args.profile:
        cmd += ["--profile", str(Path(args.profile).expanduser().resolve())]
    if args.brand_name:
        cmd += ["--brand-name", args.brand_name]
    if args.business:
        cmd += ["--business", args.business]
    if args.audience:
        cmd += ["--audience", args.audience]
    if args.tone:
        cmd += ["--tone", args.tone]
    if args.avoid:
        cmd += ["--avoid", args.avoid]
    if args.product_context:
        cmd += ["--product-context", args.product_context]
    for material in args.material or []:
        cmd += ["--material", material]
    for source in args.source or []:
        cmd += ["--source", source]
    run_child_script(EXPLORE_BRAND_PY, cmd)



def cmd_review_brand(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    reviews_dir = brand_dir / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    output = Path(args.output).expanduser() if args.output else reviews_dir / f"{args.version or 'latest'}-review.md"
    cmd = ["--brand-dir", str(brand_dir.resolve()), "--output", str(output.resolve())]
    if args.version:
        cmd += ["--version", args.version]
    run_child_script(BUILD_REVIEW_PACKET_PY, cmd)
    if sys.platform == "darwin" and args.open:
        subprocess.run(["open", str(output)], check=False)


def cmd_example_sources(args):
    cmd = ["list"]
    if args.category:
        cmd += ["--category", args.category]
    if args.query:
        cmd += ["--query", args.query]
    if args.format:
        cmd += ["--format", args.format]
    run_child_script(BRAND_EXAMPLES_PY, cmd)


def cmd_collect_examples(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    out_dir = Path(args.out_dir).expanduser() if args.out_dir else brand_dir / "examples"
    cmd = ["capture", "--out-dir", str(out_dir.resolve()), "--width", str(args.width), "--height", str(args.height)]
    if args.category:
        cmd += ["--category", args.category]
    if args.query:
        cmd += ["--query", args.query]
    if args.limit:
        cmd += ["--limit", str(args.limit)]
    for site in args.site or []:
        cmd += ["--site", site]
    if args.open_folder:
        cmd.append("--open-folder")
    run_child_script(BRAND_EXAMPLES_PY, cmd)


def cmd_social_specs(args):
    key = (args.format or "").strip().lower()
    items = SOCIAL_SPECS.items()
    if key:
        if key not in SOCIAL_SPECS:
            available = ", ".join(sorted(SOCIAL_SPECS))
            print(f"Unknown format '{args.format}'. Available: {available}", file=sys.stderr)
            sys.exit(1)
        items = [(key, SOCIAL_SPECS[key])]
    print(f"{'FORMAT':<24} {'SIZE':<14} {'ASPECT':<10} {'LABEL'}")
    print("-" * 120)
    for name, spec in items:
        size = f"{spec['width']}x{spec['height']}"
        print(f"{name:<24} {size:<14} {spec['aspect_ratio']:<10} {spec['label']}")
        if args.verbose:
            print(f"  notes: {spec['notes']}")
            print(f"  source: {spec['source']}")
            print()


def list_material_types():
    print("Available material types:\n")
    for key, config in sorted(MATERIAL_CONFIG.items()):
        ratio = config.get("default_aspect_ratio", "—")
        print(f"  {key:<20} {config['generation_mode']:<6} default model: {config['default_model']:<12} default AR: {ratio}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Brand iteration wrapper for image and motion materials", formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("bootstrap", help="Scan existing files into manifest")
    sub.add_parser("types", help="List supported material types")

    init = sub.add_parser("init", help="Initialize .brand-gen structure and optionally migrate a legacy brand-materials workspace")
    init.add_argument("--brand-name", help="Brand key to initialize / activate")
    init.add_argument("--brand-gen-dir", help="Override .brand-gen location")
    init.add_argument("--legacy-brand-dir", help="Optional legacy brand-materials directory to migrate")

    start_testing = sub.add_parser("start-testing", help="Start an explicit brand testing session instead of defaulting to a saved brand")
    start_testing.add_argument("--session-name", help="Session key; defaults to a slug from the working name or timestamp")
    start_testing.add_argument("--working-name", help="Temporary working brand name for this session")
    start_testing.add_argument("--brand", help="Optional saved brand to seed the session from")
    start_testing.add_argument("--goal", help="What this test session is trying to learn or generate")
    start_testing.add_argument("--brand-gen-dir", help="Override .brand-gen location")

    use = sub.add_parser("use", help="Switch the active brand in .brand-gen/config.json")
    use.add_argument("brand", nargs="?", help="Brand key to activate")
    use.add_argument("--list", dest="list_only", action="store_true", help="List available brands instead")

    list_brands = sub.add_parser("list-brands", help="List available brands under .brand-gen/brands")
    list_brands.add_argument("--format", choices=["text", "json"], default="text")

    extract = sub.add_parser("extract-brand", help="Extract a structured brand profile from a local project")
    extract.add_argument("--project-root", default=".", help="Codebase or docs root to inspect")
    extract.add_argument("--brand-name", help="Optional explicit brand name")
    extract.add_argument("--homepage-url", help="Optional homepage URL to record")
    extract.add_argument("--notes-file", help="Optional text file with extra notes")
    extract.add_argument("--reference-dir", help="Optional reference asset directory to include as brand anchors")
    extract.add_argument("--design-tokens-json", help="Optional dembrandt-style design tokens JSON to merge into the profile")
    extract.add_argument("--design-memory-path", help="Optional .design-memory folder or project root containing one; defaults to <project-root>/.design-memory when present")
    extract.add_argument("--output-json", help="Optional output path for the JSON profile")
    extract.add_argument("--output-markdown", help="Optional output path for the Markdown profile")
    extract.add_argument("--output-identity-json", help="Optional output path for brand-identity.json")
    extract.add_argument("--output-identity-markdown", help="Optional output path for brand-identity.md")

    build_identity = sub.add_parser("build-identity", help="Build brand identity memory files from a saved profile")
    build_identity.add_argument("--profile", help="Path to brand-profile.json")
    build_identity.add_argument("--output-json", help="Output path for brand-identity.json")
    build_identity.add_argument("--output-markdown", help="Output path for brand-identity.md")

    describe = sub.add_parser("describe-brand", help="Generate brand description and prompt blocks from a saved profile")
    describe.add_argument("--profile", help="Path to brand-profile.json")
    describe.add_argument("--identity", help="Optional path to brand-identity.json")
    describe.add_argument("--output", help="Output path for the Markdown prompt file")

    show_identity = sub.add_parser("show-identity", help="Show a readable or JSON summary of stored brand identity")
    show_identity.add_argument("--profile", help="Optional path to brand-profile.json")
    show_identity.add_argument("--identity", help="Optional path to brand-identity.json")
    show_identity.add_argument("--format", choices=["text", "json"], default="text")
    show_identity.add_argument("--show-prelude", action="store_true", help="Include the full brand guardrail prompt prelude")

    show_blackboard = sub.add_parser("show-blackboard", help="Show the shared brand blackboard / specialist state")
    show_blackboard.add_argument("--profile", help="Optional path to brand-profile.json")
    show_blackboard.add_argument("--identity", help="Optional path to brand-identity.json")
    show_blackboard.add_argument("--format", choices=["text", "json"], default="text")

    show_session_summary = sub.add_parser("show-session-summary", help="Show one current-workspace summary: generated versions, feedback, iteration notes, messaging, and latest artifacts")
    show_session_summary.add_argument("--profile", help="Optional path to brand-profile.json")
    show_session_summary.add_argument("--identity", help="Optional path to brand-identity.json")
    show_session_summary.add_argument("--limit", type=int, default=5, help="How many recent versions/notes to show")
    show_session_summary.add_argument("--format", choices=["text", "json"], default="text")

    show_workflow_lineage = sub.add_parser("show-workflow-lineage", help="Show blackboard lineage and saved artifact paths for a workflow_id")
    show_workflow_lineage.add_argument("--workflow-id", required=True, help="Workflow id to inspect")
    show_workflow_lineage.add_argument("--format", choices=["text", "json"], default="text")

    show_reference_analysis = sub.add_parser("show-reference-analysis", help="Show cached reference-analysis results for the current workspace")
    show_reference_analysis.add_argument("--profile", help="Optional path to brand-profile.json")
    show_reference_analysis.add_argument("--identity", help="Optional path to brand-identity.json")
    show_reference_analysis.add_argument("--refresh-reference-analysis", action="store_true", help="Recompute cached reference analysis before showing it")
    show_reference_analysis.add_argument("--format", choices=["text", "json"], default="text")

    route_request = sub.add_parser("route-request", help="Route a request to the right specialist path before planning or generation")
    route_request.add_argument("--material-type", help="Target material type if known")
    route_request.add_argument("--goal", help="What this artifact or set should accomplish")
    route_request.add_argument("--request", help="Freeform request text or brief")
    route_request.add_argument("--motion-reference", help="Optional motion reference path to bias routing toward motion")
    route_request.add_argument("--set-scope", action="store_true", help="Treat this as a multi-material set request")
    route_request.add_argument("--profile", help="Optional path to brand-profile.json")
    route_request.add_argument("--identity", help="Optional path to brand-identity.json")
    route_request.add_argument("--format", choices=["text", "json"], default="text")

    resolve_prompt = sub.add_parser("resolve-prompt", help="Show the effective prompt after applying brand guardrails")
    resolve_prompt.add_argument("-p", "--prompt", help="Base prompt body")
    resolve_prompt.add_argument("--plan", help="Optional material plan JSON generated by plan-material")
    resolve_prompt.add_argument("--profile", help="Optional path to brand-profile.json")
    resolve_prompt.add_argument("--identity", help="Optional path to brand-identity.json")
    resolve_prompt.add_argument("--material-type", help="Optional material type to tailor inspiration doctrine loading")
    resolve_prompt.add_argument("--mode", choices=["auto", "reference", "inspiration", "hybrid"], default="auto", help="Optional workflow mode to inspect material-specific snippet variants")
    resolve_prompt.add_argument("--disable-brand-guardrails", action="store_true", help="Skip automatic brand guardrail prelude injection")
    resolve_prompt.add_argument("--refresh-reference-analysis", action="store_true", help="Recompute cached reference analysis before resolving the prompt")
    resolve_prompt.add_argument("--format", choices=["text", "json"], default="text")

    review_prompt = sub.add_parser("review-prompt", help="Review and refine a resolved prompt before generation")
    review_prompt.add_argument("-p", "--prompt", help="Base prompt body")
    review_prompt.add_argument("--plan", help="Optional material plan JSON generated by plan-material")
    review_prompt.add_argument("--profile", help="Optional path to brand-profile.json")
    review_prompt.add_argument("--identity", help="Optional path to brand-identity.json")
    review_prompt.add_argument("--material-type", help="Optional material type to tailor prompt review")
    review_prompt.add_argument("--mode", choices=["auto", "reference", "inspiration", "hybrid"], default="auto", help="Optional workflow mode to inspect material-specific snippet variants")
    review_prompt.add_argument("--disable-brand-guardrails", action="store_true", help="Skip automatic brand guardrail prelude injection")
    review_prompt.add_argument("--refresh-reference-analysis", action="store_true", help="Recompute cached reference analysis before reviewing the prompt")
    review_prompt.add_argument("--format", choices=["text", "json"], default="text")

    validate_identity = sub.add_parser("validate-identity", help="Validate whether stored brand memory is complete enough for generation")
    validate_identity.add_argument("--profile", help="Optional path to brand-profile.json")
    validate_identity.add_argument("--identity", help="Optional path to brand-identity.json")
    validate_identity.add_argument("--format", choices=["text", "json"], default="text")
    validate_identity.add_argument("--strict", action="store_true", help="Exit non-zero if errors or warnings are present")

    parse_design_memory = sub.add_parser("parse-design-memory", help="Parse an existing .design-memory folder into a compact structured summary")
    parse_design_memory.add_argument("--path", required=True, help="Path to a .design-memory folder, file inside it, or project root containing one")
    parse_design_memory.add_argument("--format", choices=["text", "json"], default="text")
    parse_design_memory.add_argument("--output-json", help="Optional output path for the parsed design-memory summary")

    extract_css_variables = sub.add_parser("extract-css-variables", help="Extract CSS custom properties from .design-memory, CSS, HTML, or markdown files")
    extract_css_variables.add_argument("--path", required=True, help="Path to a .design-memory folder, local file, or project root")
    extract_css_variables.add_argument("--format", choices=["text", "json"], default="text")
    extract_css_variables.add_argument("--output-json", help="Optional output path for the extracted CSS variables")
    extract_css_variables.add_argument("--max-files", type=int, default=250, help="Maximum number of files to scan when the input is a directory")

    diff_design_memory = sub.add_parser("diff-design-memory", help="Compare two .design-memory folders to inspect token and doctrine drift")
    diff_design_memory.add_argument("--before", required=True, help="Earlier .design-memory folder or project root containing one")
    diff_design_memory.add_argument("--after", required=True, help="Later .design-memory folder or project root containing one")
    diff_design_memory.add_argument("--format", choices=["text", "json"], default="text")
    diff_design_memory.add_argument("--output-json", help="Optional output path for the diff report")

    extract_inspiration = sub.add_parser("extract-inspiration", help="Run batch design-memory extraction for curated inspiration sources")
    extract_inspiration.add_argument("--category", help="Filter by category key")
    extract_inspiration.add_argument("--source", action="append", help="Specific inspiration source key; repeat as needed")
    extract_inspiration.add_argument("--workers", type=int, default=4)
    extract_inspiration.add_argument("--force", action="store_true")
    extract_inspiration.add_argument("--limit", type=int)
    extract_inspiration.add_argument("--timeout", type=int, default=120)

    inspiration_mode = sub.add_parser("inspiration-mode", help="Toggle whether inspiration tokens are injected in addition to principles")
    inspiration_mode.add_argument("state", nargs="?", help="on|off")

    shotlist = sub.add_parser("shotlist", help="Create a product screenshot shotlist markdown file")
    shotlist.add_argument("--product-name", help="Product name to use in the shotlist")
    shotlist.add_argument("--goal", help="Optional marketing goal for the shotlist")
    shotlist.add_argument("--output", help="Output path for the shotlist markdown")

    capture = sub.add_parser("capture-product", help="Capture product screenshots with agent-browser")
    capture.add_argument("--url", help="Single URL to capture")
    capture.add_argument("--label", help="Label for --url captures")
    capture.add_argument("--shot", action="append", help="Repeatable label=url pair for multiple captures")
    capture.add_argument("--out-dir", help="Output directory for screenshots")
    capture.add_argument("--count", type=int, default=1, help="How many scroll positions to capture per shot")
    capture.add_argument("--scroll-px", type=int, default=1400)
    capture.add_argument("--session", help="Explicit agent-browser session id")
    capture.add_argument("--open-folder", action="store_true")

    explore = sub.add_parser("explore-brand", help="Suggest exploratory concept directions, source packs, and prompt seeds")
    explore.add_argument("--profile", help="Optional brand-profile.json path")
    explore.add_argument("--brand-name", help="Explicit brand name")
    explore.add_argument("--business", help="Business or product summary")
    explore.add_argument("--audience", help="Target audience summary")
    explore.add_argument("--tone", help="Comma-separated tone words")
    explore.add_argument("--avoid", help="Comma-separated anti-patterns or avoid words")
    explore.add_argument("--product-context", help="Which product surfaces matter and what product truth should anchor the work")
    explore.add_argument("--material", action="append", help="Target material type; repeat as needed")
    explore.add_argument("--source", action="append", help="Preferred curated source key to constrain suggested example sources; repeat as needed")
    explore.add_argument("--top", type=int, default=4, help="How many directions to include")
    explore.add_argument("--output", help="Markdown output path")
    explore.add_argument("--output-json", help="JSON output path")

    plan_set = sub.add_parser("plan-set", help="Establish a coherent material set from translated inspiration and brand truth")
    plan_set.add_argument("--template", default="product-core", help="Template key (product-core, launch-core, brand-system-core, social-launch)")
    plan_set.add_argument("--set-name", help="Optional explicit set slug/name")
    plan_set.add_argument("--goal", help="What this set should accomplish")
    plan_set.add_argument("--surface", help="Primary use surface or campaign context")
    plan_set.add_argument("--mode", choices=["reference", "inspiration", "hybrid"], default="hybrid")
    plan_set.add_argument("--profile", help="Optional path to brand-profile.json")
    plan_set.add_argument("--identity", help="Optional path to brand-identity.json")
    plan_set.add_argument("--output", help="Output path for the set JSON manifest")
    plan_set.add_argument("--format", choices=["text", "json"], default="text")

    validate_brand_fit = sub.add_parser("validate-brand-fit", help="Validate that a material plan or set stays clearly branded and product-fit")
    validate_brand_fit.add_argument("--plan", help="Path to a material plan JSON")
    validate_brand_fit.add_argument("--set", help="Path to a set manifest JSON")
    validate_brand_fit.add_argument("--format", choices=["text", "json"], default="text")
    validate_brand_fit.add_argument("--strict", action="store_true")

    validate_set = sub.add_parser("validate-set", help="Validate set-level coherence, product-fit, and brand-anchor coverage")
    validate_set.add_argument("--set", required=True, help="Path to a set manifest JSON")
    validate_set.add_argument("--format", choices=["text", "json"], default="text")
    validate_set.add_argument("--strict", action="store_true")

    generate_set = sub.add_parser("generate-set", help="Generate the explicit generateable members of a saved set manifest")
    generate_set.add_argument("--set", required=True, help="Path to a set manifest JSON")
    generate_set.add_argument("--only", action="append", help="Only generate these material types; repeat as needed")
    generate_set.add_argument("--skip", action="append", help="Skip these material types; repeat as needed")
    generate_set.add_argument("--model", help="Optional model override passed through to generate")
    generate_set.add_argument("--aspect-ratio", help="Optional aspect ratio override passed through to generate")
    generate_set.add_argument("--parallel", action="store_true", help="Generate independent materials in parallel using a thread pool")
    generate_set.add_argument("--workers", type=int, default=3, help="Max parallel workers when --parallel is set (default: 3, max: 5)")

    review = sub.add_parser("review-brand", help="Build a structured critique/refine packet for a generated or composed artifact")
    review.add_argument("version", nargs="?", help="Version to review; defaults to latest")
    review.add_argument("--output", help="Optional output path for the review markdown")
    review.add_argument("--open", action="store_true", help="Open the review markdown after writing it")

    suggest_role_pack = sub.add_parser("suggest-role-pack", help="Inspect candidate reference-role selections before generation")
    suggest_role_pack.add_argument("--material-type", required=True, help="Material type to inspect (e.g. pattern-system, sticker-family, campaign-poster)")
    suggest_role_pack.add_argument("--format", choices=["text", "json"], default="text")
    suggest_role_pack.add_argument("--top", type=int, default=3, help="How many suggestions to show per role")

    plan_material = sub.add_parser("plan-material", help="Write an explicit material plan so the agent can reason before generating")
    plan_material.add_argument("--material-type", required=True, help="Material type to plan")
    plan_material.add_argument("--mode", choices=["reference", "inspiration", "hybrid"], default="hybrid", help="Workflow mode for the plan")
    plan_material.add_argument("--mechanic", help="The one system mechanic or reveal move to emphasize")
    plan_material.add_argument("--purpose", help="What job this material should do")
    plan_material.add_argument("--target-surface", help="Where this material will be used")
    plan_material.add_argument("--product-truth-expression", help="What concrete product truth this material must express")
    plan_material.add_argument("--abstraction-level", choices=["low", "medium", "high"], help="How abstract this material is allowed to be")
    plan_material.add_argument("--preserve", action="append", help="Thing that must stay fixed; repeat as needed")
    plan_material.add_argument("--push", action="append", help="Thing that can be pushed or explored; repeat as needed")
    plan_material.add_argument("--ban", action="append", help="Thing that must not appear; repeat as needed")
    plan_material.add_argument("--pick", action="append", help="Explicit role pick in the form role=source-key-or-path; repeat as needed")
    plan_material.add_argument("--prompt-seed", help="Optional explicit prompt seed; otherwise one is generated")
    plan_material.add_argument("--profile", help="Optional brand-profile.json path")
    plan_material.add_argument("--identity", help="Optional brand-identity.json path")
    plan_material.add_argument("--output", help="Optional output path for the plan JSON")
    plan_material.add_argument("--format", choices=["text", "json"], default="text")

    plan_draft = sub.add_parser("plan-draft", help="Write a plan draft scratchpad that the critic can inspect before generation")
    plan_draft.add_argument("--material-type", required=True, help="Material type to plan")
    plan_draft.add_argument("--mode", choices=["reference", "inspiration", "hybrid"], default="hybrid", help="Workflow mode for the draft")
    plan_draft.add_argument("--mechanic", help="The one system mechanic or reveal move to emphasize")
    plan_draft.add_argument("--purpose", help="What job this material should do")
    plan_draft.add_argument("--target-surface", help="Where this material will be used")
    plan_draft.add_argument("--product-truth-expression", help="What concrete product truth this material must express")
    plan_draft.add_argument("--abstraction-level", choices=["low", "medium", "high"], help="How abstract this material is allowed to be")
    plan_draft.add_argument("--preserve", action="append", help="Thing that must stay fixed; repeat as needed")
    plan_draft.add_argument("--push", action="append", help="Thing that can be pushed or explored; repeat as needed")
    plan_draft.add_argument("--ban", action="append", help="Thing that must not appear; repeat as needed")
    plan_draft.add_argument("--pick", action="append", help="Explicit role pick in the form role=source-key-or-path; repeat as needed")
    plan_draft.add_argument("--prompt-seed", help="Optional explicit prompt seed; otherwise one is generated")
    plan_draft.add_argument("--profile", help="Optional brand-profile.json path")
    plan_draft.add_argument("--identity", help="Optional brand-identity.json path")
    plan_draft.add_argument("--output", help="Optional output path for the plan draft JSON")
    plan_draft.add_argument("--format", choices=["text", "json"], default="text")

    critique_plan = sub.add_parser("critique-plan", help="Critique a plan or plan draft before building a generation scratchpad")
    critique_plan.add_argument("--plan", required=True, help="Path to a material plan JSON or plan-draft JSON")
    critique_plan.add_argument("-p", "--prompt", help="Optional prompt override for the critique pass")
    critique_plan.add_argument("--material-type", help="Optional material type override")
    critique_plan.add_argument("--generation-mode", choices=["auto", "image", "video"], default="auto")
    critique_plan.add_argument("--mode", choices=["auto", "reference", "inspiration", "hybrid"], default="auto")
    critique_plan.add_argument("-m", "--model", help="Optional model override")
    critique_plan.add_argument("--aspect-ratio", "-ar")
    critique_plan.add_argument("--resolution")
    critique_plan.add_argument("--duration", "-d", type=int)
    critique_plan.add_argument("--tag", "-t")
    critique_plan.add_argument("-i", "--image", action="append")
    critique_plan.add_argument("--reference-dir")
    critique_plan.add_argument("--motion-reference")
    critique_plan.add_argument("--motion-mode", choices=["std", "pro"])
    critique_plan.add_argument("--character-orientation", choices=["image", "video"])
    critique_plan.add_argument("--keep-original-sound", action="store_true")
    critique_plan.add_argument("--preset")
    critique_plan.add_argument("--negative-prompt", "-n")
    critique_plan.add_argument("--style")
    critique_plan.add_argument("--make-gif", action="store_true")
    critique_plan.add_argument("--profile")
    critique_plan.add_argument("--identity")
    critique_plan.add_argument("--disable-brand-guardrails", action="store_true")
    critique_plan.add_argument("--output", help="Optional output path for the plan critique JSON")
    critique_plan.add_argument("--format", choices=["text", "json"], default="text")

    build_scratch = sub.add_parser("build-generation-scratchpad", help="Build the execution scratchpad that generate now requires")
    build_scratch.add_argument("-p", "--prompt", help="Generation prompt override")
    build_scratch.add_argument("--plan", required=True, help="Material plan JSON or plan-draft JSON")
    build_scratch.add_argument("--material-type", help="Material type override")
    build_scratch.add_argument("--generation-mode", choices=["auto", "image", "video"], default="auto")
    build_scratch.add_argument("--mode", choices=["auto", "reference", "inspiration", "hybrid"], default="auto")
    build_scratch.add_argument("-m", "--model")
    build_scratch.add_argument("--aspect-ratio", "-ar")
    build_scratch.add_argument("--resolution")
    build_scratch.add_argument("--duration", "-d", type=int)
    build_scratch.add_argument("--tag", "-t")
    build_scratch.add_argument("-i", "--image", action="append")
    build_scratch.add_argument("--reference-dir")
    build_scratch.add_argument("--motion-reference")
    build_scratch.add_argument("--motion-mode", choices=["std", "pro"])
    build_scratch.add_argument("--character-orientation", choices=["image", "video"])
    build_scratch.add_argument("--keep-original-sound", action="store_true")
    build_scratch.add_argument("--preset")
    build_scratch.add_argument("--negative-prompt", "-n")
    build_scratch.add_argument("--style")
    build_scratch.add_argument("--make-gif", action="store_true")
    build_scratch.add_argument("--profile")
    build_scratch.add_argument("--identity")
    build_scratch.add_argument("--disable-brand-guardrails", action="store_true")
    build_scratch.add_argument("--skip-extraction", action="store_true", help="Skip cached reference analysis during scratchpad assembly")
    build_scratch.add_argument("--refresh-reference-analysis", action="store_true", help="Recompute cached reference analysis even if a cache entry exists")
    build_scratch.add_argument("--allow-blocking", action="store_true", help="Write the scratchpad even if blocking issues remain")
    build_scratch.add_argument("--output", help="Optional output path for the generation scratchpad JSON")
    build_scratch.add_argument("--format", choices=["text", "json"], default="text")

    ideate_material = sub.add_parser("ideate-material", help="Generate idea tracks and alignment questions for an evolving brand material")
    ideate_material.add_argument("--material-type", required=True, help="Material type to ideate")
    ideate_material.add_argument("--mode", choices=["reference", "inspiration", "hybrid"], default="hybrid")
    ideate_material.add_argument("--goal", help="Optional goal for this material")
    ideate_material.add_argument("--use-surface", help="Where this material will appear first")
    ideate_material.add_argument("--concern", help="Main concern or tension to resolve")
    ideate_material.add_argument("--profile", help="Optional brand-profile.json path")
    ideate_material.add_argument("--identity", help="Optional brand-identity.json path")
    ideate_material.add_argument("--format", choices=["text", "json"], default="text")

    ideate_copy = sub.add_parser("ideate-copy", help="Generate headline, slogan, and CTA candidates for branded materials")
    ideate_copy.add_argument("--material-type", required=True, help="Material type to ideate copy for")
    ideate_copy.add_argument("--goal", help="What this material should accomplish")
    ideate_copy.add_argument("--surface", help="Primary surface, channel, or placement")
    ideate_copy.add_argument("--profile", help="Optional brand-profile.json path")
    ideate_copy.add_argument("--identity", help="Optional brand-identity.json path")
    ideate_copy.add_argument("--format", choices=["text", "json"], default="text")

    ideate_messaging = sub.add_parser("ideate-messaging", help="Assemble brand context for messaging ideation — the calling agent generates positioning angles from the returned context")
    ideate_messaging.add_argument("--profile", help="Optional brand-profile.json path")
    ideate_messaging.add_argument("--identity", help="Optional brand-identity.json path")
    ideate_messaging.add_argument("--format", choices=["text", "json"], default="text")

    promote_messaging = sub.add_parser("promote-messaging", help="Promote session messaging into the saved brand identity for cross-session persistence")
    promote_messaging.add_argument("--include-copy-notes", action="store_true", help="Also promote iteration messaging/copy notes as messaging insights")
    promote_messaging.add_argument("--profile", help="Optional brand-profile.json path")
    promote_messaging.add_argument("--identity", help="Optional brand-identity.json path")

    update_messaging = sub.add_parser("update-messaging", help="Update brand messaging (tagline, elevator, voice, copy bank) in the brand identity")
    update_messaging.add_argument("--tagline", help="Set the brand tagline")
    update_messaging.add_argument("--elevator", help="Set the elevator pitch (1-2 sentences)")
    update_messaging.add_argument("--voice-description", help="Set the brand voice description")
    update_messaging.add_argument("--add-value-prop", action="append", help="Add an approved value proposition; repeat for multiple")
    update_messaging.add_argument("--add-headline", action="append", help="Add an approved headline to the copy bank; repeat for multiple")
    update_messaging.add_argument("--add-slogan", action="append", help="Add an approved slogan; repeat for multiple")
    update_messaging.add_argument("--add-subheadline", action="append", help="Add an approved subheadline; repeat for multiple")
    update_messaging.add_argument("--profile", help="Optional brand-profile.json path")
    update_messaging.add_argument("--identity", help="Optional brand-identity.json path")
    update_messaging.add_argument("--format", choices=["text", "json"], default="text")

    show_iteration_memory = sub.add_parser("show-iteration-memory", help="Show the evolving scratchpad of negative examples, messaging/copy notes, and wins")
    show_iteration_memory.add_argument("--format", choices=["text", "json"], default="text")

    update_iteration_memory = sub.add_parser("update-iteration-memory", help="Record positive/negative examples or explicit brand/messaging/copy/material notes")
    update_iteration_memory.add_argument("--version", help="Optional version id related to the note")
    update_iteration_memory.add_argument("--material-type", help="Optional material type for material-specific notes")
    update_iteration_memory.add_argument("--kind", choices=["brand", "copy", "messaging", "material"], default="brand")
    update_iteration_memory.add_argument("--note", help="General note to add")
    update_iteration_memory.add_argument("--negative", help="Add a negative example summary")
    update_iteration_memory.add_argument("--positive", help="Add a positive example summary")
    update_iteration_memory.add_argument("--score", type=int)
    update_iteration_memory.add_argument("--format", choices=["text", "json"], default="text")

    examples = sub.add_parser("example-sources", help="List or search curated brand example sources")
    examples.add_argument("--category", help="Category key filter (e.g. saas-product-specialists)")
    examples.add_argument("--query", help="Search query across source names, notes, and tags")
    examples.add_argument("--format", choices=["table", "json"], default="table")

    collect_examples = sub.add_parser("collect-examples", help="Capture curated brand example references into categorized folders")
    collect_examples.add_argument("--category", help="Category key filter (e.g. premium-branding)")
    collect_examples.add_argument("--query", help="Search query across source names, notes, and tags")
    collect_examples.add_argument("--site", action="append", help="Specific source key to capture; repeat as needed")
    collect_examples.add_argument("--limit", type=int, help="Limit number of captures after filtering")
    collect_examples.add_argument("--out-dir", help="Output directory for example captures")
    collect_examples.add_argument("--width", type=int, default=1600)
    collect_examples.add_argument("--height", type=int, default=1100)
    collect_examples.add_argument("--open-folder", action="store_true")

    specs = sub.add_parser("social-specs", help="Show recommended X / LinkedIn / OG card and feed dimensions")
    specs.add_argument("format", nargs="?", help="Optional single format filter (x-card, x-feed, x-feed-square, x-feed-portrait, linkedin-card, linkedin-feed, linkedin-feed-square, linkedin-feed-portrait, og-card)")
    specs.add_argument("--verbose", action="store_true", help="Include notes and source hints")

    gen = sub.add_parser("generate", aliases=["gen", "g"], help="Generate a new brand material version from a generation scratchpad")
    gen.add_argument("--scratchpad", required=True, help="Path to a generation scratchpad JSON created by build-generation-scratchpad")
    gen.add_argument("--max-iterations", type=int, default=1, help="Max generate→VLM-critique→refine loops (1-3, default: 1 = single-shot)")
    gen.add_argument("--skip-vlm", action="store_true", help="Skip VLM image critique even when max-iterations > 1")

    pipeline = sub.add_parser("pipeline", help="Run the generative pipeline in-process: route → plan-draft → critique → scratchpad → generate")
    pipeline.add_argument("--material-type", required=True, help="Material type to generate")
    pipeline.add_argument("--mode", choices=["reference", "inspiration", "hybrid"], default="hybrid", help="Workflow mode for the plan")
    pipeline.add_argument("--mechanic", help="The one system mechanic or reveal move to emphasize")
    pipeline.add_argument("--purpose", help="What job this material should do")
    pipeline.add_argument("--target-surface", help="Where this material will be used")
    pipeline.add_argument("--product-truth-expression", help="What concrete product truth this material must express")
    pipeline.add_argument("--abstraction-level", choices=["low", "medium", "high"], help="How abstract this material is allowed to be")
    pipeline.add_argument("--preserve", action="append", help="Thing that must stay fixed; repeat as needed")
    pipeline.add_argument("--push", action="append", help="Thing that can be pushed or explored; repeat as needed")
    pipeline.add_argument("--ban", action="append", help="Thing that must not appear; repeat as needed")
    pipeline.add_argument("--pick", action="append", help="Explicit role pick in the form role=source-key-or-path; repeat as needed")
    pipeline.add_argument("--prompt-seed", help="Optional explicit prompt seed; otherwise one is generated")
    pipeline.add_argument("--goal", help="Optional top-level goal used for routing context")
    pipeline.add_argument("--request", help="Optional request text used for routing context")
    pipeline.add_argument("--motion-reference", help="Optional motion reference path for routing or video generation")
    pipeline.add_argument("--set-scope", action="store_true", help="Route as a set orchestration brief, even though generation remains single-material")
    pipeline.add_argument("--max-iterations", type=int, default=1, help="Max generate→VLM-critique→refine loops (1-3)")
    pipeline.add_argument("--skip-vlm", action="store_true", help="Skip VLM image critique loop")
    pipeline.add_argument("--skip-route", action="store_true", help="Skip the routing stage and start at plan-draft")
    pipeline.add_argument("--profile", help="Optional brand-profile.json path")
    pipeline.add_argument("--identity", help="Optional brand-identity.json path")
    pipeline.add_argument("--format", choices=["text", "json"], default="json")

    fb = sub.add_parser("feedback", aliases=["fb", "f"], help="Record feedback")
    fb.add_argument("version", help="Version ID (e.g., v12)")
    fb.add_argument("--score", "-s", type=int, choices=range(1, 6), help="Score 1-5")
    fb.add_argument("--notes", "-n", help="Feedback notes")
    fb.add_argument("--status", choices=["favorite", "rejected"], help="Mark status")
    fb.add_argument("--lock", nargs="+", help="Lock prompt fragments")
    fb.add_argument("--prompt", "-p", help="Backfill prompt text")

    sh = sub.add_parser("show", aliases=["s"], help="Show manifest")
    sh.add_argument("version", nargs="?", help="Specific version to show")
    sh.add_argument("--favorites", action="store_true", help="Only favorites")
    sh.add_argument("--top", type=int, help="Top N by score")
    sh.add_argument("--latest", type=int, help="Latest N versions by version id")
    sh.add_argument("--format", choices=["text", "json"], default="text")

    cmp = sub.add_parser("compare", aliases=["cmp", "c"], help="HTML comparison board")
    cmp.add_argument("versions", nargs="*", help="Versions to compare")
    cmp.add_argument("--favorites", action="store_true", help="Compare favorites")
    cmp.add_argument("--top", type=int, help="Compare top N")
    cmp.add_argument("--output", "-o", help="Output HTML path")

    diag = sub.add_parser("diagnose", aliases=["diag"], help="Compare diagnostic metadata for versions side-by-side")
    diag.add_argument("versions", nargs="+", help="Versions to diagnose (e.g. v14 v15)")
    diag.add_argument("--format", choices=["text", "json"], default="text", help="Output format")

    sub.add_parser("evolve", aliases=["ev", "e"], help="Analyze prompt patterns")

    ins = sub.add_parser("inspire", aliases=["insp", "i"], help="Browse or list inspiration")
    ins.add_argument("category", nargs="?", default="symbol", help=f"Category: {', '.join(INSPIRE_URLS.keys())}")
    ins.add_argument("--url", help="Open a custom inspiration URL")
    ins.add_argument("--label", help="Optional label for external inspiration captures")
    ins.add_argument("--list", dest="list_only", action="store_true", help="List saved inspiration assets")
    ins.add_argument("--brand", help="Brand key to configure inspiration sources for")
    ins.add_argument("--sources", action="append", help="Comma-separated inspiration source keys to attach to the brand")
    ins.add_argument("--clear", action="store_true", help="Clear configured inspiration sources for the brand")
    ins.add_argument("--show", action="store_true", help="Show current inspiration configuration for the brand")
    ins.add_argument("--format", choices=["text", "json"], default="text")

    args = parser.parse_args()
    cmd_map = {
        "bootstrap": cmd_bootstrap,
        "types": lambda _args: list_material_types(),
        "init": cmd_init,
        "start-testing": cmd_start_testing,
        "use": cmd_use,
        "list-brands": cmd_list_brands,
        "extract-brand": cmd_extract_brand,
        "build-identity": cmd_build_identity,
        "describe-brand": cmd_describe_brand,
        "show-identity": cmd_show_identity,
        "show-blackboard": cmd_show_blackboard,
        "show-session-summary": cmd_show_session_summary,
        "show-workflow-lineage": cmd_show_workflow_lineage,
        "show-reference-analysis": cmd_show_reference_analysis,
        "route-request": cmd_route_request,
        "resolve-prompt": cmd_resolve_prompt,
        "review-prompt": cmd_review_prompt,
        "validate-identity": cmd_validate_identity,
        "parse-design-memory": cmd_parse_design_memory,
        "extract-css-variables": cmd_extract_css_variables,
        "diff-design-memory": cmd_diff_design_memory,
        "extract-inspiration": cmd_extract_inspiration,
        "inspiration-mode": cmd_inspiration_mode,
        "shotlist": cmd_shotlist,
        "capture-product": cmd_capture_product,
        "explore-brand": cmd_explore_brand,
        "plan-set": cmd_plan_set,
        "validate-brand-fit": cmd_validate_brand_fit,
        "validate-set": cmd_validate_set,
        "generate-set": cmd_generate_set,
        "ideate-copy": cmd_ideate_copy,
        "ideate-messaging": cmd_ideate_messaging,
        "promote-messaging": cmd_promote_messaging,
        "update-messaging": cmd_update_messaging,
        "show-iteration-memory": cmd_show_iteration_memory,
        "update-iteration-memory": cmd_update_iteration_memory,
        "review-brand": cmd_review_brand,
        "suggest-role-pack": cmd_suggest_role_pack,
        "plan-material": cmd_plan_material,
        "plan-draft": cmd_plan_draft,
        "critique-plan": cmd_critique_plan,
        "build-generation-scratchpad": cmd_build_generation_scratchpad,
        "ideate-material": cmd_ideate_material,
        "example-sources": cmd_example_sources,
        "collect-examples": cmd_collect_examples,
        "social-specs": cmd_social_specs,
        "generate": cmd_generate,
        "gen": cmd_generate,
        "g": cmd_generate,
        "pipeline": cmd_pipeline,
        "feedback": cmd_feedback,
        "fb": cmd_feedback,
        "f": cmd_feedback,
        "show": cmd_show,
        "s": cmd_show,
        "compare": cmd_compare,
        "cmp": cmd_compare,
        "c": cmd_compare,
        "diagnose": cmd_diagnose,
        "diag": cmd_diagnose,
        "evolve": cmd_evolve,
        "ev": cmd_evolve,
        "e": cmd_evolve,
        "inspire": cmd_inspire,
        "insp": cmd_inspire,
        "i": cmd_inspire,
    }
    cmd_map[args.command](args)


if __name__ == "__main__":
    main()
