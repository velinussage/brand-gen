from __future__ import annotations

from pathlib import Path
from typing import Any

from .runtime_brand import load_inspiration_index, load_inspirations_config
from .runtime_io import load_json_file
from .runtime_support import dedupe_keep_order


_BUCKET_KEYWORDS = {
    "composition": ["composition", "layout", "hierarchy", "framing", "spacing", "grid", "editorial"],
    "narrative_system": ["system", "campaign", "structure", "sequence", "process", "application", "reasoning", "story"],
    "rendering_style": ["palette", "typography", "finish", "texture", "restraint", "material", "surface", "whitespace"],
}


def _normalize_design_memory_path(path_value: str, brand_gen_dir: Path) -> Path:
    path = Path(str(path_value or "")).expanduser()
    if not path.is_absolute():
        path = (brand_gen_dir / path).resolve()
    return path


def derive_bucket_hints(record: dict[str, Any]) -> list[str]:
    haystack_parts = [
        " ".join(str(item) for item in (record.get("best_for") or [])),
        " ".join(str(item) for item in (record.get("tags") or [])),
        " ".join(str(item) for item in (record.get("borrow_mechanics") or [])),
        " ".join(str(item) for item in (record.get("layout_cues") or [])),
        " ".join(str(item) for item in (record.get("palette_lines") or [])),
        " ".join(str(item) for item in (record.get("typography_lines") or [])),
    ]
    haystack = " ".join(part.lower() for part in haystack_parts if part)
    buckets: list[str] = []
    for bucket, keywords in _BUCKET_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            buckets.append(bucket)
    if not buckets:
        buckets = ["composition", "rendering_style"]
    if "composition" in buckets and "narrative_system" not in buckets and any(term in haystack for term in ["editorial", "campaign", "application"]):
        buckets.append("narrative_system")
    return dedupe_keep_order(buckets)


def _load_source_summary(design_memory_path: Path) -> dict[str, Any]:
    summary_path = design_memory_path / "source-summary.json"
    payload = load_json_file(summary_path)
    return payload if isinstance(payload, dict) else {}


def enrich_source_record(base_record: dict[str, Any]) -> dict[str, Any]:
    record = dict(base_record or {})
    design_memory_path = Path(str(record.get("design_memory_path") or "")).expanduser().resolve()
    summary = _load_source_summary(design_memory_path)
    source = summary.get("source") if isinstance(summary.get("source"), dict) else {}
    analysis = summary.get("analysis") if isinstance(summary.get("analysis"), dict) else {}
    record["notes"] = str(record.get("notes") or source.get("notes") or "")
    record["tags"] = list(record.get("tags") or source.get("tags") or [])
    record["borrow_mechanics"] = list(record.get("borrow_mechanics") or source.get("borrow_mechanics") or [])
    record["avoid_literal"] = list(record.get("avoid_literal") or source.get("avoid_literal") or [])
    record["best_for"] = list(record.get("best_for") or source.get("best_for") or [])
    record["direct_generation_risk"] = str(record.get("direct_generation_risk") or source.get("direct_generation_risk") or "medium")
    record["summary_doctrine"] = list(analysis.get("doctrine") or [])
    record["layout_cues"] = list(analysis.get("layout_cues") or [])
    record["palette_lines"] = list(analysis.get("palette_lines") or [])
    record["typography_lines"] = list(analysis.get("typography_lines") or [])
    record["motion_cues"] = list(analysis.get("motion_cues") or [])
    record["bucket_hints"] = derive_bucket_hints(record)
    if not record.get("summary"):
        summary_bits = list(record.get("borrow_mechanics") or [])[:2] or list(record.get("layout_cues") or [])[:1]
        record["summary"] = f"{record.get('source_name') or record.get('source_key')}: {'; '.join(summary_bits) if summary_bits else 'translated mechanics only'}"
    return record


def load_configured_source_records(
    *,
    brand_dir: Path,
    brand_gen_dir: Path,
    active_brand: str,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    config = load_inspirations_config(active_brand, brand_gen_dir)
    index = load_inspiration_index(brand_gen_dir).get("sources", {})
    source_records: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for key in config.get("sources", []):
        item = index.get(key)
        if not item:
            skipped.append({"source": key, "reason": "not indexed"})
            continue
        status = item.get("status")
        if status != "complete":
            skipped.append({"source": key, "reason": f"status={status or 'unknown'}"})
            continue
        design_path_value = item.get("designMemoryPath")
        if not design_path_value:
            skipped.append({"source": key, "reason": "missing designMemoryPath"})
            continue
        design_path = _normalize_design_memory_path(str(design_path_value), brand_gen_dir)
        if not design_path.exists():
            skipped.append({"source": key, "reason": "design memory path missing"})
            continue
        source_records.append(
            enrich_source_record(
                {
                    "source_key": key,
                    "source_name": str(item.get("name") or key),
                    "source_url": str(item.get("url") or item.get("sourceUrl") or ""),
                    "design_memory_path": str(design_path),
                    "selection_mode": "configured_inspiration",
                }
            )
        )
    return source_records, skipped
