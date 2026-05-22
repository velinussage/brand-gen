from __future__ import annotations

from pathlib import Path
from typing import Any

from brand_gen.memory import (
    append_event_to_ledger,
    read_ledger_events,
    get_markdown_path,
    register_summarizer,
)

def project_campaign_memory(brand_dir: Path) -> dict[str, Any]:
    """Projects campaign events ledger into a structured campaign registry."""
    events = read_ledger_events(brand_dir, "campaign")
    
    campaigns = {}
    branches = {}
    
    for event in events:
        payload = event.get("payload") or {}
        etype = event.get("event_type")
        timestamp = event.get("timestamp")
        
        if etype == "campaign_started":
            cid = payload.get("campaign_id")
            wid = payload.get("workflow_id")
            mtype = payload.get("material_type")
            if not cid:
                continue
                
            campaigns.setdefault(cid, {
                "campaign_id": cid,
                "workflow_ids": [],
                "material_type": mtype,
                "status": "in-progress",
                "started_at": timestamp,
                "ended_at": None,
                "details": dict(payload.get("details") or {}),
                "locked_version": None,
            })
            if wid and wid not in campaigns[cid]["workflow_ids"]:
                campaigns[cid]["workflow_ids"].append(wid)
                
        elif etype == "campaign_ended":
            cid = payload.get("campaign_id")
            status = payload.get("status")
            if cid in campaigns:
                campaigns[cid]["status"] = status or "completed"
                campaigns[cid]["ended_at"] = timestamp
                
        elif etype == "branch_created":
            bid = payload.get("branch_id")
            pbid = payload.get("parent_branch_id")
            if bid:
                branches[bid] = {
                    "branch_id": bid,
                    "parent_branch_id": pbid or None,
                    "status": "active",
                    "reason": None,
                    "created_at": timestamp,
                }
                
        elif etype == "branch_abandoned":
            bid = payload.get("branch_id")
            reason = payload.get("reason")
            if bid in branches:
                branches[bid]["status"] = "abandoned"
                branches[bid]["reason"] = reason
            elif bid:
                branches[bid] = {
                    "branch_id": bid,
                    "parent_branch_id": None,
                    "status": "abandoned",
                    "reason": reason,
                    "created_at": timestamp,
                }
                
        elif etype == "branch_locked":
            bid = payload.get("branch_id")
            vid = payload.get("version_id")
            if bid in branches:
                branches[bid]["status"] = "locked"
                branches[bid]["locked_version"] = vid
            for cid, camp in campaigns.items():
                if bid in camp["workflow_ids"]:
                    camp["status"] = "succeeded"
                    camp["locked_version"] = vid
                    
    return {
        "campaigns": campaigns,
        "branches": branches,
    }

def summarize_campaign_memory(brand_dir: Path) -> None:
    """Renders the projected campaign history into a derived markdown file."""
    state = project_campaign_memory(brand_dir)
    md_path = get_markdown_path(brand_dir, "campaign")
    
    lines = [
        "# Campaign History Dossier",
        "",
        "> [!NOTE]",
        "> This is a derived markdown file generated from the canonical append-only campaign event ledger.",
        "",
    ]
    
    camps = state["campaigns"]
    active_camps = [c for c in camps.values() if c["status"] == "in-progress"]
    past_camps = [c for c in camps.values() if c["status"] != "in-progress"]
    
    if active_camps:
        lines.append("## Active Campaign Sessions")
        for c in active_camps:
            lines.append(f"### Campaign `{c['campaign_id']}` ({c['material_type']})")
            lines.append(f"- **Started at**: {c['started_at']}")
            lines.append(f"- **Active Branches/Workflows**: {', '.join(c['workflow_ids'])}")
            if c['details']:
                lines.append("- **Details**:")
                for k, v in c['details'].items():
                    lines.append(f"  - *{k}*: {v}")
            lines.append("")
            
    if past_camps:
        lines.append("## Past / Completed Campaigns")
        for c in sorted(past_camps, key=lambda x: x.get("started_at") or "", reverse=True):
            status_badge = "✅ succeeded" if c["status"] == "succeeded" else f"❌ {c['status']}"
            lines.append(f"### Campaign `{c['campaign_id']}` ({c['material_type']}) — {status_badge}")
            lines.append(f"- **Started at**: {c['started_at']}")
            lines.append(f"- **Ended at**: {c['ended_at']}")
            if c['locked_version']:
                lines.append(f"- **Locked Version**: `{c['locked_version']}`")
            lines.append("")
            
    branches = state["branches"]
    if branches:
        lines.append("## Exploration Branches & Lifetimes")
        for b in sorted(branches.values(), key=lambda x: x.get("created_at") or "", reverse=True):
            parent = f" (parent: `{b['parent_branch_id']}`)" if b['parent_branch_id'] else ""
            lines.append(f"### Branch `{b['branch_id']}`{parent}")
            lines.append(f"- **Status**: `{b['status']}`")
            lines.append(f"- **Created at**: {b['created_at']}")
            if b['reason']:
                lines.append(f"- **Reason/Notes**: {b['reason']}")
            if b.get("locked_version"):
                lines.append(f"- **Locked version ID**: `{b['locked_version']}`")
            lines.append("")
            
    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

# Register with package summarization manager
register_summarizer("campaign", summarize_campaign_memory)
