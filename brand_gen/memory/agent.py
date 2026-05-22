from __future__ import annotations

from pathlib import Path
from typing import Any

from brand_gen.memory import (
    append_event_to_ledger,
    read_ledger_events,
    get_markdown_path,
    register_summarizer,
)

def project_agent_memory(brand_dir: Path) -> dict[str, Any]:
    """Projects agent events ledger into structured agent state."""
    events = read_ledger_events(brand_dir, "agent")
    
    state = {
        "recent_style_anchors_by_material": {},
        "last_style_anchor_by_material": {},
        "recent_sage_framings_by_material": {},
        "modelPreferences": [],
        "compositionPatterns": [],
        "failurePatterns": [],
    }
    
    for event in events:
        payload = event.get("payload") or {}
        etype = event.get("event_type")
        
        if etype == "anchor_selected":
            mtype = str(payload.get("material_type") or "").strip()
            anchor = str(payload.get("anchor_version") or "").strip()
            if mtype and anchor:
                state["last_style_anchor_by_material"][mtype] = anchor
                history = list(state["recent_style_anchors_by_material"].get(mtype) or [])
                if anchor in history:
                    history.remove(anchor)
                history.append(anchor)
                state["recent_style_anchors_by_material"][mtype] = history
                
        elif etype == "framing_selected":
            mtype = str(payload.get("material_type") or "").strip()
            framing = str(payload.get("framing_id") or "").strip()
            if mtype and framing:
                history = list(state["recent_sage_framings_by_material"].get(mtype) or [])
                if framing in history:
                    history.remove(framing)
                history.append(framing)
                state["recent_sage_framings_by_material"][mtype] = history
                
        elif etype == "lesson_promoted":
            bucket = str(payload.get("bucket") or "").strip()
            text = str(payload.get("text") or "").strip()
            if bucket in {"modelPreferences", "compositionPatterns", "failurePatterns"} and text:
                entry = {
                    "text": text,
                    "material_type": payload.get("material_type") or "",
                    "evidence_versions": payload.get("evidence_versions") or [],
                    "promoted_at": event.get("timestamp") or "",
                }
                # Check deduplication
                existing = state[bucket]
                if not any(e.get("text") == text for e in existing):
                    existing.append(entry)
                state[bucket] = existing
                
    return state

def add_agent_lesson(brand_dir: Path, bucket: str, text: str, material_type: str, evidence_versions: list[str]) -> dict[str, Any]:
    """Appends a lesson_promoted event to the agent ledger."""
    payload = {
        "bucket": bucket,
        "text": text,
        "material_type": material_type,
        "evidence_versions": evidence_versions,
    }
    event = append_event_to_ledger(brand_dir, "agent", "lesson_promoted", payload)
    summarize_agent_memory(brand_dir)
    return event

def summarize_agent_memory(brand_dir: Path) -> None:
    """Renders agent learnings and rotation indexes in a derived markdown file."""
    state = project_agent_memory(brand_dir)
    md_path = get_markdown_path(brand_dir, "agent")
    
    lines = [
        "# Agent Performance & Learnings Dossier",
        "",
        "> [!NOTE]",
        "> This is a derived markdown file generated from the canonical append-only agent event ledger.",
        "",
    ]
    
    if state["modelPreferences"]:
        lines.append("## Model Performance & Selection Insights")
        for item in state["modelPreferences"]:
            lines.append(f"- **{item['material_type']}**: {item['text']}")
            if item["evidence_versions"]:
                lines.append(f"  *Evidence versions: {', '.join(item['evidence_versions'])}*")
        lines.append("")
        
    if state["compositionPatterns"]:
        lines.append("## Reusable Composition Insights")
        for item in state["compositionPatterns"]:
            lines.append(f"- **{item['material_type']}**: {item['text']}")
            if item["evidence_versions"]:
                lines.append(f"  *Evidence versions: {', '.join(item['evidence_versions'])}*")
        lines.append("")
        
    if state["failurePatterns"]:
        lines.append("## Known Failure Patterns to Avoid")
        for item in state["failurePatterns"]:
            lines.append(f"- **{item['material_type']}**: {item['text']}")
            if item["evidence_versions"]:
                lines.append(f"  *Evidence versions: {', '.join(item['evidence_versions'])}*")
        lines.append("")
        
    # Show active rotation states
    if state["last_style_anchor_by_material"]:
        lines.append("## Style Anchor Rotations")
        for mtype, anchor in sorted(state["last_style_anchor_by_material"].items()):
            history = state["recent_style_anchors_by_material"].get(mtype) or []
            lines.append(f"- **{mtype}**: current=`{anchor}` | rotation queue={history}")
        lines.append("")
        
    if state["recent_sage_framings_by_material"]:
        lines.append("## Sage Product Framing Rotations")
        for mtype, framings in sorted(state["recent_sage_framings_by_material"].items()):
            lines.append(f"- **{mtype}**: rotation queue={framings}")
        lines.append("")
        
    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

# Register with package summarization manager
register_summarizer("agent", summarize_agent_memory)
