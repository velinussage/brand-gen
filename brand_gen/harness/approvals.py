"""Approval request gates and ticket serialization (sync and async)."""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal


@dataclass
class ApprovalRequest:
    """Represents a request for human approval before executing a policy-gated action."""

    ticket_id: str
    trigger_name: str
    run_id: str
    campaign_id: str
    cost_estimate: float
    description: str
    status: Literal["pending", "approved", "rejected"] = "pending"
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = time.strftime("%Y-%m-%dT%H:%M:%S")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ApprovalRequest:
        return cls(
            ticket_id=data["ticket_id"],
            trigger_name=data["trigger_name"],
            run_id=data["run_id"],
            campaign_id=data["campaign_id"],
            cost_estimate=float(data["cost_estimate"]),
            description=data["description"],
            status=data.get("status", "pending"),
            created_at=data.get("created_at", ""),
        )


def request_approval(
    brand_dir: Path,
    request: ApprovalRequest,
    mode: Literal["sync", "async"],
) -> bool:
    """Request human approval for a policy-gated action.

    Sync mode blocks the CLI execution and prompts the user on stdout.
    Async mode writes a ticket to `<brand>/approvals/pending.jsonl` and returns False.
    """
    brand_dir = Path(brand_dir).expanduser().resolve()
    approvals_dir = brand_dir / "approvals"
    approvals_dir.mkdir(parents=True, exist_ok=True)

    if mode == "sync":
        print("\n" + "=" * 60)
        print("🚨  APPROVAL REQUIRED  🚨")
        print("=" * 60)
        print(f"Action:      {request.trigger_name}")
        print(f"Campaign:    {request.campaign_id}")
        print(f"Run ID:      {request.run_id}")
        print(f"Cost Est:    ${request.cost_estimate:.2f}")
        print(f"Description: {request.description}")
        print("=" * 60)

        # In non-interactive/CI environments, check environment override
        if os.environ.get("FORCE_APPROVE") == "1":
            print("Auto-approving via FORCE_APPROVE environment variable.")
            request.status = "approved"
            _write_approval_history(approvals_dir, request)
            return True

        if not sys.stdin.isatty():
            print("Non-interactive terminal detected; sync approval rejected.")
            request.status = "rejected"
            _write_approval_history(approvals_dir, request)
            return False

        try:
            choice = input("Proceed with this action? [y/N]: ").strip().lower()
            if choice in {"y", "yes"}:
                print("Action approved. Resuming execution...")
                request.status = "approved"
                _write_approval_history(approvals_dir, request)
                return True
            else:
                print("Action rejected by user.")
                request.status = "rejected"
                _write_approval_history(approvals_dir, request)
                return False
        except (KeyboardInterrupt, EOFError):
            print("\nAction rejected (aborted).")
            request.status = "rejected"
            _write_approval_history(approvals_dir, request)
            return False

    else:  # async
        pending_file = approvals_dir / "pending.jsonl"
        with pending_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(request.to_dict()) + "\n")
        print(f"\n[ASYNC APPROVAL TICKET CREATED] Ticket ID: {request.ticket_id}")
        print(f"Write pending ticket to {pending_file.relative_to(brand_dir.parent.parent)}")
        print("Harness execution suspended. Approve using 'bgen approve' or modify approvals/pending.jsonl.")
        return False


def _write_approval_history(approvals_dir: Path, request: ApprovalRequest) -> None:
    """Log the approved/rejected request to the history ledger."""
    history_file = approvals_dir / "history.jsonl"
    with history_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(request.to_dict()) + "\n")
