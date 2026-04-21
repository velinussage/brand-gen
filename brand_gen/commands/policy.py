"""CLI handlers for Phase D policy verbs.

brand_get_policy / brand_set_policy / brand_approve_action /
brand_reject_action.
"""
from __future__ import annotations

import json

from ..runtime import get_brand_dir
from ..policy import (
    find_pending,
    load_policy_envelope,
    request_approval,
    resolve_approval,
    save_policy_envelope,
    set_policy_class,
)


def cmd_get_policy(args):
    brand_dir = get_brand_dir()
    envelope = load_policy_envelope(brand_dir)
    payload = {
        "brand_dir": str(brand_dir),
        "policy": envelope,
    }
    print(json.dumps(payload, indent=2))


def cmd_set_policy(args):
    brand_dir = get_brand_dir()
    policy_class = str(getattr(args, "policy_class", "") or "").strip()
    mode = str(getattr(args, "mode", "") or "").strip()
    if not policy_class or not mode:
        raise SystemExit("--policy-class and --mode are required")
    try:
        envelope = set_policy_class(brand_dir, policy_class=policy_class, mode=mode)
    except ValueError as exc:
        print(json.dumps({"status": "bad_request", "error": str(exc)}, indent=2))
        raise SystemExit(1)
    payload = {
        "status": "ok",
        "brand_dir": str(brand_dir),
        "policy": envelope,
    }
    print(json.dumps(payload, indent=2))


def cmd_approve_action(args):
    brand_dir = get_brand_dir()
    envelope = load_policy_envelope(brand_dir)
    pending_id = str(getattr(args, "pending_id", "") or "").strip()
    tool = str(getattr(args, "tool", "") or "").strip()
    if pending_id:
        entry = resolve_approval(
            envelope,
            pending_id=pending_id,
            decision="approved",
            reason=str(getattr(args, "reason", "") or ""),
        )
        if entry is None:
            print(json.dumps({"status": "not_found", "pending_id": pending_id}, indent=2))
            raise SystemExit(1)
        save_policy_envelope(brand_dir, envelope)
        print(json.dumps({"status": "ok", "resolved": entry}, indent=2))
        return
    # Bulk create approval: request_approval mints a pending_id and marks
    # it approved immediately (operator pre-approval of a specific tool
    # call before the autonomous worker asks).
    if not tool:
        raise SystemExit("--pending-id or --tool is required")
    pending_id = request_approval(
        envelope,
        tool=tool,
        args_summary=str(getattr(args, "args_summary", "") or ""),
        requested_by=str(getattr(args, "requested_by", "") or "operator"),
    )
    entry = resolve_approval(
        envelope,
        pending_id=pending_id,
        decision="approved",
        reason="pre-approved",
    )
    save_policy_envelope(brand_dir, envelope)
    print(json.dumps({"status": "ok", "resolved": entry}, indent=2))


def cmd_reject_action(args):
    brand_dir = get_brand_dir()
    envelope = load_policy_envelope(brand_dir)
    pending_id = str(getattr(args, "pending_id", "") or "").strip()
    if not pending_id:
        raise SystemExit("--pending-id is required")
    entry = resolve_approval(
        envelope,
        pending_id=pending_id,
        decision="rejected",
        reason=str(getattr(args, "reason", "") or ""),
    )
    if entry is None:
        print(json.dumps({"status": "not_found", "pending_id": pending_id}, indent=2))
        raise SystemExit(1)
    save_policy_envelope(brand_dir, envelope)
    print(json.dumps({"status": "ok", "resolved": entry}, indent=2))
