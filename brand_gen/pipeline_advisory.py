"""Orchestrator-advisory + iteration-learning helpers.

Extracted from `pipeline_runner.py` in PR-8 to slim the runner. These helpers
are *behavior unchanged* — `PipelineRunner` now delegates to module-level
functions in this file. The methods on `PipelineRunner` remain so test
patches and `DummyRunner` overrides continue to work.

The advisory tracks whether the brand-orchestrator chain has fired its
preflight stages recently. The iteration-learning helper writes
quality-gate failures into `iteration-memory.json` so the next attempt
benefits from the prior failure context.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from brand_gen.run_ledger import append_run_event, load_all_run_events

if TYPE_CHECKING:  # pragma: no cover
    from brand_gen.runtime_models import GenerationResult


ORCHESTRATOR_PREFLIGHT_STAGES: frozenset[str] = frozenset({
    "route-request",
    "route_request",
    "plan-draft",
    "plan_draft",
    "critique-plan",
    "critique_plan",
    "inspiration-status",
    "inspiration_status",
    "export-design-tokens",
    "export_design_tokens",
    "validate-brand-fit",
    "validate_brand_fit",
})
ORCHESTRATOR_PREFLIGHT_WINDOW_SECONDS = 30 * 60  # 30 minutes


def recent_orchestrator_preflight_seen(brand_dir: Path) -> tuple[bool, list[str]]:
    """Scan the run ledger for preflight stages in the last 30 minutes.

    Returns ``(seen, stages_found)`` so callers can both decide whether
    to warn and cite the labels they saw.
    """

    try:
        events = load_all_run_events(brand_dir, limit=200)
    except Exception:
        return (False, [])
    now = _dt.datetime.now()
    cutoff = now - _dt.timedelta(seconds=ORCHESTRATOR_PREFLIGHT_WINDOW_SECONDS)
    seen: list[str] = []
    for evt in events:
        stage = str(evt.get("stage") or "").strip().lower()
        event_type = str(evt.get("event_type") or "").strip().lower()
        ts_raw = str(evt.get("timestamp") or "").strip()
        if not ts_raw:
            continue
        try:
            ts = _dt.datetime.strptime(ts_raw, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            continue
        if ts < cutoff:
            continue
        if stage in ORCHESTRATOR_PREFLIGHT_STAGES or event_type in ORCHESTRATOR_PREFLIGHT_STAGES:
            label = stage or event_type
            if label and label not in seen:
                seen.append(label)
    return (bool(seen), seen)


def emit_orchestrator_advisory(
    brand_dir: Path,
    workflow_id: str,
    plan_args: argparse.Namespace,
) -> None:
    """Warn on stderr when `bgen pipeline` runs without the orchestrator chain.

    The historic v121-v124 drift came from agents calling `bgen pipeline`
    directly without firing the brand-orchestrator preflight stages first
    (philosopher WCAG, inspiration-readiness, critic plan-level pushback).
    This advisory makes that bypass visible.
    """

    bypass = bool(getattr(plan_args, "bypass_orchestrator", False))
    reason = str(getattr(plan_args, "bypass_reason", "") or "").strip()
    seen, _found = recent_orchestrator_preflight_seen(brand_dir)
    if seen:
        return
    if bypass:
        try:
            append_run_event(
                brand_dir,
                workflow_id,
                stage="pipeline",
                event_type="orchestrator_bypass",
                status="bypass",
                notes=reason or "no reason provided",
                override_reason=reason or "",
                override_actor="bgen-pipeline-cli",
            )
        except Exception:
            pass
        return
    sys.stderr.write(
        "\n"
        "========================================================================\n"
        "[brand-gen advisory] `bgen pipeline` invoked without the orchestrator\n"
        "chain in the last 30 minutes. You are about to skip:\n"
        "  - brand-philosopher WCAG palette audit (export-design-tokens)\n"
        "  - inspiration-readiness preflight (inspiration-status)\n"
        "  - brand-critic plan-level P1 pushback (critique-plan)\n"
        "  - brand-cinematographer shot validation (for video materials)\n"
        "This is the path that produced the v121-v124 drift documented in\n"
        "skills/brand-gen/references/recipes.md.\n"
        "\n"
        "Recommended: read .claude/agents/orchestrator.md (or .pi/ variant)\n"
        "             and use the Agent tool / /run orchestrator chain.\n"
        "Scripting / CI / intentional bypass:\n"
        "             bgen pipeline --bypass-orchestrator --bypass-reason \"<one-line>\" ...\n"
        "========================================================================\n"
        "\n"
    )
    sys.stderr.flush()


def record_iteration_learning(
    brand_dir: Path,
    gen_result: "GenerationResult",
    quality: dict[str, Any],
) -> None:
    """Write a quality-gate failure into `iteration-memory.json`.

    The next generation attempt reads iteration memory during prompt assembly
    so the failure context is incorporated automatically.
    """

    try:
        from brand_gen.iteration_memory import (
            add_iteration_note,
            load_iteration_memory,
            save_iteration_memory,
        )
    except ImportError:  # pragma: no cover
        from iteration_memory import (  # type: ignore
            add_iteration_note,
            load_iteration_memory,
            save_iteration_memory,
        )

    memory = load_iteration_memory(brand_dir)
    reason = quality.get("reason", "Quality gate failure")
    note = f"Pipeline auto-retry after quality failure on {gen_result.version_id}: {reason}"
    memory = add_iteration_note(memory, note, bucket="brand_notes")

    negative_record = {
        "version": gen_result.version_id,
        "material_type": "",
        "summary": f"Quality gate failure: {reason}",
        "score": 1,
        "status": "rejected",
    }
    existing = memory.get("negative_examples", [])
    existing = [item for item in existing if item.get("version") != gen_result.version_id]
    existing.append(negative_record)
    memory["negative_examples"] = existing[-20:]

    save_iteration_memory(brand_dir, memory)
    print(f"quality_gate: recorded failure learning for {gen_result.version_id}")
