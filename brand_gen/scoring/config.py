"""LM configuration + caching adapter for the v2 scorer.

Design notes (from M2 spike + review):

1. Judge LM: Anthropic Claude Sonnet 4.5 (`claude-sonnet-4-5-20250929`) at
   temperature=0. Sonnet 4.x still honors temperature; Opus 4.7 removed
   temperature so Sonnet is the deterministic choice for scoring.

2. Reflection LM (for v2 GEPA): Opus 4.6 at temperature=1.0, max_tokens=32000.
   Not used in v1.

3. Caching adapter — DEFENSIVE design:
   - DSPy's Signature formatting may or may not preserve Anthropic
     `cache_control` breakpoints (spike inconclusive in this session).
   - Rather than depend on the answer, we BYPASS Signature formatting for
     cache-sensitive paths and build messages directly via
     `build_cached_messages()`. This gives us explicit control over the
     `cache_control` markers regardless of DSPy's internal normalization.
   - Describe + Synthesize still go through Signatures (called once per
     critique, caching doesn't help there).

4. DSPy's own cache is DISABLED (`cache=False`) in CI / production to keep
   behavior deterministic. Anthropic prompt caching is the win; DSPy's
   local response cache is noise.

5. Image cache TTL is 5 minutes ephemeral — enough to span the 5-7 axis
   calls within one critique. System-prompt + rubric cache TTL is also
   5 minutes ephemeral (Anthropic's standard; 1-hour cache is a beta).

Operational note for VLM / judge LM version upgrades:
When Anthropic ships a new Sonnet / Opus model, every compiled rubric
prompt needs to be re-evaluated against the new model before shipping.
Process: (a) freeze optimizer, (b) re-measure kappa on the holdout set,
(c) decide whether to accept the new baseline or roll back. Full
baseline re-lock protocol is v2; this note is the v1 placeholder.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

import dspy


# Default routes through OpenRouter (one key, many models). The DEFAULT
# judge is Haiku 4.5 — ~3x cheaper than Sonnet 4.5, still vision-capable
# and strong enough for rubric scoring work. Upgrade to Sonnet 4.5 if
# kappa against user scores plateaus and cheaper-model failure modes
# show up in disagreement logs. GEPA reflection LM in v2 stays on Sonnet
# 4.5 or higher (reflection quality matters more than critic quality).
#
# Cost tier comparison (OpenRouter, approximate early 2026 pricing):
#   openrouter/google/gemini-2.5-flash            ~$0.30 / $2.50 per M     (cheapest; good vision)
#   openrouter/openai/gpt-4.1-mini                ~$0.15 / $0.60 per M     (even cheaper; smaller vision)
#   openrouter/anthropic/claude-haiku-4.5         ~$1.00 / $5.00 per M     (DEFAULT; balanced)
#   openrouter/anthropic/claude-sonnet-4.5        ~$3.00 / $15.00 per M    (upgrade if Haiku plateaus)
#   openrouter/anthropic/claude-opus-4.5          ~$5.00 / $25.00 per M    (reserve for reflection LM)
#
# Per-critique cost @ 9 calls with caching adapter:
#   Haiku 4.5:      ~$0.003 per critique
#   Sonnet 4.5:     ~$0.015 per critique
#   Gemini 2.5 Flash: ~$0.001 per critique (if caching works via OpenRouter)
#
# Override via BRAND_GEN_SCORER_MODEL env var or configure_judge_lm(model=...).
# Direct Anthropic routing also supported (use anthropic/claude-...-date format).
DEFAULT_JUDGE_MODEL = "openrouter/anthropic/claude-haiku-4.5"
DEFAULT_REFLECTION_MODEL = "openrouter/anthropic/claude-sonnet-4.5"  # v2 GEPA; quality > cost here


def configure_judge_lm(model: str | None = None) -> dspy.LM:
    """Configure the scoring judge LM.

    Defaults to OpenRouter routing (OPENROUTER_API_KEY required). Override
    via `model=` arg or BRAND_GEN_SCORER_MODEL env var. Honors DSPy's
    global `configure(lm=...)` so downstream Signatures pick it up.

    For direct Anthropic routing instead of OpenRouter:
        configure_judge_lm("anthropic/claude-sonnet-4-5-20250929")
    (requires ANTHROPIC_API_KEY env var)
    """
    model = model or os.environ.get("BRAND_GEN_SCORER_MODEL") or DEFAULT_JUDGE_MODEL

    # OpenRouter exposes Anthropic's prompt-caching beta transparently.
    # When routing directly through the Anthropic adapter, we still need
    # the beta header; when routing through OpenRouter, the header is a
    # no-op but LiteLLM forwards it harmlessly.
    extra_headers = {"anthropic-beta": "prompt-caching-2024-07-31"}

    judge = dspy.LM(
        model,
        temperature=0,
        max_tokens=2000,
        extra_headers=extra_headers,
    )
    # Disable DSPy's local response cache — Anthropic's prompt cache
    # (via OpenRouter or direct) is the real win; process-local
    # memoization hides behavior in tests.
    dspy.configure(lm=judge, cache=False)
    return judge


def build_cached_messages(
    system_prompt: str,
    image_source: dict[str, Any],
    user_text: str,
    *,
    cache_system: bool = True,
    cache_image: bool = True,
) -> list[dict[str, Any]]:
    """Construct Anthropic-shaped messages with explicit cache_control
    breakpoints.

    Shape matches Anthropic's content-block format. LiteLLM's Anthropic
    adapter preserves this structure when routed through
    `dspy.LM.__call__(messages=[...])` (spike is the definitive answer;
    this is the shape that works in all known cases).

    Args:
        system_prompt: the full system-level context (rubric + instructions).
        image_source: Anthropic image source block, e.g.
            {"type": "base64", "media_type": "image/png", "data": "..."}
            or {"type": "url", "url": "..."}
        user_text: the specific question / axis definition for this call.
        cache_system: place a cache_control breakpoint on the system block.
        cache_image: place a cache_control breakpoint on the image block.
    """
    system_block: dict[str, Any] = {"type": "text", "text": system_prompt}
    if cache_system:
        system_block["cache_control"] = {"type": "ephemeral"}

    image_block: dict[str, Any] = {"type": "image", "source": dict(image_source)}
    if cache_image:
        image_block["cache_control"] = {"type": "ephemeral"}

    return [
        {"role": "system", "content": [system_block]},
        {
            "role": "user",
            "content": [
                image_block,
                {"type": "text", "text": user_text},
            ],
        },
    ]


def image_source_from_path(image_path: str | Path) -> dict[str, Any]:
    """Load a local image into Anthropic's base64 source block format."""
    path = Path(image_path)
    data = path.read_bytes()
    media_type = _guess_media_type(path)
    return {
        "type": "base64",
        "media_type": media_type,
        "data": base64.b64encode(data).decode("ascii"),
    }


def _guess_media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in (".jpg", ".jpeg"):
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".gif":
        return "image/gif"
    return "image/png"  # safe default
