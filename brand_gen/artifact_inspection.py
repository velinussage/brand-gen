"""Phase B: typed artifact inspection over brand-gen scratchpads and reviews.

Agents shouldn't have to know the on-disk layout of plan drafts, critiques,
scratchpads, or review packets. These helpers accept either a direct path
or a (run_id, schema_type) tuple and return the typed JSON payload ready
for a CLI to print.

The caller can also pass ``run_id`` alone; the helper picks the most recent
artifact of the requested kind for that run.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .runtime_brand import (
    collect_workflow_artifacts,
    iter_workflow_artifact_paths,
    load_json_file,
    resolve_workflow_id,
)


_ARTIFACT_BUCKET_BY_KIND = {
    "plan": "plan_drafts",
    "critique": "plan_critiques",
    "scratchpad": "generation_scratchpads",
}


def _resolve_artifact_entry(
    brand_dir: Path,
    *,
    kind: str,
    run_id: str | None,
    path: str | None,
) -> dict[str, Any]:
    """Return a dict containing `payload`, `path`, and `status`.

    kind ∈ {"plan", "critique", "scratchpad"}.
    If path is provided and exists, that wins. Otherwise scan for the
    most recent artifact of the requested kind matching run_id.
    """
    if path:
        resolved = Path(path).expanduser().resolve()
        if not resolved.exists():
            return {"status": "not_found", "path": str(resolved), "payload": None}
        payload = load_json_file(resolved)
        return {"status": "ok", "path": str(resolved), "payload": payload}

    if not run_id:
        return {"status": "bad_request", "error": "run_id or path is required", "payload": None}

    bucket = _ARTIFACT_BUCKET_BY_KIND.get(kind)
    if not bucket:
        return {"status": "bad_request", "error": f"unknown kind: {kind}", "payload": None}

    grouped = collect_workflow_artifacts(brand_dir, run_id)
    entries = grouped.get(bucket) or []
    if not entries:
        return {
            "status": "not_found",
            "run_id": run_id,
            "kind": kind,
            "payload": None,
        }
    # Most recent by mtime (collect returns insertion order; mtime-sort to
    # pick the freshest).
    entries.sort(key=lambda item: Path(item["path"]).stat().st_mtime, reverse=True)
    chosen = entries[0]
    resolved = Path(chosen["path"]).expanduser().resolve()
    payload = load_json_file(resolved)
    return {"status": "ok", "path": str(resolved), "payload": payload}


def fetch_plan(brand_dir: Path, *, run_id: str | None = None, path: str | None = None) -> dict[str, Any]:
    return _resolve_artifact_entry(brand_dir, kind="plan", run_id=run_id, path=path)


def fetch_critique(brand_dir: Path, *, run_id: str | None = None, path: str | None = None) -> dict[str, Any]:
    return _resolve_artifact_entry(brand_dir, kind="critique", run_id=run_id, path=path)


def fetch_scratchpad(brand_dir: Path, *, run_id: str | None = None, path: str | None = None) -> dict[str, Any]:
    return _resolve_artifact_entry(brand_dir, kind="scratchpad", run_id=run_id, path=path)


def fetch_review_packet(brand_dir: Path, *, version_id: str) -> dict[str, Any]:
    """Fetch the agent review packet for a generated version.

    Prefers agent-review.json (structured DSPy output) when present; falls
    back to auto-review.json. Returns typed payload + path.
    """
    version_id = str(version_id or "").strip()
    if not version_id:
        return {"status": "bad_request", "error": "version_id required", "payload": None}
    reviews_dir = brand_dir / "reviews"
    candidates = [
        reviews_dir / f"{version_id}-agent-review.json",
        reviews_dir / f"{version_id}-auto-review.json",
        reviews_dir / f"{version_id}.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            payload = load_json_file(candidate)
            return {
                "status": "ok",
                "version_id": version_id,
                "path": str(candidate),
                "packet_kind": candidate.name.replace(f"{version_id}-", "").replace(".json", "") or "review",
                "payload": payload,
            }
    return {
        "status": "not_found",
        "version_id": version_id,
        "reviews_dir": str(reviews_dir),
        "payload": None,
    }


def fetch_version(brand_dir: Path, *, version_id: str, manifest: dict | None = None) -> dict[str, Any]:
    """Return the manifest entry + on-disk file paths for a version."""
    version_id = str(version_id or "").strip()
    if not version_id:
        return {"status": "bad_request", "error": "version_id required", "payload": None}
    if manifest is None:
        from .runtime import load_manifest  # lazy to avoid circular import at module load

        manifest = load_manifest()
    versions = (manifest or {}).get("versions") or {}
    entry = versions.get(version_id)
    if not entry:
        return {"status": "not_found", "version_id": version_id, "payload": None}
    files = entry.get("files") or []
    existing_files = [f for f in files if Path(f).exists()]
    return {
        "status": "ok",
        "version_id": version_id,
        "entry": entry,
        "files": files,
        "existing_files": existing_files,
        "payload": entry,
    }


def _simple_dict_diff(a: dict | None, b: dict | None, *, keys: list[str]) -> dict[str, Any]:
    a = a or {}
    b = b or {}
    diff: dict[str, Any] = {}
    for key in keys:
        if a.get(key) != b.get(key):
            diff[key] = {"a": a.get(key), "b": b.get(key)}
    return diff


def compare_versions(
    brand_dir: Path,
    *,
    version_a: str,
    version_b: str,
    manifest: dict | None = None,
) -> dict[str, Any]:
    """Side-by-side summary of two versions' manifest entries."""
    a = fetch_version(brand_dir, version_id=version_a, manifest=manifest)
    b = fetch_version(brand_dir, version_id=version_b, manifest=manifest)
    if a.get("status") != "ok" or b.get("status") != "ok":
        return {
            "status": "missing",
            "a": a,
            "b": b,
        }
    diff_keys = [
        "material_type",
        "mode",
        "model",
        "score",
        "status",
        "generation_mode",
        "reference_count",
        "prompt_char_count",
        "tag",
    ]
    return {
        "status": "ok",
        "a": {"version": version_a, "entry": a["entry"], "files": a.get("files") or []},
        "b": {"version": version_b, "entry": b["entry"], "files": b.get("files") or []},
        "diff": _simple_dict_diff(a.get("entry"), b.get("entry"), keys=diff_keys),
    }
