"""Migrate brand learnings.json material_type fields to hyphen form.

Canonical external form for material_type is HYPHEN
(`concept-illustration`, `brand-scene`, etc.). Historical learnings were
written with UNDERSCORE (`concept_illustration`, `brand_scene`) because
the internal role_pack_material_key normalizer happened to return
underscore form.

Downstream code like resolve_learned_model and validate_material_plan_dict
is tolerant of both forms, but having two conventions in one data file
is a trap for future audits. This migration rewrites any
`material_type` / `applies_to_material_types` value in any brand's
learnings.json from `a_b_c` to `a-b-c`.

Safe to re-run (idempotent): the rewrite is a no-op when all keys are
already hyphenated.

Usage (dry-run by default):
    python3 scripts/migrate_learnings_material_type_hyphens.py
    python3 scripts/migrate_learnings_material_type_hyphens.py --apply
    python3 scripts/migrate_learnings_material_type_hyphens.py --apply --brand sage
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


# Material_type strings that live in buckets we rewrite. Everything here
# gets `_` → `-` in material_type scalar fields and
# applies_to_material_types list fields. Bucket-level keys (e.g. the dict
# keyed by material under `modelPreferences_by_material`) are not
# auto-rewritten to keep the migration conservative.
_BUCKETS_TO_REWRITE = (
    "modelPreferences",
    "styleReferencePolicies",
    "failurePatterns",
    "compositionPatterns",
    "colorInsights",
    "messagingInsights",
    "audienceInsights",
)

_SCALAR_FIELDS = ("material_type",)
_LIST_FIELDS = ("applies_to_material_types",)


def _underscore_to_hyphen(value):
    if isinstance(value, str):
        return value.replace("_", "-")
    return value


def migrate_entry(entry: dict) -> tuple[dict, int]:
    """Rewrite scalar + list material-type fields in one bucket entry.

    Returns the updated entry and the number of changes applied.
    """
    changes = 0
    if not isinstance(entry, dict):
        return entry, 0
    for field in _SCALAR_FIELDS:
        if field in entry and isinstance(entry[field], str):
            new_value = _underscore_to_hyphen(entry[field])
            if new_value != entry[field]:
                entry[field] = new_value
                changes += 1
    for field in _LIST_FIELDS:
        if field in entry and isinstance(entry[field], list):
            new_list = [_underscore_to_hyphen(v) for v in entry[field]]
            if new_list != entry[field]:
                entry[field] = new_list
                changes += 1
    return entry, changes


def migrate_learnings_payload(payload: dict) -> tuple[dict, int]:
    """Rewrite every material-type field inside known buckets."""
    total_changes = 0
    if not isinstance(payload, dict):
        return payload, 0
    for bucket in _BUCKETS_TO_REWRITE:
        entries = payload.get(bucket)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            _, changes = migrate_entry(entry)
            total_changes += changes
    return payload, total_changes


def migrate_brand(brand_dir: Path, *, apply: bool) -> dict:
    """Load learnings.json for a brand, apply the migration, optionally write."""
    path = brand_dir / "learnings.json"
    if not path.exists():
        return {"brand_dir": str(brand_dir), "status": "skipped", "reason": "no learnings.json"}
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        return {"brand_dir": str(brand_dir), "status": "error", "reason": str(exc)}
    _, changes = migrate_learnings_payload(payload)
    result = {
        "brand_dir": str(brand_dir),
        "status": "ok",
        "changes": changes,
        "dry_run": not apply,
    }
    if apply and changes:
        path.write_text(json.dumps(payload, indent=2) + "\n")
        result["written"] = str(path)
    return result


def find_brand_dirs(repo_root: Path, only_brand: str | None = None) -> list[Path]:
    brands_dir = repo_root / "brands"
    if not brands_dir.exists():
        return []
    candidates = [p for p in brands_dir.iterdir() if p.is_dir()]
    if only_brand:
        candidates = [p for p in candidates if p.name == only_brand]
    return sorted(candidates)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--apply", action="store_true", help="Write changes to disk (default: dry run)")
    parser.add_argument("--brand", help="Limit migration to a single brand key")
    parser.add_argument("--repo-root", default=".", help="Repository root (default: current directory)")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    brand_dirs = find_brand_dirs(repo_root, only_brand=args.brand)
    if not brand_dirs:
        print(f"No brand directories found under {repo_root}/brands", file=sys.stderr)
        return 1

    results = [migrate_brand(bd, apply=args.apply) for bd in brand_dirs]
    total_changes = sum(r.get("changes", 0) for r in results)
    for r in results:
        status = r["status"]
        if status == "ok":
            mark = "apply" if args.apply else "would change"
            print(f"{r['brand_dir']}: {mark} {r.get('changes', 0)} entries")
        else:
            print(f"{r['brand_dir']}: {status} ({r.get('reason')})")
    if not args.apply and total_changes:
        print(f"\nDry run complete. Re-run with --apply to write {total_changes} changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
