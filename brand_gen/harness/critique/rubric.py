"""Hard constraints deterministic gating and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from brand_gen.harness.policy import RunPolicy
from brand_gen.custom_scratchpad import load_custom_scratchpad_json

def check_hard_constraints(
    brand_dir: Path,
    material_type: str,
    generation_prompt: str,
    text_details: dict[str, Any],
    policy: RunPolicy | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run all deterministic hard constraints.
    
    Returns a dict with:
    - passed: bool
    - blocking_failures: list[str]
    - warnings: list[str]
    """
    brand_dir = Path(brand_dir).expanduser().resolve()
    blocking: list[str] = []
    warnings: list[str] = []

    # 1. Forbidden patterns check
    try:
        scratchpad_data = load_custom_scratchpad_json(brand_dir)
        forbidden = scratchpad_data.get("forbidden_patterns") or []
        for item in forbidden:
            pattern = item.get("pattern", "").strip()
            reason = item.get("reason", "").strip()
            if not pattern:
                continue
            
            # Check prompt
            if pattern.lower() in generation_prompt.lower():
                blocking.append(
                    f"Forbidden pattern '{pattern}' detected in generation prompt"
                    + (f" ({reason})" if reason else "")
                )
            
            # Check text details
            for key, val in text_details.items():
                if isinstance(val, str) and pattern.lower() in val.lower():
                    blocking.append(
                        f"Forbidden pattern '{pattern}' detected in text field '{key}'"
                        + (f" ({reason})" if reason else "")
                    )
                elif isinstance(val, list):
                    for idx, v in enumerate(val):
                        if isinstance(v, str) and pattern.lower() in v.lower():
                            blocking.append(
                                f"Forbidden pattern '{pattern}' detected in text list '{key}' at index {idx}"
                                + (f" ({reason})" if reason else "")
                            )
    except Exception as exc:
        warnings.append(f"Failed to run forbidden patterns check: {exc}")

    # 2. Allowed model check
    if policy is not None and metadata is not None:
        used_model = metadata.get("model")
        if used_model and used_model not in policy.allowed_models:
            blocking.append(f"Model '{used_model}' is not in policy allowed_models: {policy.allowed_models}")

    # 3. Allowed tools check
    if policy is not None and metadata is not None:
        used_tools = metadata.get("tools", [])
        for tool in used_tools:
            if tool not in policy.allowed_tools:
                blocking.append(f"Tool '{tool}' is not in policy allowed_tools: {policy.allowed_tools}")

    # 4. Aspect ratio validation (optional)
    if metadata is not None and "aspect_ratio" in metadata:
        expected = metadata.get("expected_aspect_ratio")
        actual = metadata.get("aspect_ratio")
        if expected and actual and expected != actual:
            blocking.append(f"Aspect ratio mismatch: expected {expected}, got {actual}")

    return {
        "passed": len(blocking) == 0,
        "blocking_failures": blocking,
        "warnings": warnings,
    }
