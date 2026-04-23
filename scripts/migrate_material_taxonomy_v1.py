"""Migrate saved plans, sets, scratchpads, and manifest entries to taxonomy v1.

Rewrites deprecated material types toward the newer SaaS-oriented taxonomy:
- brand-scene -> illustrated-brand-world
- campaign-poster -> proof-poster
- pattern-system -> site-pattern-tile (or pattern-board for board-like briefs)
- concept-illustration -> system-explainer-illustration (or editorial-metaphor-illustration for metaphor-led briefs)

Safe to re-run (idempotent).

Usage (dry-run by default):
    python3 scripts/migrate_material_taxonomy_v1.py --brand-dir brands/sage
    python3 scripts/migrate_material_taxonomy_v1.py --brand-dir brands/sage --apply
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from brand_gen.material_taxonomy_migration import migrate_workspace


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--brand-dir", required=True, help="Brand workspace root to migrate")
    parser.add_argument("--apply", action="store_true", help="Write updates to disk (default: dry run)")
    args = parser.parse_args()

    result = migrate_workspace(Path(args.brand_dir), apply=args.apply)
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") in {"ok", "partial"} else 1


if __name__ == "__main__":
    sys.exit(main())
