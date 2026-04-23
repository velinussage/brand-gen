"""Phase D: Policy surface for the typed canonical runtime.

Design (policy-tag-first, approval-envelope opt-in):

1. Every canonical tool has a policy_class attached in
   packages/brand-gen-core/src/tool-registry.ts and mirrored in
   POLICY_CLASSES_BY_TOOL below. One of:

   - ``read_only``          — inspection tools; always allowed.
   - ``local_mutation``     — writes brand-gen state (scratchpad, palette,
                              learnings, plans, critiques). Always allowed
                              by default; configurable per-brand.
   - ``costly_generation``  — invokes a paid image/video model
                              (execute_run, orchestrate_material). Allowed
                              by default; hosts (especially OpenClaw)
                              flip this to ``require_approval`` for
                              autonomous workflows.
   - ``publish_external``   — reserved for tools that push work outside
                              the local workspace (social posting, etc.).
                              Denied by default.

2. Per-brand envelope stored at ``<brand_dir>/.policy.json``:

   ```json
   {
     "version": 1,
     "updated_at": "...",
     "classes": {
       "read_only":         {"mode": "allow"},
       "local_mutation":    {"mode": "allow"},
       "costly_generation": {"mode": "allow"},
       "publish_external":  {"mode": "deny"}
     },
     "pending_approvals": [
       {"pending_id": "...", "tool": "...", "policy_class": "...",
        "args_summary": "...", "requested_at": "...",
        "requested_by": "...", "decision": "pending"}
     ],
     "recent_decisions":   [ ... ]
   }
   ```

3. ``check_policy_for_tool(envelope, tool_name)`` returns
   {"decision": "allow" | "require_approval" | "deny", "class": "..."}.

4. ``request_approval(envelope, tool, args)`` appends a pending_approval
   entry, returns the new pending_id.

5. ``resolve_approval(envelope, pending_id, decision)`` flips a pending
   entry to ``approved`` or ``rejected`` and drains it to
   ``recent_decisions``.

Hosts that want to enforce the envelope (OpenClaw for autonomous loops)
call ``check_policy_for_tool`` before dispatching, and treat
``require_approval`` as "queue a pending_approval, wait".
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Literal


PolicyClass = Literal["read_only", "local_mutation", "costly_generation", "publish_external"]
PolicyMode = Literal["allow", "require_approval", "deny"]


# Single source of truth for tool → policy class. Keep in sync with the
# policy_class field in packages/brand-gen-core/src/tool-registry.ts.
POLICY_CLASSES_BY_TOOL: dict[str, PolicyClass] = {
    # Orchestration — stage transitions.
    "brand_prepare_run":           "local_mutation",
    "brand_plan_run":              "local_mutation",
    "brand_validate_run":          "local_mutation",
    "brand_execute_run":           "costly_generation",
    "brand_review_run":            "local_mutation",
    "brand_evolve_run":            "local_mutation",
    "brand_orchestrate_material":  "costly_generation",
    "brand_build_generation_scratchpad": "local_mutation",
    # Mutation — typed state changes.
    "brand_append_forbidden_pattern":      "local_mutation",
    "brand_append_custom_scratchpad_note": "local_mutation",
    "brand_promote_learning":              "local_mutation",
    "brand_promote_style_policy":          "local_mutation",
    "brand_set_motion_grammar":            "local_mutation",
    "brand_update_palette":                "local_mutation",
    "brand_update_typography":             "local_mutation",
    "brand_update_devices":                "local_mutation",
    "brand_export_design_tokens":          "local_mutation",
    "brand_extract_inspiration":           "local_mutation",
    "brand_consolidate_inspiration":       "local_mutation",
    "brand_submit_review":                 "local_mutation",
    "brand_switch_brand":                  "local_mutation",
    # Inspection — read-only.
    "brand_context_snapshot":        "read_only",
    "brand_show_blackboard":         "read_only",
    "brand_show_iteration_memory":   "read_only",
    "brand_show_rubric":             "read_only",
    "brand_show_disagreements":      "read_only",
    "brand_scoring_status":          "read_only",
    "brand_capabilities":            "read_only",
    "brand_list_runs":               "read_only",
    "brand_get_run":                 "read_only",
    "brand_get_plan":                "read_only",
    "brand_get_critique":            "read_only",
    "brand_get_scratchpad":          "read_only",
    "brand_get_review_packet":       "read_only",
    "brand_get_version":             "read_only",
    "brand_compare_versions":        "read_only",
    "brand_list_brands":             "read_only",
    "brand_get_pending_reviews":     "read_only",
    # Feedback — user/agent scoring hook.
    "brand_feedback":         "local_mutation",
    "brand_critique_rubric":  "read_only",
}


_DEFAULT_POLICY = {
    "version": 1,
    "classes": {
        "read_only":         {"mode": "allow"},
        "local_mutation":    {"mode": "allow"},
        "costly_generation": {"mode": "allow"},
        "publish_external":  {"mode": "deny"},
    },
    "pending_approvals": [],
    "recent_decisions": [],
}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def policy_path(brand_dir: Path) -> Path:
    return Path(brand_dir).expanduser().resolve() / ".policy.json"


def load_policy_envelope(brand_dir: Path) -> dict[str, Any]:
    """Load the per-brand policy envelope, falling back to defaults."""
    path = policy_path(brand_dir)
    if not path.exists():
        envelope = json.loads(json.dumps(_DEFAULT_POLICY))  # deep copy
        envelope["updated_at"] = ""
        return envelope
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        envelope = json.loads(json.dumps(_DEFAULT_POLICY))
        envelope["updated_at"] = ""
        return envelope
    # Normalize: add any missing default keys without overwriting user values.
    defaults = _DEFAULT_POLICY
    for key, default_value in defaults.items():
        envelope.setdefault(key, json.loads(json.dumps(default_value)))
    classes = envelope.setdefault("classes", {})
    for cls, default_cls in defaults["classes"].items():
        classes.setdefault(cls, json.loads(json.dumps(default_cls)))
    envelope.setdefault("pending_approvals", [])
    envelope.setdefault("recent_decisions", [])
    return envelope


def save_policy_envelope(brand_dir: Path, envelope: dict[str, Any]) -> Path:
    envelope["updated_at"] = _now()
    path = policy_path(brand_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(envelope, indent=2) + "\n", encoding="utf-8")
    return path


def set_policy_class(
    brand_dir: Path,
    *,
    policy_class: PolicyClass,
    mode: PolicyMode,
) -> dict[str, Any]:
    envelope = load_policy_envelope(brand_dir)
    classes = envelope["classes"]
    if policy_class not in classes:
        raise ValueError(f"unknown policy class: {policy_class}")
    if mode not in ("allow", "require_approval", "deny"):
        raise ValueError(f"unknown mode: {mode}")
    classes[policy_class]["mode"] = mode
    save_policy_envelope(brand_dir, envelope)
    return envelope


def policy_class_for_tool(tool_name: str) -> PolicyClass:
    cls = POLICY_CLASSES_BY_TOOL.get(tool_name)
    if cls is None:
        # Unknown tool — default conservative: deny publishes, allow reads.
        # Anything not registered is treated as local_mutation (safest
        # non-broken default for legacy CLI bridges).
        return "local_mutation"
    return cls


def check_policy_for_tool(envelope: dict[str, Any], tool_name: str) -> dict[str, Any]:
    """Return {decision, class} where decision ∈ {allow, require_approval, deny}."""
    cls = policy_class_for_tool(tool_name)
    classes = (envelope or {}).get("classes") or {}
    mode = (classes.get(cls) or {}).get("mode") or "allow"
    return {"decision": mode, "class": cls, "tool": tool_name}


def request_approval(
    envelope: dict[str, Any],
    *,
    tool: str,
    args_summary: str = "",
    requested_by: str = "",
) -> str:
    """Append a pending_approval entry, return pending_id."""
    pending_id = uuid.uuid4().hex[:12]
    cls = policy_class_for_tool(tool)
    entry = {
        "pending_id": pending_id,
        "tool": tool,
        "policy_class": cls,
        "args_summary": args_summary[:500],
        "requested_at": _now(),
        "requested_by": requested_by or "",
        "decision": "pending",
    }
    envelope.setdefault("pending_approvals", []).append(entry)
    return pending_id


def resolve_approval(
    envelope: dict[str, Any],
    *,
    pending_id: str,
    decision: Literal["approved", "rejected"],
    reason: str = "",
) -> dict[str, Any] | None:
    """Flip a pending approval to approved/rejected + move to recent_decisions."""
    pending = envelope.setdefault("pending_approvals", [])
    for idx, entry in enumerate(pending):
        if entry.get("pending_id") == pending_id:
            entry["decision"] = decision
            entry["resolved_at"] = _now()
            if reason:
                entry["reason"] = reason[:500]
            envelope.setdefault("recent_decisions", []).insert(0, entry)
            # Keep only the last 50 decisions.
            envelope["recent_decisions"] = envelope["recent_decisions"][:50]
            del pending[idx]
            return entry
    return None


def find_pending(envelope: dict[str, Any], pending_id: str) -> dict[str, Any] | None:
    for entry in envelope.get("pending_approvals") or []:
        if entry.get("pending_id") == pending_id:
            return entry
    return None
