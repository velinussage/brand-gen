from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable

from .runtime_io import warn as runtime_warn

DEFAULT_BRAND_GEN_CONFIG = {
    "version": 2,
    "active": None,
    "activeSession": None,
    "inspirationMode": False,
    "brandGenDir": None,
}


def _looks_like_repo_root_workspace_override(candidate: Path, *, repo_root: Path) -> bool:
    """Return True when BRAND_GEN_DIR points at the checkout root, not the
    durable `.brand-gen` root.

    Older local env files used `BRAND_GEN_DIR=/path/to/brand-gen`, which
    made the runtime read/write top-level `brands/` beside the source tree
    while Pi/OpenClaw usually used `/path/to/brand-gen/.brand-gen`.  Treat
    that exact checkout-root shape as a compatibility typo and canonicalize
    to the child `.brand-gen` directory.  Do not rewrite arbitrary workspace
    roots named something else; users may intentionally keep a workspace at
    `~/brand-workspace` with `brands/` and `config.json` directly inside it.
    """
    try:
        if candidate.resolve() != repo_root.resolve():
            return False
    except OSError:
        return False
    return (candidate / ".brand-gen").is_dir() and (candidate / "brand_gen").is_dir()


def canonicalize_brand_gen_dir(value: str | Path, *, repo_root: Path) -> Path:
    candidate = Path(value).expanduser().resolve()
    if _looks_like_repo_root_workspace_override(candidate, repo_root=repo_root):
        return (candidate / ".brand-gen").resolve()
    return candidate


def get_brand_gen_dir(*, repo_root: Path) -> Path | None:
    override = os.environ.get("BRAND_GEN_DIR")
    if override:
        return canonicalize_brand_gen_dir(override, repo_root=repo_root)
    candidate = repo_root / ".brand-gen"
    if candidate.exists():
        return candidate.resolve()
    return None


def brand_gen_config_path(*, brand_gen_dir: Path | None = None, repo_root: Path) -> Path | None:
    resolved = brand_gen_dir or get_brand_gen_dir(repo_root=repo_root)
    if not resolved:
        return None
    return resolved / "config.json"


def load_brand_gen_config(
    *,
    default_config: dict | None = None,
    brand_gen_dir: Path | None = None,
    repo_root: Path,
    warn: Callable[[str], None] | None = None,
) -> dict:
    defaults = dict(default_config or DEFAULT_BRAND_GEN_CONFIG)
    path = brand_gen_config_path(brand_gen_dir=brand_gen_dir, repo_root=repo_root)
    if not path or not path.exists():
        return defaults
    try:
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise ValueError("config is not an object")
    except (json.JSONDecodeError, OSError, UnicodeDecodeError, ValueError):
        if warn:
            warn(f"Corrupted brand-gen config at {path}; using defaults.")
        return defaults
    merged = dict(defaults)
    merged.update(value)
    if merged.get("brandGenDir"):
        merged["brandGenDir"] = str(Path(str(merged["brandGenDir"])).expanduser().resolve())
    return merged


def save_brand_gen_config(
    config: dict,
    *,
    default_config: dict | None = None,
    brand_gen_dir: Path | None = None,
    repo_root: Path,
) -> Path:
    defaults = dict(default_config or DEFAULT_BRAND_GEN_CONFIG)
    resolved = brand_gen_dir or get_brand_gen_dir(repo_root=repo_root) or (repo_root / ".brand-gen")
    resolved.mkdir(parents=True, exist_ok=True)
    path = resolved / "config.json"
    payload = dict(defaults)
    payload.update(config or {})
    payload["brandGenDir"] = str(resolved.resolve())
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def get_inspiration_index_path(*, brand_gen_dir: Path | None = None, repo_root: Path) -> Path | None:
    resolved = brand_gen_dir or get_brand_gen_dir(repo_root=repo_root)
    if not resolved:
        return None
    return resolved / "inspiration" / "index.json"


def resolve_active_brand_key(*, brand_gen_dir: Path | None = None, repo_root: Path) -> str | None:
    config = load_brand_gen_config(brand_gen_dir=brand_gen_dir, repo_root=repo_root)
    active = config.get("active")
    return str(active) if active else None


def resolve_active_session_key(*, brand_gen_dir: Path | None = None, repo_root: Path) -> str | None:
    config = load_brand_gen_config(brand_gen_dir=brand_gen_dir, repo_root=repo_root)
    active = config.get("activeSession")
    return str(active) if active else None


def get_sessions_dir(*, brand_gen_dir: Path | None = None, repo_root: Path) -> Path | None:
    resolved = brand_gen_dir or get_brand_gen_dir(repo_root=repo_root)
    if not resolved:
        return None
    return resolved / "sessions"


def explicit_legacy_brand_override() -> Path | None:
    if os.environ.get("BRAND_DIR"):
        return Path(os.environ["BRAND_DIR"]).expanduser()
    if os.environ.get("LOGO_DIR"):
        return Path(os.environ["LOGO_DIR"]).expanduser()
    if os.environ.get("SCREENSHOTS_DIR"):
        return Path(os.environ["SCREENSHOTS_DIR"]).expanduser() / "brand-materials"
    return None


def infer_brand_key_from_path(path: Path | None, *, brand_gen_dir: Path | None = None, repo_root: Path) -> str | None:
    resolved = brand_gen_dir or get_brand_gen_dir(repo_root=repo_root)
    if not resolved or not path:
        return None
    try:
        rel = path.resolve().relative_to((resolved / "brands").resolve())
    except (OSError, ValueError):
        return None
    parts = rel.parts
    return parts[0] if parts else None


def resolve_context_brand_key(
    *,
    brand_dir: Path | None = None,
    profile_path: Path | None = None,
    identity_path: Path | None = None,
    profile: dict | None = None,
    identity: dict | None = None,
    brand_gen_dir: Path | None = None,
    repo_root: Path,
    resolve_active_brand_key_fn: Callable[..., str | None] | None = None,
) -> str | None:
    inferred = infer_brand_key_from_path(
        profile_path if profile_path and profile_path.exists() else identity_path if identity_path and identity_path.exists() else None,
        brand_gen_dir=brand_gen_dir,
        repo_root=repo_root,
    )
    if inferred:
        return inferred
    for payload in (profile or {}, identity or {}):
        session_context = payload.get("session_context") or {}
        seeded_from = str(session_context.get("seeded_from_brand") or "").strip()
        if seeded_from:
            return seeded_from
    inferred_brand_dir = None
    if brand_dir:
        inferred_brand_dir = brand_dir
    elif profile_path and profile_path.exists():
        inferred_brand_dir = profile_path.parent
    elif identity_path and identity_path.exists():
        inferred_brand_dir = identity_path.parent
    if inferred_brand_dir:
        board_path = inferred_brand_dir / "blackboard.json"
        if board_path.exists():
            try:
                board = json.loads(board_path.read_text())
                for decision in reversed(board.get("decisions") or []):
                    data = decision.get("data") or {}
                    seeded_from = str(data.get("seeded_from_brand") or "").strip()
                    if seeded_from:
                        return seeded_from
            except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
                runtime_warn(f"Failed to read blackboard context at {board_path}: {exc}")
    resolver = resolve_active_brand_key_fn or resolve_active_brand_key
    return resolver(brand_gen_dir=brand_gen_dir, repo_root=repo_root)
