#!/usr/bin/env python3
"""Audit recent run-ledger bypass paths.

Reads brand-gen run JSONL files and emits a markdown report summarizing every
event/flag that looks like a bypass.  The script is intentionally read-only for
production state; only the report path is written.
"""
from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Any


def _parse_time(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            pass
    return None


def _iter_ledger_paths(root: Path) -> list[Path]:
    candidates: list[Path] = []
    for base in [root / ".brand-gen" / "brands", root / "brands", root / ".brand-gen" / "sessions"]:
        if base.exists():
            candidates.extend(base.glob("**/runs/*.jsonl"))
    return sorted(set(path.resolve() for path in candidates))


def _load_manifest_scores(brand_root: Path) -> dict[str, Any]:
    manifest = brand_root / "manifest.json"
    if not manifest.exists():
        return {}
    try:
        payload = json.loads(manifest.read_text())
    except Exception:
        return {}
    return payload.get("versions") if isinstance(payload.get("versions"), dict) else {}


def _bypass_fields(record: dict[str, Any]) -> list[tuple[str, Any]]:
    def active(value: Any) -> bool:
        return value not in (False, None, "", [], {})

    fields: list[tuple[str, Any]] = []
    for key, value in record.items():
        if (key.startswith("bypass_") or key.startswith("bypass")) and active(value):
            fields.append((key, value))
    data = record.get("data") if isinstance(record.get("data"), dict) else {}
    for key, value in data.items():
        if (key.startswith("bypass_") or key.startswith("bypass")) and active(value):
            fields.append((f"data.{key}", value))
    policy = data.get("critique_policy") if isinstance(data.get("critique_policy"), dict) else {}
    for key, value in policy.items():
        if (key.startswith("bypass_") or key.startswith("bypass")) and active(value):
            fields.append((f"data.critique_policy.{key}", value))
    event_text = " ".join(str(record.get(k) or "") for k in ("event_type", "status", "notes", "override_reason")).lower()
    if "bypass" in event_text:
        fields.append(("event_text", event_text))
    return fields


def audit(root: Path, *, days: int) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    cutoff = datetime.now() - timedelta(days=days)
    rows: list[dict[str, Any]] = []
    versions_by_brand: dict[Path, dict[str, Any]] = {}
    for ledger in _iter_ledger_paths(root):
        # .../<brand>/runs/<workflow>.jsonl
        brand_root = ledger.parent.parent
        versions_by_brand.setdefault(brand_root, _load_manifest_scores(brand_root))
        for line_no, line in enumerate(ledger.read_text(encoding="utf-8").splitlines(), start=1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            ts = _parse_time(record.get("timestamp") or "")
            if ts and ts < cutoff:
                continue
            bypasses = _bypass_fields(record)
            if not bypasses:
                continue
            output_version = str(record.get("output_version") or record.get("attempt_id") or "")
            version_entry = versions_by_brand.get(brand_root, {}).get(output_version) or {}
            for kind, value in bypasses:
                rows.append(
                    {
                        "brand": brand_root.name,
                        "ledger": str(ledger.relative_to(root) if ledger.is_relative_to(root) else ledger),
                        "line": line_no,
                        "timestamp": record.get("timestamp") or "",
                        "workflow_id": record.get("workflow_id") or ledger.stem,
                        "version_id": output_version,
                        "bypass_kind": kind,
                        "bypass_value": value,
                        "stage": record.get("stage") or "",
                        "event_type": record.get("event_type") or "",
                        "what_bypassed": record.get("notes") or record.get("override_reason") or "",
                        "actor": record.get("override_actor") or record.get("provider") or "",
                        "downstream_score": version_entry.get("score"),
                    }
                )
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["bypass_kind"])].append(row)
    return rows, grouped


def render_report(rows: list[dict[str, Any]], grouped: dict[str, list[dict[str, Any]]], *, days: int) -> str:
    lines = [
        "# Bypass-path audit",
        "",
        f"Generated: {time.strftime('%Y-%m-%dT%H:%M:%S')}",
        f"Window: last {days} days",
        f"Bypass rows found: {len(rows)}",
        "",
        "## Summary by bypass kind",
        "",
        "| Bypass kind | Count | Mean downstream score | Example |",
        "|---|---:|---:|---|",
    ]
    if not grouped:
        lines.append("| _none found_ | 0 | n/a | No bypass-looking run-ledger rows were present in the audited window. |")
    for kind, items in sorted(grouped.items()):
        scores = [float(item["downstream_score"]) for item in items if isinstance(item.get("downstream_score"), (int, float))]
        avg = f"{mean(scores):.2f}" if scores else "n/a"
        example = items[0]
        lines.append(
            f"| `{kind}` | {len(items)} | {avg} | "
            f"{example['brand']} `{example['workflow_id']}` {example['version_id']} {example['event_type']} |"
        )
    lines += [
        "",
        "## Examples",
        "",
        "| Timestamp | Brand | Workflow | Version | Kind | Stage/event | What it bypassed | Actor | Score |",
        "|---|---|---|---|---|---|---|---|---:|",
    ]
    for row in rows[:80]:
        lines.append(
            "| {timestamp} | {brand} | `{workflow_id}` | {version_id} | `{bypass_kind}` | {stage}/{event_type} | {what_bypassed} | {actor} | {downstream_score} |".format(
                **{k: str(v).replace("|", "\\|") for k, v in row.items()}
            )
        )
    if not rows:
        lines.append("| — | — | — | — | — | — | — | — | — |")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Repository/workspace root to audit")
    parser.add_argument("--days", type=int, default=60, help="How many days of run-ledger history to include")
    parser.add_argument("--output", default="docs/audits/2026-04-28-bypass-path-audit.md", help="Markdown report path")
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()
    rows, grouped = audit(root, days=args.days)
    report = render_report(rows, grouped, days=args.days)
    output = (root / args.output).resolve() if not Path(args.output).is_absolute() else Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report)
    print(f"wrote {output} ({len(rows)} bypass rows)")


if __name__ == "__main__":
    main()
