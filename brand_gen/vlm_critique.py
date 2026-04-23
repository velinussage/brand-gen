from __future__ import annotations

import base64
import json
import mimetypes
import os
from pathlib import Path

from .runtime_brand import load_system_prompt

VLM_CRITIQUE_SYSTEM = load_system_prompt("vlm_critique")
REFERENCE_ANALYSIS_SYSTEM = load_system_prompt("reference_analysis")


def extract_json_dict(text: str) -> dict | None:
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


def _extract_completion_text(message_content) -> str:
    if isinstance(message_content, str):
        return message_content
    if isinstance(message_content, list):
        parts: list[str] = []
        for block in message_content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return ""


def _resolve_openrouter_vlm_model(merged_env: dict[str, str]) -> str:
    model = (
        merged_env.get("BRAND_GEN_VLM_MODEL")
        or merged_env.get("OPENROUTER_VLM_MODEL")
        or "anthropic/claude-haiku-4.5"
    )
    model = str(model).strip()
    if model.startswith("openrouter/"):
        model = model.split("/", 1)[1]
    return model or "anthropic/claude-haiku-4.5"


def run_vlm_json(image_path: Path, system_prompt: str, user_text: str, *, env: dict | None = None, max_tokens: int = 1024) -> dict | None:
    if not image_path.exists():
        return None
    img_bytes = image_path.read_bytes()
    img_b64 = base64.b64encode(img_bytes).decode("utf-8")
    mime = mimetypes.guess_type(str(image_path))[0] or "image/jpeg"
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)

    openrouter_key = merged_env.get("OPENROUTER_API_KEY")
    if openrouter_key:
        try:
            import httpx
            model = _resolve_openrouter_vlm_model(merged_env)
            resp = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {openrouter_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": merged_env.get("OPENROUTER_HTTP_REFERER", "https://brand-gen.local"),
                    "X-Title": merged_env.get("OPENROUTER_TITLE", "brand-gen"),
                },
                json={
                    "model": model,
                    "max_tokens": max_tokens,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": [
                            {"type": "text", "text": user_text},
                            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}},
                        ]},
                    ],
                },
                timeout=60.0,
            )
            if resp.status_code == 200:
                body = resp.json()
                text = _extract_completion_text(body.get("choices", [{}])[0].get("message", {}).get("content", ""))
                parsed = extract_json_dict(text)
                if parsed is not None:
                    return dict(parsed, vlm_provider="openrouter", vlm_model=model)
        except Exception as exc:
            print(f"VLM (OpenRouter) error: {exc}", file=os.sys.stderr)

    anthropic_key = merged_env.get("ANTHROPIC_API_KEY")
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
                parsed = extract_json_dict(text)
                if parsed is not None:
                    return dict(parsed, vlm_provider="anthropic")
        except Exception as exc:
            print(f"VLM (Claude) error: {exc}", file=os.sys.stderr)

    return None


def vlm_stub(reason: str) -> dict:
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


def parse_vlm_json(text: str) -> dict:
    data = extract_json_dict(text)
    if isinstance(data, dict):
        data.setdefault("approved", not bool(data.get("p1")))
        data.setdefault("p1", [])
        data.setdefault("p2", [])
        data.setdefault("p3", [])
        data.setdefault("clean", [])
        data.setdefault("refinement_suggestion", "")
        data["vlm_available"] = True
        return data
    return vlm_stub(f"VLM returned unparseable response: {text[:200]}")


def run_vlm_critique(image_path: Path, brief: str, brand_dna: dict, *, env: dict | None = None) -> dict:
    palette = ", ".join(str(c) for c in (brand_dna.get("palette_direction") or [])[:6])
    approved = "; ".join(str(d) for d in (brand_dna.get("approved_graphic_devices") or [])[:4])
    forbidden = "; ".join(str(d) for d in (brand_dna.get("forbidden_elements") or [])[:4])

    user_text = (
        f"## Brand DNA\nPalette: {palette}\nApproved devices: {approved}\n"
        f"Forbidden: {forbidden}\n\n## Brief\n{brief[:1500]}\n\n"
        "Analyze the attached image against the brand DNA and brief. Return JSON only."
    )

    parsed = run_vlm_json(image_path, VLM_CRITIQUE_SYSTEM, user_text, env=env, max_tokens=1024)
    if parsed is None:
        return vlm_stub("No VLM API key available (set OPENROUTER_API_KEY or ANTHROPIC_API_KEY)")
    return parse_vlm_json(json.dumps(parsed))


def refine_prompt_from_vlm_critique(effective_prompt: str, vlm_critique: dict) -> str:
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
