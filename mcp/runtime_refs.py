from __future__ import annotations

import base64
import mimetypes
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .runtime_models import ROLE_PACK_TAG_PRIORITY, SUPPORTED_IMAGE_EXTS, SUPPORTED_MEDIA_EXTS, SUPPORTED_VIDEO_EXTS


def path_media_kind(path: Path | str) -> str:
    ext = Path(path).suffix.lower()
    if ext in SUPPORTED_IMAGE_EXTS:
        return "image"
    if ext in SUPPORTED_VIDEO_EXTS:
        return "video"
    return "other"


def find_role_asset_paths(source_root: Path) -> dict[str, Path]:
    role_assets: dict[str, Path] = {}
    search_roots = [source_root / "screenshots", source_root]
    for role in ROLE_PACK_TAG_PRIORITY:
        for root in search_roots:
            if not root.exists():
                continue
            exact_matches = [
                root / f"{role}.png",
                root / f"{role}.webp",
                root / f"{role}.jpg",
                root / f"{role}.jpeg",
                root / f"{role}.svg",
                root / f"{role}.gif",
                root / f"{role}.mp4",
                root / f"{role}.mov",
                root / f"{role}.webm",
                root / f"{role}.m4v",
            ]
            candidate = next((path for path in exact_matches if path.exists()), None)
            if not candidate:
                wildcard = sorted(
                    [
                        path
                        for path in root.glob(f"{role}*")
                        if path.is_file() and path_media_kind(path) in {"image", "video"}
                    ]
                )
                candidate = wildcard[0] if wildcard else None
            if candidate:
                role_assets[role] = candidate.resolve()
                break
    return role_assets


def sanitize_reference_tag(value: str, fallback: str) -> str:
    tag = re.sub(r"[^A-Za-z0-9]+", "", str(value or ""))
    if not tag:
        tag = fallback
    if not tag[0].isalpha():
        tag = f"r{tag}"
    if len(tag) < 3:
        tag = (tag + "ref")[:3]
    return tag[:15]


def build_reference_tag_context(
    model: str,
    generation_mode: str,
    reference_paths: list[Path],
    role_pack_entries: list[dict],
) -> dict:
    if generation_mode != "image" or model != "runway-gen4-image":
        return {
            "passed_refs": list(reference_paths),
            "reference_tags": [],
            "prompt_suffix": "",
        }

    selected: list[tuple[Path, str, str]] = []
    seen: set[str] = set()

    for index, ref in enumerate(reference_paths):
        resolved = Path(ref).expanduser().resolve()
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        fallback = "brandref" if index == 0 else f"ref{index+1}"
        tag = sanitize_reference_tag("brandref" if index == 0 else fallback, fallback)
        help_text = "Use this tag for brand truth, subject silhouette, and exact mark or product identity."
        selected.append((resolved, tag, help_text))
        if len(selected) >= 3:
            break

    role_priority: list[str] = []
    for item in role_pack_entries:
        role = item.get("role")
        if role and role not in role_priority:
            role_priority.append(role)
    for role in ROLE_PACK_TAG_PRIORITY:
        if role not in role_priority:
            role_priority.append(role)

    if len(selected) < 3:
        for role in role_priority:
            for item in role_pack_entries:
                if item.get("role") != role:
                    continue
                if item.get("asset_kind") != "image":
                    continue
                resolved = Path(item["path"]).expanduser().resolve()
                key = str(resolved)
                if key in seen:
                    continue
                seen.add(key)
                tag = sanitize_reference_tag(role, f"ref{len(selected)+1}")
                help_text = item.get("role_help") or f"Use @{tag} only for {role}."
                selected.append((resolved, tag, help_text))
                break
            if len(selected) >= 3:
                break

    tag_lines = [f"- @{tag}: {help_text}" for _path, tag, help_text in selected]
    prompt_suffix = "Reference tags for this run:\n" + "\n".join(tag_lines) if tag_lines else ""
    return {
        "passed_refs": [item[0] for item in selected],
        "reference_tags": [item[1] for item in selected],
        "prompt_suffix": prompt_suffix,
    }


def normalize_image_args(images) -> list[str]:
    if not images:
        return []
    if isinstance(images, str):
        return [images]
    flattened: list[str] = []
    for image in images:
        if isinstance(image, (list, tuple)):
            flattened.extend(image)
        else:
            flattened.append(image)
    return flattened


def resolve_brand_asset_paths(profile: dict, identity: dict, brand_dir: Path | None = None) -> list[Path]:
    assets = identity.get("brand_assets") or profile.get("brand_assets") or {}
    project_root = (
        (identity.get("brand") or {}).get("project_root")
        or profile.get("project_root")
        or ""
    )
    resolved: list[Path] = []
    seen: set[str] = set()

    for key in ("icon", "wordmark", "lockup"):
        rel_path = assets.get(key)
        if not rel_path or not isinstance(rel_path, str):
            continue
        abs_path = Path(rel_path).expanduser().resolve()
        if abs_path.exists() and abs_path.suffix.lower() in SUPPORTED_IMAGE_EXTS:
            if str(abs_path) not in seen:
                resolved.append(abs_path)
                seen.add(str(abs_path))
            continue
        if project_root:
            candidate = Path(project_root).expanduser().resolve() / rel_path
            if candidate.exists() and candidate.suffix.lower() in SUPPORTED_IMAGE_EXTS:
                resolved_candidate = candidate.resolve()
                if str(resolved_candidate) not in seen:
                    resolved.append(resolved_candidate)
                    seen.add(str(resolved_candidate))
                continue
        if brand_dir:
            candidate = brand_dir / rel_path
            if candidate.exists() and candidate.suffix.lower() in SUPPORTED_IMAGE_EXTS:
                resolved_candidate = candidate.resolve()
                if str(resolved_candidate) not in seen:
                    resolved.append(resolved_candidate)
                    seen.add(str(resolved_candidate))
    return resolved


def expand_reference_paths(images, reference_dir=None) -> list[Path]:
    refs: list[Path] = []
    for image in normalize_image_args(images):
        path = Path(image).expanduser()
        if not path.exists():
            print(f"ERROR: Reference asset not found: {image}", file=sys.stderr)
            sys.exit(1)
        if path.suffix.lower() not in SUPPORTED_MEDIA_EXTS:
            print(f"ERROR: Unsupported reference asset type: {image}", file=sys.stderr)
            sys.exit(1)
        refs.append(path.resolve())

    if reference_dir:
        ref_dir = Path(reference_dir).expanduser()
        if not ref_dir.exists() or not ref_dir.is_dir():
            print(f"ERROR: Reference directory not found: {reference_dir}", file=sys.stderr)
            sys.exit(1)
        dir_refs = sorted(
            path.resolve()
            for path in ref_dir.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_MEDIA_EXTS
        )
        if not dir_refs:
            print(f"ERROR: No supported reference assets found in: {reference_dir}", file=sys.stderr)
            sys.exit(1)
        refs.extend(dir_refs)

    deduped: list[Path] = []
    seen = set()
    for ref in refs:
        key = str(ref)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ref)
    return deduped


def stage_reference_assets(version_id: str, reference_paths: list[Path], brand_dir: Path) -> list[str]:
    if not reference_paths:
        return []
    references_dir = brand_dir / "references"
    references_dir.mkdir(parents=True, exist_ok=True)
    staged: list[str] = []
    for idx, source in enumerate(reference_paths, start=1):
        dest_name = f"{version_id}-ref-{idx:02d}{source.suffix.lower()}"
        dest = references_dir / dest_name
        shutil.copy2(source, dest)
        staged.append(str(Path("references") / dest_name))
    return staged


def resolve_workflow_mode(requested_mode: str, reference_paths: list[Path]) -> str:
    if requested_mode != "auto":
        return requested_mode
    return "reference" if reference_paths else "inspiration"


def media_tag(path: Path, embed: bool = False) -> str:
    ext = path.suffix.lower()
    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    if ext in SUPPORTED_VIDEO_EXTS:
        if embed:
            b64 = base64.b64encode(path.read_bytes()).decode()
            return (
                f'<video controls loop muted playsinline preload="metadata">'
                f'<source src="data:{mime};base64,{b64}" type="{mime}"></video>'
            )
        return (
            f'<video controls loop muted playsinline preload="metadata">'
            f'<source src="{path.name}" type="{mime}"></video>'
        )
    if embed:
        b64 = base64.b64encode(path.read_bytes()).decode()
        return f'<img src="data:{mime};base64,{b64}" alt="{path.name}">'
    return f'<img src="{path.name}" loading="lazy" alt="{path.name}">'


def convert_video_to_gif(video_path: Path) -> Path | None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("WARNING: ffmpeg not found; skipping GIF conversion.", file=sys.stderr)
        return None
    gif_path = video_path.with_suffix(".gif")
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(video_path),
        "-vf",
        "fps=12,scale=960:-1:flags=lanczos",
        str(gif_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("WARNING: GIF conversion failed.", file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return None
    print(f"Converted GIF: {gif_path.name}")
    return gif_path
