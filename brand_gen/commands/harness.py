"""CLI command handlers for the campaign control plane event/run harness."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from brand_gen.runtime import get_brand_dir
from brand_gen.harness.run import BrandRun, RunRegistry


def cmd_run_list(args):
    """List campaign runs using the RunRegistry index layer."""
    brand_dir = get_brand_dir()
    runs = RunRegistry.list_runs(brand_dir)

    status_filter = getattr(args, "status", None) or None
    material_filter = getattr(args, "material_type", None) or None
    limit = getattr(args, "limit", None)

    # Filter
    filtered_runs = []
    for run in runs:
        if status_filter and run.get("status") != status_filter:
            continue
        if material_filter and run.get("material_type") != material_filter:
            continue
        filtered_runs.append(run)

    # Sort by timestamp newest first (in index, entries are sorted oldest first, so we reverse it)
    filtered_runs.sort(key=lambda x: x.get("timestamp") or "", reverse=True)

    if isinstance(limit, int) and limit > 0:
        filtered_runs = filtered_runs[:limit]

    payload = {
        "brand_dir": str(brand_dir),
        "count": len(filtered_runs),
        "filter": {
            "status": status_filter,
            "material_type": material_filter,
            "limit": limit if isinstance(limit, int) and limit > 0 else None,
        },
        "runs": filtered_runs,
    }

    if getattr(args, "format", "json") == "json":
        print(json.dumps(payload, indent=2))
        return

    if not filtered_runs:
        print("No campaign runs found.")
        return

    # Print pretty columns matching the table layout
    print(f"{'RUN_ID':<38} {'CAMPAIGN_ID':<38} {'STATUS':<16} {'MATERIAL':<20} {'TIMESTAMP':<20} {'EVENTS':>6} {'COST':>6}")
    print("-" * 150)
    for r in filtered_runs:
        print(
            f"{r.get('run_id', '—'):<38} {r.get('campaign_id', '—'):<38} "
            f"{r.get('status', '—'):<16} {r.get('material_type', '—'):<20} "
            f"{r.get('timestamp', '—'):<20} {r.get('event_count', 0):>6} "
            f"${r.get('cost', 0.0):>5.2f}"
        )


def cmd_run_show(args):
    """Show details of a single campaign run."""
    brand_dir = get_brand_dir()
    workflow_id = str(getattr(args, "run_id", "") or "").strip()
    if not workflow_id:
        raise SystemExit("run-show requires --run-id")

    # In case they passed the deterministic uuid run_id, let's resolve it.
    runs = RunRegistry.list_runs(brand_dir)
    target_workflow_id = workflow_id
    for run_entry in runs:
        if run_entry.get("run_id") == workflow_id or run_entry.get("workflow_id") == workflow_id:
            target_workflow_id = run_entry.get("workflow_id")
            break

    run = BrandRun.load(brand_dir, target_workflow_id)
    if not run.events:
        payload = {
            "status": "not_found",
            "run_id": workflow_id,
            "brand_dir": str(brand_dir),
        }
        print(json.dumps(payload, indent=2))
        return

    summary = run.replay()
    payload = {
        "status": "ok",
        "brand_dir": str(brand_dir),
        "run_id": run.run_id,
        "campaign_id": run.campaign_id,
        "workflow_id": run.workflow_id,
        "summary": summary,
        "events": [e.to_dict() for e in run.events],
    }

    if getattr(args, "format", "json") == "json":
        print(json.dumps(payload, indent=2))
        return

    # Text format
    print(f"Run {run.run_id}")
    print(f"  Campaign ID:   {run.campaign_id or '—'}")
    print(f"  Workflow ID:   {run.workflow_id or '—'}")
    print(f"  Created At:    {summary.get('created_at', '—')}")
    print(f"  Last Updated:  {summary.get('last_updated_at', '—')}")
    print(f"  Status:        {summary.get('status', '—')}")
    print(f"  Current Stage: {summary.get('stage', '—')}")
    print(f"  Material Type: {summary.get('material_type', '—')}")
    print(f"  Total Cost:    ${summary.get('cost', 0.0):.2f}")
    print(f"  Events Count:  {summary.get('event_count', 0)}")
    
    if summary.get("warnings"):
        print("  Warnings:")
        for warning in summary["warnings"]:
            print(f"    - {warning}")

    print("\nEvent Ledger Timeline:")
    print(f"  {'TIMESTAMP':<20} {'STAGE':<18} {'EVENT_TYPE':<22} {'STATUS':<12} {'COST':>6}")
    print("  " + "-" * 85)
    for e in sorted(run.events, key=lambda x: x.timestamp):
        cost_str = f"${e.cost:.2f}" if e.cost is not None else "—"
        print(
            f"  {e.timestamp:<20} {e.stage:<18} "
            f"{e.event_type:<22} {e.status:<12} {cost_str:>6}"
        )


def cmd_run_replay(args):
    """Reconstruct/replay the campaign's event sequence and show accumulated state."""
    brand_dir = get_brand_dir()
    workflow_id = str(getattr(args, "run_id", "") or "").strip()
    if not workflow_id:
        raise SystemExit("run-replay requires --run-id")

    runs = RunRegistry.list_runs(brand_dir)
    target_workflow_id = workflow_id
    for run_entry in runs:
        if run_entry.get("run_id") == workflow_id or run_entry.get("workflow_id") == workflow_id:
            target_workflow_id = run_entry.get("workflow_id")
            break

    run = BrandRun.load(brand_dir, target_workflow_id)
    if not run.events:
        payload = {
            "status": "not_found",
            "run_id": workflow_id,
            "brand_dir": str(brand_dir),
        }
        print(json.dumps(payload, indent=2))
        return

    # Sort events by timestamp
    sorted_events = sorted(run.events, key=lambda e: e.timestamp)
    steps = []
    
    accumulated_cost = 0.0
    stages_seen = []
    warnings = []
    
    for idx, event in enumerate(sorted_events, start=1):
        if event.cost is not None:
            accumulated_cost += float(event.cost)
        if event.stage and event.stage not in stages_seen:
            stages_seen.append(event.stage)
        if event.warnings:
            for w in event.warnings:
                if w and w not in warnings:
                    warnings.append(w)
                    
        steps.append({
            "step": idx,
            "timestamp": event.timestamp,
            "stage": event.stage,
            "event_type": event.event_type,
            "status": event.status,
            "cost_delta": event.cost,
            "accumulated_cost": accumulated_cost,
            "stages_completed": list(stages_seen),
            "warnings_count": len(warnings),
        })

    payload = {
        "run_id": run.run_id,
        "campaign_id": run.campaign_id,
        "workflow_id": run.workflow_id,
        "brand_dir": str(brand_dir),
        "steps": steps,
        "final_state": run.replay()
    }

    if getattr(args, "format", "json") == "json":
        print(json.dumps(payload, indent=2))
        return

    print(f"Replaying Campaign Run: {run.run_id}")
    print(f"Workflow ID: {run.workflow_id} | Campaign ID: {run.campaign_id}")
    print("-" * 80)
    for step in steps:
        cost_delta_str = f"+${step['cost_delta']:.2f}" if step['cost_delta'] is not None else "+$0.00"
        print(
            f"Step {step['step']}: [{step['timestamp']}] {step['stage']} -> {step['event_type']} "
            f"({step['status'] or 'unknown'})"
        )
        print(f"  Cost Delta: {cost_delta_str:<12} | Accumulated Cost: ${step['accumulated_cost']:.2f}")
        print(f"  Completed Stages: {', '.join(step['stages_completed'])}")
        print(f"  Warnings: {step['warnings_count']}")
        print("-" * 80)


def cmd_rebuild_run_index(args):
    """Rebuild the runs/_index.jsonl index from raw run event files."""
    brand_dir = get_brand_dir()
    entries = RunRegistry.rebuild_index(brand_dir)
    payload = {
        "status": "ok",
        "brand_dir": str(brand_dir),
        "entries_count": len(entries),
    }
    if getattr(args, "format", "json") == "json":
        print(json.dumps(payload, indent=2))
        return
    print(f"Successfully rebuilt runs index for brand {brand_dir.name}.")
    print(f"Indexed {len(entries)} campaign runs in runs/_index.jsonl.")
