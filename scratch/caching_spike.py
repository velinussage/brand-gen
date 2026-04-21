"""DSPy 3.1.3 + Anthropic prompt-caching passthrough spike.

Purpose: verify that a long system/user prompt cached via `cache_control`
breakpoints actually gets a cache hit on the second call, when routed through
DSPy's LM abstraction (LiteLLM under the hood).

Pass condition: second response.usage shows cache_read_input_tokens > 0.

If pass: the M2 caching adapter can be ~40 lines (explicit cache_control on
system/user blocks passed through dspy.LM.__call__(messages=...)).

If fail: budget +1 day for a custom AnthropicDirectLM(dspy.LM) subclass that
bypasses LiteLLM for the Anthropic adapter only.

Uses text-only to avoid image-encoding overhead; the cache-passthrough
question is independent of content type. Image cache behavior will be
verified in M2 with a second smaller spike.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Load .env manually (DSPy / LiteLLM don't auto-load it in all paths)
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

# Honors OpenRouter by default (brand-gen's scoring uses openrouter/... routing).
# Falls back to direct Anthropic if only ANTHROPIC_API_KEY is set.
if not os.environ.get("OPENROUTER_API_KEY") and not os.environ.get("ANTHROPIC_API_KEY"):
    print("Neither OPENROUTER_API_KEY nor ANTHROPIC_API_KEY set; cannot run spike.")
    print("Export one (OpenRouter preferred) or put it in .env.")
    sys.exit(2)

import dspy

# Build a prompt that's long enough to be cacheable (Anthropic requires >=1024 tokens
# on Sonnet 4.x for cache_control to take effect).
BIG_SYSTEM_PROMPT = (
    "You are a rubric-based evaluator. Score the described design against the rubric. "
    "The rubric has the following axes: composition, brand_coherence, restraint, "
    "story_fidelity, meaning_clarity. For each axis, consider the following guidance: "
) + ("This is padding text to push the cache prefix above the 1024-token threshold. " * 120)

USER_CONTENT = "A minimalist landing-hero design with cream background and serif headline. One dominant gesture."


def call_with_cache_control(lm: dspy.LM, system_text: str, user_text: str) -> dict:
    """Call dspy.LM with explicit Anthropic cache_control on the system block.

    Uses the lower-level messages API that DSPy exposes, so we control the
    message shape directly instead of relying on Signature formatting.
    """
    messages = [
        {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": system_text,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
        },
        {"role": "user", "content": user_text},
    ]
    # dspy.LM.__call__ forwards to LiteLLM. Use the kwargs API.
    response = lm(messages=messages)
    return response


def main() -> int:
    print(f"DSPy version: {dspy.__version__}")
    print(f"LiteLLM model: anthropic/claude-sonnet-4-5")
    print()

    # Prefer OpenRouter if available (matches brand-gen's default scoring config).
    if os.environ.get("OPENROUTER_API_KEY"):
        model = "openrouter/anthropic/claude-sonnet-4.5"
    else:
        model = "anthropic/claude-sonnet-4-5-20250929"
    print(f"model: {model}")

    lm = dspy.LM(
        model,
        temperature=0,
        max_tokens=128,
        cache=False,  # disable DSPy's local cache so we measure Anthropic cache
        extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
    )
    dspy.configure(lm=lm, cache=False)

    print("Call 1 (cold) …")
    try:
        r1 = call_with_cache_control(lm, BIG_SYSTEM_PROMPT, USER_CONTENT)
    except Exception as exc:
        print(f"Call 1 failed: {type(exc).__name__}: {exc}")
        return 1
    print(f"  response type: {type(r1).__name__}")
    if isinstance(r1, list):
        print(f"  response[0]: {str(r1[0])[:120]}...")
    else:
        print(f"  response: {str(r1)[:120]}...")

    # LiteLLM usage tracking: dspy.LM stores recent calls in .history
    if hasattr(lm, "history") and lm.history:
        h1 = lm.history[-1]
        usage1 = h1.get("usage") or {}
        print(f"  usage: {usage1}")
        c1 = usage1.get("cache_creation_input_tokens", 0)
        r1 = usage1.get("cache_read_input_tokens", 0)
        print(f"  cache_creation_input_tokens: {c1}")
        print(f"  cache_read_input_tokens: {r1}")
    else:
        print("  (no history on lm)")
    print()

    print("Call 2 (same system prompt; should hit cache) …")
    try:
        r2 = call_with_cache_control(lm, BIG_SYSTEM_PROMPT, "Different user question: is the design readable at thumbnail size?")
    except Exception as exc:
        print(f"Call 2 failed: {type(exc).__name__}: {exc}")
        return 1

    if hasattr(lm, "history") and lm.history:
        h2 = lm.history[-1]
        usage2 = h2.get("usage") or {}
        print(f"  usage: {usage2}")
        # LiteLLM normalizes Anthropic cache fields into prompt_tokens_details.
        # Names differ across providers — we check the union.
        details2 = usage2.get("prompt_tokens_details") or {}
        if hasattr(details2, "__dict__"):
            details2 = details2.__dict__
        cached2 = (
            usage2.get("cache_read_input_tokens", 0)  # native Anthropic key
            or (details2.get("cached_tokens") if isinstance(details2, dict) else 0)
            or 0
        )
        writes2 = (
            usage2.get("cache_creation_input_tokens", 0)
            or (details2.get("cache_write_tokens") if isinstance(details2, dict) else 0)
            or 0
        )
        print(f"  cache_write_tokens: {writes2}")
        print(f"  cached_tokens (read): {cached2}")

        print()
        if cached2 > 0:
            print("=" * 60)
            print("PASS: cached_tokens > 0 on second call.")
            print("DSPy 3.1.3 -> LiteLLM -> (OpenRouter|Anthropic) preserves")
            print("cache_control passthrough. The caching adapter works.")
            print("=" * 60)
            return 0
        elif writes2 > 0 and cached2 == 0:
            print("=" * 60)
            print("PARTIAL: cache was created but not read on the second call.")
            print("This may mean the cache breakpoint is being preserved but")
            print("the system block subtly differs between calls. Investigate.")
            print("=" * 60)
            return 3
        else:
            print("=" * 60)
            print("FAIL: no cache activity on either call.")
            print("LiteLLM is probably stripping cache_control.")
            print("Consider a custom dspy.LM subclass that bypasses LiteLLM.")
            print("=" * 60)
            return 4
    else:
        print("  (no history on lm)")
        return 5


if __name__ == "__main__":
    sys.exit(main())
