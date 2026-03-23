from __future__ import annotations

import json
import os
import re
import uuid
import fcntl
from functools import partial
from pathlib import Path

from .brand_scaffold import load_brand_registry
from .runtime_io import atomic_json_write, load_json_file, slugify, warn
from .runtime_paths import (
    ALIGNMENT_QUESTIONS_PATH,
    IDEA_TRACKS_PATH,
    MATERIAL_POLICY_PATH,
    MATERIAL_SNIPPETS_PATH,
    PIPELINE_CONFIG_PATH,
    PROMPT_BUDGET_PATH,
    PROMPT_FRAGMENTS_PATH,
    PROMPT_REVIEW_RULES_PATH,
    REFERENCE_ROLE_PACKS_PATH,
    REPO_ROOT,
    SYSTEM_PROMPTS_DIR,
    WORKFLOW_ROUTER_RULES_PATH,
)
from .session import (
    DEFAULT_BRAND_GEN_CONFIG,
    brand_gen_config_path as _brand_gen_config_path,
    explicit_legacy_brand_override as _explicit_legacy_brand_override,
    get_brand_gen_dir as _get_brand_gen_dir,
    get_inspiration_index_path as _get_inspiration_index_path,
    get_sessions_dir as _get_sessions_dir,
    infer_brand_key_from_path as _infer_brand_key_from_path,
    load_brand_gen_config as _load_brand_gen_config,
    resolve_active_brand_key as _resolve_active_brand_key,
    resolve_active_session_key as _resolve_active_session_key,
    resolve_context_brand_key as _resolve_context_brand_key,
    save_brand_gen_config as _save_brand_gen_config,
)

get_brand_gen_dir = partial(_get_brand_gen_dir, repo_root=REPO_ROOT)
brand_gen_config_path = partial(_brand_gen_config_path, repo_root=REPO_ROOT)
load_brand_gen_config = partial(
    _load_brand_gen_config,
    default_config=DEFAULT_BRAND_GEN_CONFIG,
    repo_root=REPO_ROOT,
    warn=warn,
)
save_brand_gen_config = partial(
    _save_brand_gen_config,
    default_config=DEFAULT_BRAND_GEN_CONFIG,
    repo_root=REPO_ROOT,
)
get_inspiration_index_path = partial(_get_inspiration_index_path, repo_root=REPO_ROOT)
resolve_active_brand_key = partial(_resolve_active_brand_key, repo_root=REPO_ROOT)
resolve_active_session_key = partial(_resolve_active_session_key, repo_root=REPO_ROOT)
get_sessions_dir = partial(_get_sessions_dir, repo_root=REPO_ROOT)
explicit_legacy_brand_override = _explicit_legacy_brand_override
infer_brand_key_from_path = partial(_infer_brand_key_from_path, repo_root=REPO_ROOT)


def resolve_path(value: Path | str) -> Path:
    return Path(value).expanduser().resolve()


def ensure_path_within_root(path: Path | str, root: Path | str, *, label: str = "path") -> Path:
    candidate = resolve_path(path)
    root_path = resolve_path(root)
    try:
        candidate.relative_to(root_path)
    except ValueError as exc:
        raise SystemExit(f"{label} must stay within {root_path}; got {candidate}") from exc
    return candidate


def validate_brand_workspace_dir(
    brand_dir: Path | str,
    *,
    expected_brand_dir: Path | str | None = None,
    label: str = "brand_dir",
) -> Path:
    candidate = resolve_path(brand_dir)
    expected = resolve_path(expected_brand_dir) if expected_brand_dir is not None else resolve_path(get_brand_dir())
    if candidate != expected:
        raise SystemExit(f"{label} must match the active workspace root {expected}; got {candidate}")
    return candidate


def resolve_profile_path(brand_dir: Path, explicit: str | None = None) -> Path:
    return Path(explicit).expanduser().resolve() if explicit else (brand_dir / "brand-profile.json").resolve()


def resolve_identity_path(brand_dir: Path, explicit: str | None = None) -> Path:
    return Path(explicit).expanduser().resolve() if explicit else (brand_dir / "brand-identity.json").resolve()


def _deep_merge_memory_dicts(base: dict, override: dict) -> dict:
    merged = dict(base or {})
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_memory_dicts(merged.get(key) or {}, value)
        elif value not in (None, "", [], {}):
            merged[key] = value
        elif key not in merged:
            merged[key] = value
    return merged


def _resolve_saved_brand_memory_fallback(
    brand_dir: Path,
    *,
    profile_path: Path,
    identity_path: Path,
    profile: dict,
    identity: dict,
) -> tuple[Path | None, Path | None, dict, dict]:
    brand_gen_dir = get_brand_gen_dir()
    if not brand_gen_dir:
        return None, None, {}, {}
    brand_key = resolve_context_brand_key(
        brand_dir=brand_dir,
        profile_path=profile_path if profile_path.exists() else None,
        identity_path=identity_path if identity_path.exists() else None,
        profile=profile,
        identity=identity,
        brand_gen_dir=brand_gen_dir,
    )
    if not brand_key:
        return None, None, {}, {}
    fallback_dir = (brand_gen_dir / "brands" / brand_key).resolve()
    if fallback_dir == brand_dir.resolve() or not fallback_dir.exists():
        return None, None, {}, {}
    fallback_profile_path = resolve_profile_path(fallback_dir)
    fallback_identity_path = resolve_identity_path(fallback_dir)
    fallback_profile = load_json_file(fallback_profile_path)
    fallback_identity = load_json_file(fallback_identity_path)
    if not fallback_profile and not fallback_identity:
        return None, None, {}, {}
    return fallback_profile_path, fallback_identity_path, fallback_profile, fallback_identity


def load_brand_memory(brand_dir: Path, profile_arg: str | None = None, identity_arg: str | None = None) -> tuple[Path, Path, dict, dict]:
    profile_path = resolve_profile_path(brand_dir, profile_arg)
    identity_path = resolve_identity_path(brand_dir, identity_arg)
    profile = load_json_file(profile_path)
    identity = load_json_file(identity_path)
    if profile and identity:
        return profile_path, identity_path, profile, identity

    fallback_profile_path, fallback_identity_path, fallback_profile, fallback_identity = _resolve_saved_brand_memory_fallback(
        brand_dir,
        profile_path=profile_path,
        identity_path=identity_path,
        profile=profile,
        identity=identity,
    )
    if fallback_profile:
        profile = _deep_merge_memory_dicts(fallback_profile, profile)
        profile_path = profile_path if profile_path.exists() else fallback_profile_path or profile_path
    if fallback_identity:
        identity = _deep_merge_memory_dicts(fallback_identity, identity)
        identity_path = identity_path if identity_path.exists() else fallback_identity_path or identity_path
    return profile_path, identity_path, profile, identity


def load_reference_role_packs() -> dict:
    return load_json_file(REFERENCE_ROLE_PACKS_PATH)


def load_prompt_review_rules() -> dict:
    return load_json_file(PROMPT_REVIEW_RULES_PATH)


def load_workflow_router_rules() -> dict:
    return load_json_file(WORKFLOW_ROUTER_RULES_PATH)


def load_system_prompt(name: str) -> str:
    path = SYSTEM_PROMPTS_DIR / f"{name}.md"
    if path.exists():
        return path.read_text().strip()
    return ""


def load_prompt_budget() -> dict:
    return load_json_file(PROMPT_BUDGET_PATH)


def load_material_snippets() -> dict:
    return load_json_file(MATERIAL_SNIPPETS_PATH)


_material_policy_cache: dict | None = None


def load_material_policy() -> dict:
    global _material_policy_cache
    if _material_policy_cache is None:
        _material_policy_cache = load_json_file(MATERIAL_POLICY_PATH)
    return _material_policy_cache


def load_prompt_fragments() -> dict:
    return load_json_file(PROMPT_FRAGMENTS_PATH)


def load_idea_tracks() -> dict:
    return load_json_file(IDEA_TRACKS_PATH)


def load_alignment_questions() -> dict:
    return load_json_file(ALIGNMENT_QUESTIONS_PATH)


def load_pipeline_config() -> dict:
    return load_json_file(PIPELINE_CONFIG_PATH)


def get_sources_registry_path(brand_gen_dir: Path | None = None) -> Path:
    resolved = brand_gen_dir or get_brand_gen_dir()
    candidate = resolved / "sources" / "brand_example_sources.json" if resolved else None
    if candidate and candidate.exists():
        return candidate
    return REPO_ROOT / "data" / "brand_example_sources.json"


def load_source_registry() -> dict:
    return load_json_file(get_sources_registry_path())


def load_source_registry_lookup() -> dict[str, dict]:
    registry = load_source_registry()
    out: dict[str, dict] = {}
    for item in registry.get("sources") or []:
        if isinstance(item, dict) and item.get("key"):
            out[str(item["key"])] = item
    return out


def load_inspiration_index(brand_gen_dir: Path | None = None) -> dict:
    path = get_inspiration_index_path(brand_gen_dir=brand_gen_dir)
    if not path or not path.exists():
        return {"version": 1, "sources": {}}
    return load_json_file(path) or {"version": 1, "sources": {}}


def inspirations_config_path(active_brand: str | None = None, brand_gen_dir: Path | None = None) -> Path | None:
    resolved = brand_gen_dir or get_brand_gen_dir()
    brand_key = active_brand or resolve_active_brand_key(brand_gen_dir=resolved, repo_root=REPO_ROOT)
    if not resolved or not brand_key:
        return None
    return resolved / "brands" / brand_key / "inspirations.json"


def load_inspirations_config(active_brand: str | None = None, brand_gen_dir: Path | None = None) -> dict:
    path = inspirations_config_path(active_brand, brand_gen_dir)
    if not path or not path.exists():
        return {"version": 1, "sources": [], "mode": "principles", "mergeStrategy": "concat"}
    payload = load_json_file(path)
    merged = {"version": 1, "sources": [], "mode": "principles", "mergeStrategy": "concat"}
    merged.update(payload)
    merged["sources"] = merged.get("sources") or []
    return merged


def save_inspirations_config(config: dict, active_brand: str, brand_gen_dir: Path | None = None) -> Path:
    resolved = brand_gen_dir or get_brand_gen_dir() or (REPO_ROOT / ".brand-gen")
    path = resolved / "brands" / active_brand / "inspirations.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "sources": [], "mode": "principles", "mergeStrategy": "concat"}
    payload.update(config or {})
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def save_prompt_review_scratchpad(brand_dir: Path, review: dict, *, label: str) -> Path:
    scratch_dir = brand_dir / "scratchpads" / "prompt-reviews"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    path = scratch_dir / f"{slugify(label)}.json"
    path.write_text(json.dumps(review, indent=2) + "\n")
    return path


def save_plan_draft(brand_dir: Path, payload: dict, *, label: str, workflow_id: str = "") -> Path:
    scratch_dir = brand_dir / "scratchpads" / "plan-drafts"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"-{workflow_id[:12]}" if workflow_id else ""
    path = scratch_dir / f"{slugify(label)}{suffix}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def save_plan_critique(brand_dir: Path, payload: dict, *, label: str, workflow_id: str = "") -> Path:
    scratch_dir = brand_dir / "scratchpads" / "plan-critiques"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"-{workflow_id[:12]}" if workflow_id else ""
    path = scratch_dir / f"{slugify(label)}{suffix}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def save_generation_scratchpad(brand_dir: Path, payload: dict, *, label: str, workflow_id: str = "") -> Path:
    scratch_dir = brand_dir / "scratchpads" / "generation"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"-{workflow_id[:12]}" if workflow_id else ""
    path = scratch_dir / f"{slugify(label)}{suffix}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def resolve_workflow_id(*payloads: dict | None) -> str:
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        value = payload.get("workflow_id")
        if value:
            return str(value)
        meta = payload.get("meta") or {}
        if isinstance(meta, dict) and meta.get("workflow_id"):
            return str(meta["workflow_id"])
    return uuid.uuid4().hex[:12]


def iter_workflow_artifact_paths(brand_dir: Path) -> list[Path]:
    roots = [
        brand_dir / "scratchpads" / "plan-drafts",
        brand_dir / "scratchpads" / "plan-critiques",
        brand_dir / "scratchpads" / "generation",
    ]
    paths: list[Path] = []
    for root in roots:
        if root.exists():
            paths.extend(sorted(root.glob("*.json")))
    return paths


def collect_workflow_artifacts(brand_dir: Path, workflow_id: str) -> dict[str, list[dict]]:
    grouped = {
        "plan_drafts": [],
        "plan_critiques": [],
        "generation_scratchpads": [],
    }
    mapping = {
        "plan_draft": "plan_drafts",
        "plan_critique": "plan_critiques",
        "generation_scratchpad": "generation_scratchpads",
    }
    for path in iter_workflow_artifact_paths(brand_dir):
        try:
            payload = load_json_file(path)
        except Exception:
            continue
        current = resolve_workflow_id(payload)
        if current != workflow_id:
            continue
        schema_type = str(payload.get("schema_type") or "")
        bucket = mapping.get(schema_type)
        if not bucket:
            continue
        grouped[bucket].append(
            {
                "path": str(path),
                "schema_type": schema_type,
                "created_at": payload.get("created_at") or "",
                "material_type": payload.get("material_type") or ((payload.get("plan") or {}).get("material_type") or ""),
                "mode": payload.get("workflow_mode") or payload.get("mode") or ((payload.get("plan") or {}).get("mode") or ""),
            }
        )
    return grouped


def get_legacy_brand_dir() -> Path:
    if os.environ.get("BRAND_DIR"):
        return Path(os.environ["BRAND_DIR"]).expanduser()
    if os.environ.get("LOGO_DIR"):
        return Path(os.environ["LOGO_DIR"]).expanduser()
    base = Path(os.environ.get("SCREENSHOTS_DIR", ".")).expanduser()
    return base / "brand-materials"


def list_brand_dirs(brand_gen_dir: Path | None = None) -> list[Path]:
    resolved = brand_gen_dir or get_brand_gen_dir()
    if not resolved:
        return []
    brands_dir = resolved / "brands"
    discovered: dict[str, Path] = {}
    if brands_dir.exists():
        for path in brands_dir.iterdir():
            if path.is_dir():
                discovered[path.name] = path
    registry = load_brand_registry(resolved)
    for key, item in (registry.get("brands") or {}).items():
        candidate = Path(str((item or {}).get("path") or (brands_dir / key))).expanduser()
        if candidate.exists() and candidate.is_dir():
            discovered[str(key)] = candidate
    return [discovered[name] for name in sorted(discovered)]


def resolve_context_brand_key(
    *,
    brand_dir: Path | None = None,
    profile_path: Path | None = None,
    identity_path: Path | None = None,
    profile: dict | None = None,
    identity: dict | None = None,
    brand_gen_dir: Path | None = None,
) -> str | None:
    return _resolve_context_brand_key(
        brand_dir=brand_dir,
        profile_path=profile_path,
        identity_path=identity_path,
        profile=profile,
        identity=identity,
        brand_gen_dir=brand_gen_dir,
        repo_root=REPO_ROOT,
        resolve_active_brand_key_fn=lambda brand_gen_dir=None, repo_root=None: resolve_active_brand_key(brand_gen_dir=brand_gen_dir, repo_root=repo_root or REPO_ROOT),
    )


def resolve_active_brand_dir(brand_gen_dir: Path | None = None, *, strict: bool = False) -> Path:
    resolved = brand_gen_dir or get_brand_gen_dir()
    active_session = resolve_active_session_key(brand_gen_dir=resolved, repo_root=REPO_ROOT)
    if resolved and active_session:
        session_dir = resolved / "sessions" / active_session / "brand-materials"
        if session_dir.exists():
            return session_dir
        message = f"Active testing session '{active_session}' not found under {resolved / 'sessions'}."
        if strict:
            raise SystemExit(message)
        warn(message)
    active = resolve_active_brand_key(brand_gen_dir=resolved, repo_root=REPO_ROOT)
    if resolved and active:
        active_dir = resolved / "brands" / active
        if active_dir.exists():
            return active_dir
        message = f"Active brand '{active}' not found under {resolved / 'brands'}."
        if strict:
            raise SystemExit(message)
        warn(message)
    legacy = explicit_legacy_brand_override()
    if legacy is not None:
        return legacy
    message = (
        "No active brand context. Start with `brand_iterate.py start-testing --session-name <name>` "
        "for a working session, or switch to a saved brand with `brand_iterate.py use <brand>`."
    )
    raise SystemExit(message)


def get_brand_dir() -> Path:
    return resolve_active_brand_dir(strict=True)


def get_manifest_path(brand_dir: Path | None = None) -> Path:
    base_dir = Path(brand_dir).expanduser().resolve() if brand_dir else get_brand_dir()
    return base_dir / "manifest.json"


def load_manifest(brand_dir: Path | None = None) -> dict:
    path = get_manifest_path(brand_dir)
    if path.exists():
        return json.loads(path.read_text())
    return {"versions": {}, "locked_fragments": [], "reference_versions": []}


def save_manifest(manifest: dict, brand_dir: Path | None = None) -> None:
    """Atomically write manifest with file-level locking."""
    atomic_json_write(get_manifest_path(brand_dir), manifest)


def next_version_num(manifest: dict, brand_dir: Path | None = None) -> int:
    nums = []
    for key in manifest["versions"]:
        match = re.match(r"v(\d+)", key)
        if match:
            nums.append(int(match.group(1)))
    base_dir = Path(brand_dir).expanduser().resolve() if brand_dir else get_brand_dir()
    for path in base_dir.glob("v*"):
        match = re.match(r"v(\d+)", path.stem)
        if match:
            nums.append(int(match.group(1)))
    return max(nums, default=0) + 1
