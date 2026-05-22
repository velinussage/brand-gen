from __future__ import annotations

from pathlib import Path
from typing import Any

from brand_gen.memory import (
    append_event_to_ledger,
    read_ledger_events,
    get_markdown_path,
    register_summarizer,
)

def project_artifact_memory(brand_dir: Path) -> dict[str, Any]:
    """Projects artifact events ledger into a structured version registry."""
    events = read_ledger_events(brand_dir, "artifact")
    
    versions = {}
    for event in events:
        payload = event.get("payload") or {}
        etype = event.get("event_type")
        timestamp = event.get("timestamp")
        
        if etype == "artifact_generated":
            vid = payload.get("version_id")
            if not vid:
                continue
                
            versions[vid] = {
                "version_id": vid,
                "material_type": payload.get("material_type") or "",
                "prompt": payload.get("prompt") or "",
                "model": payload.get("model") or "",
                "branch_id": payload.get("branch_id") or "",
                "image_path": payload.get("image_path") or None,
                "score": None,
                "status": "",
                "decision": "",
                "notes": "",
                "verdicts": [],
                "rejection_reason": "",
                "generated_at": timestamp,
            }
            
        elif etype == "artifact_feedback":
            vid = payload.get("version_id")
            if not vid:
                continue
                
            if vid not in versions:
                # Fallback if feedback arrives before generated event
                versions[vid] = {
                    "version_id": vid,
                    "material_type": "",
                    "prompt": "",
                    "model": "",
                    "branch_id": "",
                    "image_path": None,
                    "generated_at": timestamp,
                }
                
            versions[vid].update({
                "score": payload.get("score") if payload.get("score") is not None else versions[vid].get("score"),
                "status": payload.get("status") or versions[vid].get("status") or "",
                "decision": payload.get("decision") or versions[vid].get("decision") or "",
                "notes": payload.get("notes") or versions[vid].get("notes") or "",
                "verdicts": payload.get("verdicts") or versions[vid].get("verdicts") or [],
                "rejection_reason": payload.get("rejection_reason") or versions[vid].get("rejection_reason") or "",
            })
            
    return versions

def add_artifact_feedback(
    brand_dir: Path,
    version_id: str,
    score: int | None,
    status: str | None,
    decision: str | None,
    notes: str | None,
    verdicts: list[dict] | None = None,
    rejection_reason: str | None = None,
) -> dict[str, Any]:
    """Appends an artifact_feedback event to the ledger and runs summarization."""
    payload = {
        "version_id": version_id,
        "score": score,
        "status": status,
        "decision": decision,
        "notes": notes,
        "verdicts": verdicts or [],
        "rejection_reason": rejection_reason,
    }
    event = append_event_to_ledger(brand_dir, "artifact", "artifact_feedback", payload)
    summarize_artifact_memory(brand_dir)
    return event

def get_positive_and_negative_examples(brand_dir: Path) -> tuple[list[dict], list[dict]]:
    """Helper returning positive and negative lists projected from artifact memory."""
    versions = project_artifact_memory(brand_dir)
    positive = []
    negative = []
    
    for item in versions.values():
        decision = item.get("decision") or ""
        status = item.get("status") or ""
        score = item.get("score")
        
        # Build normalized feedback example structure compatible with legacy format
        record = {
            "version": item["version_id"],
            "material_type": item["material_type"],
            "summary": item.get("notes") or item.get("rejection_reason") or "No comments.",
            "score": score if score is not None else 0,
            "status": status,
            "decision": decision,
            "primary_decision": decision,
            "primary_gate": "",
            "verdicts": item.get("verdicts") or [],
            "verdict_conflict": False,
            "conflict_summary": "",
            "branch_id": item.get("branch_id") or "",
        }
        
        # Look for conflicting verdicts
        vlist = item.get("verdicts") or []
        if len(vlist) > 1:
            decisions = {v.get("decision") for v in vlist if v.get("decision")}
            if len(decisions) > 1:
                record["verdict_conflict"] = True
                record["conflict_summary"] = "Critics disagreed on the final decision."
                
        if vlist:
            # Set primary gate/decision from first verdict as default
            record["primary_gate"] = vlist[0].get("gate") or ""
            
        if decision == "approve" or status == "favorite" or (score is not None and score >= 4):
            positive.append(record)
        elif decision in {"reject", "iterate"} or status == "rejected" or (score is not None and score <= 2):
            negative.append(record)
            
    return positive, negative

def summarize_artifact_memory(brand_dir: Path) -> None:
    """Renders high-performing artifacts and misses to avoid in a derived markdown file."""
    versions = project_artifact_memory(brand_dir)
    positive, negative = get_positive_and_negative_examples(brand_dir)
    md_path = get_markdown_path(brand_dir, "artifact")
    
    lines = [
        "# Generated Artifacts Dossier",
        "",
        "> [!NOTE]",
        "> This is a derived markdown file generated from the canonical append-only artifact event ledger.",
        "",
    ]
    
    if positive:
        lines.append("## High-Performing Brand Artifacts (Favorites)")
        # Show last 12
        for item in positive[-12:]:
            lines.append(f"### Version `{item['version']}` ({item['material_type']}) — Score: {item['score']}")
            lines.append(f"- **Decision**: `{item['decision']}`")
            lines.append(f"- **Summary/Notes**: {item['summary']}")
            if item["verdicts"]:
                lines.append("- **Critic Verdicts**:")
                for v in item["verdicts"]:
                    lines.append(f"  - *{v.get('gate', 'critic')}*: score={v.get('score')}, decision={v.get('decision')}")
            lines.append("")
            
    if negative:
        lines.append("## Misses to Avoid (Failed/Rejected)")
        # Show last 12
        for item in negative[-12:]:
            lines.append(f"### Version `{item['version']}` ({item['material_type']}) — Score: {item['score']}")
            lines.append(f"- **Decision**: `{item['decision']}`")
            lines.append(f"- **Summary/Notes**: {item['summary']}")
            if item["verdicts"]:
                lines.append("- **Critic Verdicts**:")
                for v in item["verdicts"]:
                    lines.append(f"  - *{v.get('gate', 'critic')}*: score={v.get('score')}, decision={v.get('decision')}")
            lines.append("")
            
    if versions:
        lines.append("## Complete Generation History")
        for v in sorted(versions.values(), key=lambda x: x.get("generated_at") or "", reverse=True)[:50]:
            score_str = f"Score: {v['score']}" if v['score'] is not None else "Unscored"
            lines.append(f"- **`{v['version_id']}`**: {v['material_type']} | {v['model']} | {score_str} | branch `{v['branch_id']}`")
            lines.append(f"  - *Prompt*: `{v['prompt'][:100]}...`")
        lines.append("")
        
    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

# Register with package summarization manager
register_summarizer("artifact", summarize_artifact_memory)
