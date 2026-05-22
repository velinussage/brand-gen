"""Append-only state-mutation ledger.

The run ledger (`runs/<workflow_id>.jsonl`) records generation events scoped
to a single workflow. State mutations — typed verbs that modify per-brand
contract.json, custom-scratchpad.json, aesthetic-preferences, etc. — are
brand-scoped, not workflow-scoped, and they want a separate stream.

This ledger appends one record per mutation to `<brand>/mutations.jsonl`.
Each record captures: target file path, verb name, actor, before/after
content hashes, an optional human-readable diff summary, and the reason
the user gave at the CLI. Replaying the ledger reconstructs how a brand's
contract drifted across a launch cycle.

Schema parallels run_ledger but is intentionally narrower:
- `schema_type`: "state_mutation"
- `schema_version`: 1
- `timestamp`: ISO8601 local time
- `verb`: bgen verb name (e.g. "append-forbidden-pattern")
- `target_path`: absolute path to mutated file
- `actor`: who did it ("cli", "agent:claude-code", "agent:pi", etc.)
- `action`: short verb-result token ("inserted", "updated", "removed", "appended", "would_append", "duplicate")
- `before_hash`: sha256[:16] of pre-mutation file contents (empty if file did not exist)
- `after_hash`: sha256[:16] of post-mutation file contents
- `diff_summary`: optional one-line human-readable summary
- `reason`: rationale string the caller supplied
- `source_version`: optional pointer to a generation version that motivated the mutation
- `data`: free-form structured payload (verb-specific)
"""
from __future__ import annotations

import json
import time
from hashlib import sha256
from pathlib import Path
from typing import Any


def mutations_ledger_path(brand_dir: Path) -> Path:
    return Path(brand_dir).expanduser().resolve() / "mutations.jsonl"


def content_hash(path: Path | None) -> str:
    if path is None:
        return ""
    p = Path(path)
    if not p.exists():
        return ""
    try:
        return sha256(p.read_bytes()).hexdigest()[:16]
    except OSError:
        return ""


def append_mutation_event(
    brand_dir: Path,
    *,
    verb: str,
    target_path: Path | str,
    action: str,
    before_hash: str = "",
    after_hash: str = "",
    diff_summary: str = "",
    reason: str = "",
    source_version: str = "",
    actor: str = "cli",
    data: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> Path:
    record = {
        "schema_type": "state_mutation",
        "schema_version": 1,
        "timestamp": timestamp or time.strftime("%Y-%m-%dT%H:%M:%S"),
        "verb": str(verb or ""),
        "target_path": str(target_path or ""),
        "actor": str(actor or "cli"),
        "action": str(action or ""),
        "before_hash": str(before_hash or ""),
        "after_hash": str(after_hash or ""),
        "diff_summary": str(diff_summary or ""),
        "reason": str(reason or ""),
        "source_version": str(source_version or ""),
        "data": dict(data or {}),
    }
    path = mutations_ledger_path(brand_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str) + "\n")

    # PR-6: synchronous BRAND.md regen on every typed mutation (Q14).
    # JSON state stays canonical; BRAND.md is a rendered dossier.
    # Deferred import avoids any circular dependency at module load.
    try:
        from brand_gen.contract import render_brand_md

        render_brand_md(brand_dir)
    except Exception as exc:
        # Render bugs should be loud — emit a sibling marker so tests can detect.
        marker = Path(brand_dir) / ".brand-md-render-error"
        try:
            marker.write_text(f"{record['verb']}: {exc}\n", encoding="utf-8")
        except OSError:
            pass

    return path


def load_mutation_events(brand_dir: Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    path = mutations_ledger_path(brand_dir)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            events.append(parsed)
    if limit is not None and limit > 0:
        events = events[-limit:]
    return events
