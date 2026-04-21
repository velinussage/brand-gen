"""Quarterly-ish spot check of user self-consistency.

Surfaces up to 10 older items (>=30 days old) that the user previously
scored. Prompts the user to blind-rescore each (original score hidden
until after the new rating is recorded). Writes to:
    brands/<brand>/scoring/self_kappa_spot_check.jsonl

After collection, reports user κ(self, self) — the ground-truth ceiling
no scorer can beat. If self-κ < 0.5, halt any optimization: you are
chasing mood, not signal.

This is the v1 minimum — simpler than the full blind-rerate protocol
(which is v2). Enough to tell "scorer is wrong" from "user is drifting".

Usage:
    python scripts/self_kappa_spot_check.py start     # present items; collect new scores
    python scripts/self_kappa_spot_check.py status    # current self-kappa + record count

Important: the script does NOT display original scores during rescoring.
Blind re-rate depends on the user not having seen their original score
in this session. If you open the manifest file or call `bgen show <v>`
between presentation and rescoring, the blind property is broken.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import fcntl
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brand_gen.runtime import get_brand_dir, load_manifest  # noqa: E402
from brand_gen.scoring.calibration import (  # noqa: E402
    raw_agreement_rate,
    weighted_cohen_kappa,
)

MIN_AGE_DAYS = 30
MAX_ITEMS = 10
_SCORE_CHOICES = {"1", "2", "3", "4", "5"}


def _path(brand_dir: Path) -> Path:
    return brand_dir / "scoring" / "self_kappa_spot_check.jsonl"


def _candidate_versions(brand_dir: Path) -> list[tuple[str, dict]]:
    """Return versions >= MIN_AGE_DAYS old that have a prior user score."""
    manifest = load_manifest()
    versions = manifest.get("versions") or {}
    now = _dt.datetime.now()
    cutoff = now - _dt.timedelta(days=MIN_AGE_DAYS)
    already_rerated = _load_already_rerated(brand_dir)

    candidates: list[tuple[str, dict, _dt.datetime]] = []
    for vid, entry in versions.items():
        if entry.get("score") is None:
            continue
        if vid in already_rerated:
            continue
        ts_raw = str(entry.get("timestamp") or "").strip()
        if not ts_raw:
            continue
        try:
            ts = _dt.datetime.strptime(ts_raw, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            continue
        if ts > cutoff:
            continue
        candidates.append((vid, entry, ts))

    # Sort oldest first; user rescoring something from 6 months ago carries
    # more signal than rescoring last month's work.
    candidates.sort(key=lambda item: item[2])
    return [(vid, entry) for vid, entry, _ts in candidates[:MAX_ITEMS * 3]]


def _load_already_rerated(brand_dir: Path) -> set[str]:
    path = _path(brand_dir)
    if not path.exists():
        return set()
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        vid = record.get("version_id")
        if vid:
            seen.add(vid)
    return seen


def _append_record(brand_dir: Path, record: dict) -> None:
    path = _path(brand_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            handle.write(json.dumps(record, default=str) + "\n")
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _load_records(brand_dir: Path) -> list[dict]:
    path = _path(brand_dir)
    if not path.exists():
        return []
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            records.append(parsed)
    return records


def _cmd_start(args) -> int:
    brand_dir = get_brand_dir()
    pool = _candidate_versions(brand_dir)
    if not pool:
        print(f"No eligible versions found (need user score + >={MIN_AGE_DAYS} days old).")
        return 0

    random.shuffle(pool)
    picks = pool[:MAX_ITEMS]
    print(f"Blind re-rate spot check — {len(picks)} items.")
    print(f"Your original score WILL NOT be shown until after you record a new score.")
    print(f"Rate each item honestly; the goal is measuring your own consistency.")
    print()

    for i, (vid, entry) in enumerate(picks, 1):
        mat = entry.get("material_type") or "?"
        files = entry.get("files") or []
        primary = files[0] if files else "(no file)"
        print(f"[{i}/{len(picks)}]  {vid}  ({mat})")
        print(f"   file: {primary}")
        notes = (entry.get("notes") or "").strip().split("\n")[0]
        if notes:
            print(f"   original notes: {notes[:80]}")
        print(f"   Re-rate 1-5 (or 'skip', 'quit'):")
        while True:
            try:
                response = input("   > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                print("Aborted.")
                return 1
            if response == "quit":
                print("Exiting early; records written so far are saved.")
                return 0
            if response == "skip":
                print()
                break
            if response in _SCORE_CHOICES:
                new_score = int(response)
                original_score = int(entry.get("score"))
                record = {
                    "version_id": vid,
                    "material_type": mat,
                    "original_score": original_score,
                    "blind_score": new_score,
                    "delta": abs(original_score - new_score),
                    "rerate_at": _dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                    "original_timestamp": entry.get("timestamp"),
                }
                _append_record(brand_dir, record)
                # Reveal original AFTER writing the blind score
                print(f"   blind: {new_score}  original: {original_score}  delta: {record['delta']}")
                print()
                break
            print("   (please type 1, 2, 3, 4, 5, 'skip', or 'quit')")

    return _cmd_status(args)


def _cmd_status(args) -> int:
    brand_dir = get_brand_dir()
    records = _load_records(brand_dir)
    if not records:
        print("No self-rerate records yet. Run `python scripts/self_kappa_spot_check.py start` to begin.")
        return 0

    original = [int(r["original_score"]) for r in records if "original_score" in r and "blind_score" in r]
    blind = [int(r["blind_score"]) for r in records if "original_score" in r and "blind_score" in r]
    if len(original) < 2:
        print(f"{len(original)} re-rated records; need at least 2 for self-kappa.")
        return 0

    raw = raw_agreement_rate(original, blind)
    kappa = weighted_cohen_kappa(original, blind)
    payload = {
        "n_records": len(records),
        "n_valid_pairs": len(original),
        "self_raw_agreement": round(raw, 3),
        "self_weighted_kappa": round(kappa, 3),
        "dataset_path": str(_path(brand_dir)),
    }
    if getattr(args, "format", "text") == "json":
        print(json.dumps(payload, indent=2))
    else:
        print(f"Self-consistency spot check")
        print(f"  records:              {len(records)}")
        print(f"  valid score pairs:    {len(original)}")
        print(f"  raw self-agreement:   {raw:.1%}")
        print(f"  weighted self-kappa:  {kappa:.3f}")
        print()
        if kappa < 0.5:
            print("  WARNING: self-kappa < 0.5. Your own scores are drifting across the window.")
            print("  Halt any scorer optimization until ground truth is stable. If this persists,")
            print("  investigate whether the rubric definitions match how you actually score.")
        elif kappa < 0.7:
            print("  NOTE: self-kappa is moderate. Scorer cannot meaningfully exceed this.")
            print("  Treat it as the performance ceiling in bgen scoring-status dashboards.")
        else:
            print("  Self-kappa is high. You can trust optimization against this ground truth.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")
    p_start = sub.add_parser("start", help="Present 10 old items, collect blind rescores.")
    p_status = sub.add_parser("status", help="Report current self-kappa.")
    p_status.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    if args.cmd == "start":
        return _cmd_start(args)
    if args.cmd == "status":
        return _cmd_status(args)
    # default: status
    return _cmd_status(args)


if __name__ == "__main__":
    sys.exit(main())
