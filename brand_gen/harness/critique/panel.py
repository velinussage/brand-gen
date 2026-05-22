"""Concurrent critique panel fanning out to the 3 critics concurrently."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import dspy

from brand_gen.scoring.program import _extract_json_dict, _extract_text


def load_agent_prompt(agent_id: str) -> str:
    """Load the Markdown prompt body of an agent mirror."""
    repo_root = Path(__file__).resolve().parents[3]
    path = repo_root / ".claude" / "agents" / f"{agent_id}.md"
    if not path.exists():
        path = repo_root / "agents" / f"{agent_id}.agent.md"
    if not path.exists():
        raise ValueError(f"Agent prompt mirror for '{agent_id}' not found.")

    content = path.read_text(encoding="utf-8")
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return content.strip()


async def run_critic_agent(
    lm: dspy.LM,
    critic_id: str,
    image_path: Path | None,
    material_type: str,
    generation_prompt: str,
    text_details: dict[str, Any],
) -> dict[str, Any]:
    """Runs a single critic agent using its mirror prompt and concurrent thread execution."""
    try:
        system_prompt = load_agent_prompt(critic_id)
    except Exception as exc:
        return {
            "critic_id": critic_id,
            "score": 3,
            "rationale": f"Failed to load agent prompt: {exc}",
            "evidence": [],
            "blocking": [f"prompt_load_error: {exc}"],
        }

    user_text = f"""
We have generated a '{material_type}' candidate based on the following physical generation prompt:
"{generation_prompt}"

Additional text and details parsed from the generation payload:
{json.dumps(text_details, indent=2)}

Please perform your rigorous review as specified in your instructions.
For your review, you must output a JSON object containing:
- score (an integer 1 to 5, where 5 is exceptional alignment and 1 is catastrophic failure)
- rationale (a thorough, multi-sentence critique justifying the score)
- evidence (a list of specific visual or textual details supporting your rationale)
- blocking (a list of blocking findings that must be resolved, or empty if none)

Return ONLY valid JSON.
"""

    if image_path and image_path.exists():
        from brand_gen.scoring.config import build_cached_messages, image_source_from_path
        try:
            image_source = image_source_from_path(image_path)
            messages = build_cached_messages(
                system_prompt=system_prompt,
                image_source=image_source,
                user_text=user_text,
            )
        except Exception as exc:
            # Fallback to text-only if image reading fails
            messages = [
                {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
                {"role": "user", "content": [{"type": "text", "text": f"{user_text}\n\n[WARNING: Failed to load image: {exc}]"}]},
            ]
    else:
        messages = [
            {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
            {"role": "user", "content": [{"type": "text", "text": user_text}]},
        ]

    # Run synchronous LiteLLM/dspy.LM call inside thread pool for concurrency
    loop = asyncio.get_running_loop()
    try:
        raw = await loop.run_in_executor(None, lambda: lm(messages=messages))
        text = _extract_text(raw)
        parsed = _extract_json_dict(text)
    except Exception as exc:
        return {
            "critic_id": critic_id,
            "score": 3,
            "rationale": f"LM execution failed: {exc}",
            "evidence": [],
            "blocking": [f"lm_execution_error: {exc}"],
        }

    try:
        score = int(parsed.get("score") or 3)
        score = max(1, min(5, score))
    except (ValueError, TypeError):
        score = 3

    return {
        "critic_id": critic_id,
        "score": score,
        "rationale": str(parsed.get("rationale") or "No rationale provided.").strip(),
        "evidence": list(parsed.get("evidence") or []),
        "blocking": list(parsed.get("blocking") or []),
    }


async def run_critic_panel(
    lm: dspy.LM,
    image_path: Path | None,
    material_type: str,
    generation_prompt: str,
    text_details: dict[str, Any],
    critic_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Runs the critics concurrently using asyncio.gather."""
    critics = critic_ids if critic_ids is not None else [
        "product-truth-reviewer",
        "critic-composition",
        "critic-copy",
    ]
    tasks = [
        run_critic_agent(
            lm=lm,
            critic_id=critic,
            image_path=image_path,
            material_type=material_type,
            generation_prompt=generation_prompt,
            text_details=text_details,
        )
        for critic in critics
    ]
    return list(await asyncio.gather(*tasks))
