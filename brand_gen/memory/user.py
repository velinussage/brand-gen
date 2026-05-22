from __future__ import annotations

from pathlib import Path
from typing import Any

from brand_gen.memory import (
    append_event_to_ledger,
    read_ledger_events,
    get_markdown_path,
    register_summarizer,
)

def project_user_memory(brand_dir: Path) -> dict[str, Any]:
    """Projects user events ledger into structured user preferences state."""
    events = read_ledger_events(brand_dir, "user")
    
    state = {
        "selected_by_material": {},
        "preferred_capsules": [],
        "negative_capsules": [],
        "style_likes": [],
        "style_dislikes": [],
    }
    
    for event in events:
        payload = event.get("payload") or {}
        etype = event.get("event_type")
        timestamp = event.get("timestamp") or ""
        
        if etype == "aesthetic_promoted":
            cid = str(payload.get("capsule_id") or "").strip()
            mtype = str(payload.get("material_type") or "").strip()
            sentiment = str(payload.get("sentiment") or "like").strip().lower()
            note = str(payload.get("note") or "").strip()
            
            entry = {
                "capsule_id": cid,
                "material_type": mtype,
                "note": note,
                "recorded_at": timestamp,
            }
            
            if sentiment in {"dislike", "reject", "negative"}:
                if entry not in state["style_dislikes"]:
                    state["style_dislikes"].append(entry)
                if cid and cid not in state["negative_capsules"]:
                    state["negative_capsules"].append(cid)
            else:
                if entry not in state["style_likes"]:
                    state["style_likes"].append(entry)
                if cid and cid not in state["preferred_capsules"]:
                    state["preferred_capsules"].append(cid)
                if mtype and cid:
                    state["selected_by_material"][mtype] = cid
                    
        elif etype == "capsule_selected":
            mtype = str(payload.get("material_type") or "").strip()
            cid = str(payload.get("capsule_id") or "").strip()
            if mtype and cid:
                state["selected_by_material"][mtype] = cid
                
    return state

def add_user_aesthetic_preference(brand_dir: Path, capsule_id: str, material_type: str, sentiment: str, note: str = "") -> dict[str, Any]:
    """Appends an aesthetic_promoted event to the user ledger."""
    payload = {
        "capsule_id": capsule_id,
        "material_type": material_type,
        "sentiment": sentiment,
        "note": note,
    }
    event = append_event_to_ledger(brand_dir, "user", "aesthetic_promoted", payload)
    summarize_user_memory(brand_dir)
    return event

def summarize_user_memory(brand_dir: Path) -> None:
    """Renders user aesthetic preference state into a derived markdown file."""
    state = project_user_memory(brand_dir)
    md_path = get_markdown_path(brand_dir, "user")
    
    lines = [
        "# User Aesthetic Preferences Dossier",
        "",
        "> [!NOTE]",
        "> This is a derived markdown file generated from the canonical append-only user event ledger.",
        "",
    ]
    
    if state["selected_by_material"]:
        lines.append("## Curated Capsule Selections by Material Type")
        for mtype, cid in sorted(state["selected_by_material"].items()):
            lines.append(f"- **{mtype}**: `{cid}`")
        lines.append("")
        
    if state["preferred_capsules"]:
        lines.append("## Preferred Aesthetic Capsules")
        for cid in sorted(state["preferred_capsules"]):
            lines.append(f"- `{cid}`")
        lines.append("")
        
    if state["negative_capsules"]:
        lines.append("## Avoided / Negative Aesthetic Capsules")
        for cid in sorted(state["negative_capsules"]):
            lines.append(f"- `{cid}`")
        lines.append("")
        
    if state["style_likes"]:
        lines.append("## History of Stylistic Approvals & Likes")
        for item in sorted(state["style_likes"], key=lambda x: x.get("recorded_at") or "", reverse=True):
            capsule_part = f"`{item['capsule_id']}`" if item['capsule_id'] else "General"
            note_part = f" — *{item['note']}*" if item['note'] else ""
            lines.append(f"- **{item['recorded_at']}**: {capsule_part} for {item['material_type']}{note_part}")
        lines.append("")
        
    if state["style_dislikes"]:
        lines.append("## History of Stylistic Rejections & Dislikes")
        for item in sorted(state["style_dislikes"], key=lambda x: x.get("recorded_at") or "", reverse=True):
            capsule_part = f"`{item['capsule_id']}`" if item['capsule_id'] else "General"
            note_part = f" — *{item['note']}*" if item['note'] else ""
            lines.append(f"- **{item['recorded_at']}**: {capsule_part} for {item['material_type']}{note_part}")
        lines.append("")
        
    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

# Register with package summarization manager
register_summarizer("user", summarize_user_memory)
