"""One-off: backfill the disagreement dataset from existing manifest history.

Reads the active brand's manifest, finds every version with both an
agent-style critique score and a user feedback score, writes those as
disagreement records. Intended to run once after M3 lands so the v1
calibration dashboard has data immediately.

Agent score extraction:
- v2 packets (rubric_version present) use `overall_score` or min-biased
  aggregation over `axis_scores` (same rule as cmd_feedback).
- v1 packets (4-axis narrative rubric, no rubric_version) are SKIPPED
  because there's no clean integer score to align with user scores.
  This means backfill only captures runs where the DSPy scorer was
  already used — which in practice is "none yet" for a fresh M3 install.

Usage:
    python scripts/backfill_scoring.py [--dry-run] [--brand <name>]

The script is explicitly a script, not a CLI verb — it's a one-off
migration per the v3 plan, not a recurring operation.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brand_gen.runtime import get_brand_dir, load_manifest  # noqa: E402
from brand_gen.scoring.dataset import (  # noqa: E402
    agreement_bucket,
    append_disagreement,
    compute_partition,
    disagreement_dataset_path,
)


def _extract_agent_score(vlm_critique: dict) -> int | None:
    """Same rule as cmd_feedback._extract_agent_score."""
    if not isinstance(vlm_critique, dict) or not vlm_critique:
        return None
    if not vlm_critique.get("rubric_version"):
        # v1 packet — no clean integer; skip
        return None
    overall = vlm_critique.get("overall_score") or vlm_critique.get("agent_overall_score")
    if overall is not None:
        try:
            v = int(overall)
            if 1 <= v <= 5:
                return v
        except (TypeError, ValueError):
            return None
    axis_scores = vlm_critique.get("axis_scores") or {}
    if isinstance(axis_scores, dict) and axis_scores:
        try:
            m = min(int(v) for v in axis_scores.values())
            if 1 <= m <= 5:
                return m
        except (TypeError, ValueError):
            pass
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Report counts, do not write")
    args = parser.parse_args()

    brand_dir = get_brand_dir()
    manifest = load_manifest()
    versions = manifest.get("versions") or {}
    print(f"Scanning {len(versions)} versions in {brand_dir}")

    candidates = []
    skipped_no_agent = 0
    skipped_no_user = 0
    skipped_v1_packet = 0

    for vid, entry in versions.items():
        user_score = entry.get("score")
        if user_score is None:
            skipped_no_user += 1
            continue
        vlm = entry.get("vlm_critique") or {}
        if vlm and not vlm.get("rubric_version"):
            skipped_v1_packet += 1
            continue
        agent_score = _extract_agent_score(vlm)
        if agent_score is None:
            skipped_no_agent += 1
            continue
        candidates.append((vid, entry, agent_score, int(user_score)))

    print(f"Candidates for backfill: {len(candidates)}")
    print(f"Skipped: no_user={skipped_no_user}, no_agent_v2={skipped_no_agent}, v1_packet={skipped_v1_packet}")

    if not candidates:
        print("Nothing to backfill. Exiting.")
        return 0

    path = disagreement_dataset_path(brand_dir)
    print(f"Target dataset: {path}")
    if args.dry_run:
        print("--dry-run: no writes performed. Sample records:")
        for vid, entry, a, u in candidates[:3]:
            print(f"  {vid}: agent={a} user={u} material_type={entry.get('material_type')}")
        return 0

    for vid, entry, agent_score, user_score in candidates:
        delta = abs(agent_score - user_score)
        vlm = entry.get("vlm_critique") or {}
        record = {
            "version_id": vid,
            "material_type": entry.get("material_type") or "",
            "mode": entry.get("mode") or "",
            "model": entry.get("model") or "",
            "agent_score": agent_score,
            "user_score": user_score,
            "delta": delta,
            "agreement_bucket": agreement_bucket(delta),
            "partition_tag": compute_partition(vid),
            "user_status": entry.get("status") or "",
            "user_notes": entry.get("notes") or "",
            "rubric_version": vlm.get("rubric_version") or "",
            "scorer_version": vlm.get("scorer_version") or "",
            "vlm_provider": vlm.get("provider") or vlm.get("vlm_provider") or "",
            "backfilled_from_manifest": True,
        }
        append_disagreement(brand_dir, record)
    print(f"Wrote {len(candidates)} disagreement records.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
