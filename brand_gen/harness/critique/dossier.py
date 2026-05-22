"""Dossier compilation and Synthesizer agent integration."""

from __future__ import annotations

from pathlib import Path
import time
import json
import asyncio
from typing import Any

import dspy

from brand_gen.harness.critique import panel
from brand_gen.harness.critique.claims import aggregate_surviving_claims
from brand_gen.scoring.program import _extract_json_dict, _extract_text

async def run_synthesizer_agent(
    lm: dspy.LM,
    material_type: str,
    creative_brief: str,
    critics_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Runs the Synthesizer agent to compile and consolidate individual critiques into a dossier."""
    system_prompt = panel.load_agent_prompt("synthesizer")

    user_text = f"""
We have completed a concurrent 3-critic panel review for a '{material_type}' candidate.

Creative Brief / Thesis:
{creative_brief}

Critics Feedback:
{json.dumps(critics_results, indent=2)}

Please synthesize these individual reviews into a single, cohesive, premium Review Dossier.
You must return a JSON object with:
- score: float (synthesized overall score from 1.0 to 5.0, reflecting visual and strategic quality)
- recommendation: string (one of: "lock", "promote", "safe-refine", "branch", "abandon")
- blocking_findings: list of strings (consolidated and prioritized blocking issues that must be fixed)
- prose_summary: string (detailed, premium, markdown-formatted prose explaining the consensus, strengths, weaknesses, and clear actionable steps for the next iteration)

Return ONLY valid JSON.
"""

    messages = [
        {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
        {"role": "user", "content": [{"type": "text", "text": user_text}]},
    ]

    loop = asyncio.get_running_loop() if hasattr(asyncio, "get_running_loop") else None
    try:
        if loop is not None:
            raw = await loop.run_in_executor(None, lambda: lm(messages=messages))
        else:
            raw = lm(messages=messages)
        text = _extract_text(raw)
        parsed = _extract_json_dict(text)
    except Exception as exc:
        # Fallback if synthesis fails
        avg_score = sum(c.get("score", 3) for c in critics_results) / len(critics_results)
        all_blocking = []
        for c in critics_results:
            all_blocking.extend(c.get("blocking", []))
        return {
            "score": avg_score,
            "recommendation": "safe-refine" if all_blocking else "lock",
            "blocking_findings": list(set(all_blocking)),
            "prose_summary": f"Fallback synthesis. Synthesis failed: {exc}",
        }

    return {
        "score": float(parsed.get("score") or 3.0),
        "recommendation": str(parsed.get("recommendation") or "safe-refine").strip().lower(),
        "blocking_findings": list(parsed.get("blocking_findings") or []),
        "prose_summary": str(parsed.get("prose_summary") or "").strip(),
    }


def write_dossier(
    brand_dir: Path,
    run_id: str,
    campaign_id: str,
    version_id: str,
    material_type: str,
    creative_brief: str,
    critics_results: list[dict[str, Any]],
    synthesis: dict[str, Any],
) -> tuple[Path, Path]:
    """Write the paired JSON + Markdown dossier to `reviews/` under the brand directory."""
    brand_dir = Path(brand_dir).expanduser().resolve()
    reviews_dir = brand_dir / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)

    json_path = reviews_dir / f"{version_id}-dossier.json"
    md_path = reviews_dir / f"{version_id}-dossier.md"

    # Compute prioritized surviving claims
    surviving_claims = aggregate_surviving_claims(critics_results)

    # 1. Compile and save JSON dossier
    dossier_data = {
        "schema_type": "review_dossier",
        "schema_version": 1,
        "run_id": run_id,
        "campaign_id": campaign_id,
        "version_id": version_id,
        "material_type": material_type,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "score": synthesis["score"],
        "recommendation": synthesis["recommendation"],
        "blocking_findings": synthesis["blocking_findings"],
        "critics": critics_results,
        "surviving_claims": surviving_claims,
        "prose_summary": synthesis["prose_summary"],
        "creative_brief": creative_brief,
    }

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(dossier_data, f, indent=2)
        f.write("\n")

    # 2. Render and save Markdown dossier
    blocking_section = ""
    if synthesis["blocking_findings"]:
        bullets = "\n".join(f"- 🔴 {issue}" for issue in synthesis["blocking_findings"])
        blocking_section = f"\n### 🛑 BLOCKING FINDINGS\n{bullets}\n"

    claims_section = ""
    if surviving_claims:
        claims_lines = [
            "## 🔍 Surviving Claims (Prioritized)",
            "",
            "| Axis | Severity | Consensus | Observation | Source Critics |",
            "| :--- | :---: | :---: | :--- | :--- |",
        ]
        for claim in surviving_claims:
            icon = "🔴" if claim["severity"] == "blocking" else "⚠️"
            critics = ", ".join(str(c).replace("-", " ").title() for c in claim["source_critics"])
            claims_lines.append(
                f"| **{claim['axis'].upper()}** | {icon} {claim['severity'].title()} | {claim['consensus_level'].title()} | {claim['text']} | {critics} |"
            )
        claims_section = "\n" + "\n".join(claims_lines) + "\n"

    critics_table_lines = [
        "| Critic | Score | Key Takeaway |",
        "| :--- | :---: | :--- |",
    ]
    for c in critics_results:
        role_label = str(c["critic_id"]).replace("-", " ").title()
        short_rat = c["rationale"].split(".")[0] + "."
        critics_table_lines.append(f"| **{role_label}** | {c['score']}/5 | {short_rat} |")
    critics_table = "\n".join(critics_table_lines)

    md_content = f"""# Creative Dossier: {version_id}
**Material Type:** `{material_type}`
**Campaign ID:** `{campaign_id}`
**Run ID/Workflow:** `{run_id}`
**Overall Synthesized Score:** `{synthesis["score"]:.1f} / 5.0`
**Recommendation:** **`{synthesis["recommendation"].upper()}`**

---

## 📋 Executive Summary
{synthesis["prose_summary"]}
{blocking_section}
---
{claims_section}
---

## ⚖️ Panel Breakdown
{critics_table}

---

## 🎨 Creative Thesis Context
{creative_brief}
"""

    md_path.write_text(md_content.strip() + "\n", encoding="utf-8")

    return json_path, md_path
