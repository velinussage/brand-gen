from __future__ import annotations

from pathlib import Path
from typing import Any

from brand_gen.memory import (
    append_event_to_ledger,
    read_ledger_events,
    get_markdown_path,
    register_summarizer,
)

def project_brand_memory(brand_dir: Path) -> dict[str, Any]:
    """Projects brand ledger events into a structured brand state."""
    events = read_ledger_events(brand_dir, "brand")
    
    state = {
        "brand_notes": [],
        "messaging_notes": [],
        "copy_notes": [],
        "material_notes": {},
        "palette": {},
        "typography": {},
        "devices": [],
        "forbidden_patterns": [],
        "promoted_rules": [],
    }
    
    for event in events:
        payload = event.get("payload") or {}
        etype = event.get("event_type")
        
        if etype == "note_added":
            note = str(payload.get("note") or "").strip()
            cat = str(payload.get("category") or "brand").strip()
            if not note:
                continue
                
            if cat == "brand":
                if note not in state["brand_notes"]:
                    state["brand_notes"].append(note)
            elif cat == "messaging":
                if note not in state["messaging_notes"]:
                    state["messaging_notes"].append(note)
            elif cat == "copy":
                if note not in state["copy_notes"]:
                    state["copy_notes"].append(note)
            elif cat == "material":
                mtype = str(payload.get("material_type") or "general").strip()
                state["material_notes"].setdefault(mtype, [])
                if note not in state["material_notes"][mtype]:
                    state["material_notes"][mtype].append(note)
                    
        elif etype == "palette_updated":
            state["palette"] = dict(payload.get("palette") or {})
            
        elif etype == "typography_updated":
            state["typography"] = dict(payload.get("typography") or {})
            
        elif etype == "devices_updated":
            state["devices"] = list(payload.get("devices") or [])
            
        elif etype == "forbidden_pattern_appended":
            pat = str(payload.get("pattern") or "").strip()
            if pat and pat not in state["forbidden_patterns"]:
                state["forbidden_patterns"].append(pat)
                
        elif etype == "rule_promoted":
            rule = dict(payload.get("rule") or {})
            if rule and rule not in state["promoted_rules"]:
                state["promoted_rules"].append(rule)
                
    return state

def add_brand_note(brand_dir: Path, note: str, category: str = "brand", material_type: str | None = None) -> dict[str, Any]:
    """Appends a new note_added event to the brand ledger."""
    payload = {
        "note": note,
        "category": category,
        "material_type": material_type,
    }
    event = append_event_to_ledger(brand_dir, "brand", "note_added", payload)
    summarize_brand_memory(brand_dir)
    return event

def summarize_brand_memory(brand_dir: Path) -> None:
    """Renders the projected brand memory state into a derived markdown file."""
    state = project_brand_memory(brand_dir)
    md_path = get_markdown_path(brand_dir, "brand")
    
    lines = [
        "# Brand Memory Dossier",
        "",
        "> [!NOTE]",
        "> This is a derived markdown file generated from the canonical append-only brand event ledger.",
        "",
    ]
    
    if state["brand_notes"]:
        lines.append("## Core Brand Notes")
        for item in state["brand_notes"]:
            lines.append(f"- {item}")
        lines.append("")
        
    if state["messaging_notes"]:
        lines.append("## Core Messaging & Positioning Notes")
        for item in state["messaging_notes"]:
            lines.append(f"- {item}")
        lines.append("")
        
    if state["copy_notes"]:
        lines.append("## Core Copy & Tone Notes")
        for item in state["copy_notes"]:
            lines.append(f"- {item}")
        lines.append("")
        
    if state["material_notes"]:
        lines.append("## Material-Specific Prose Directives")
        for key, notes in sorted(state["material_notes"].items()):
            lines.append(f"### {key}")
            for item in notes:
                lines.append(f"- {item}")
            lines.append("")
            
    if state["palette"]:
        lines.append("## Palette Tokens")
        lines.append("```json")
        lines.append(json.dumps(state["palette"], indent=2))
        lines.append("```")
        lines.append("")
        
    if state["typography"]:
        lines.append("## Typography Roles")
        lines.append("```json")
        lines.append(json.dumps(state["typography"], indent=2))
        lines.append("```")
        lines.append("")
        
    if state["devices"]:
        lines.append("## Approved Visual Devices")
        for device in state["devices"]:
            lines.append(f"- {device}")
        lines.append("")
        
    if state["forbidden_patterns"]:
        lines.append("## Banned Copy / Visual Patterns")
        for pattern in state["forbidden_patterns"]:
            lines.append(f"- `{pattern}`")
        lines.append("")
        
    if state["promoted_rules"]:
        lines.append("## Promoted Brand Learnings & Rules")
        for rule in state["promoted_rules"]:
            txt = rule.get("text") or ""
            src = rule.get("source") or "promoted"
            lines.append(f"- **{src}**: {txt}")
        lines.append("")
        
    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

# Register with package summarization manager
register_summarizer("brand", summarize_brand_memory)
