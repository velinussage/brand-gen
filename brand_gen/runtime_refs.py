from __future__ import annotations

import base64
import hashlib
import mimetypes
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .runtime_models import ROLE_PACK_TAG_PRIORITY, SUPPORTED_IMAGE_EXTS, SUPPORTED_MEDIA_EXTS, SUPPORTED_VIDEO_EXTS, role_pack_material_key


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


_PRODUCT_TRUTH_REFERENCE_NAME_TOKENS = (
    "library-canon-proof",
    "manifest-proof",
    "skill-proof",
    "tool-proof",
    "capability-proof",
    "mcp-proof",
    "library",
    "manifest",
    "skill",
    "tool",
    "capability",
    "proof",
)


def _brand_name_from_identity(identity: dict, brand_dir: Path | None = None) -> str:
    name = str(((identity or {}).get("brand") or {}).get("name") or "").strip().lower()
    if name:
        return re.sub(r"[^a-z0-9_-]+", "-", name).strip("-")
    if brand_dir:
        return re.sub(r"[^a-z0-9_-]+", "-", brand_dir.name.lower()).strip("-")
    return ""


def _reference_candidate_roots(brand_dir: Path, brand_name: str) -> list[Path]:
    roots = [
        brand_dir / "proof-references",
        brand_dir / "references",
    ]
    try:
        from .runtime_paths import REPO_ROOT

        if brand_name:
            roots.extend(
                [
                    REPO_ROOT / "brands" / brand_name / "proof-references",
                    REPO_ROOT / "brands" / brand_name / "references",
                ]
            )
    except Exception:
        pass
    return roots


def _reference_candidate_score(path: Path) -> tuple[int, str]:
    name = path.name.lower()
    if any(token in name for token in ("logo", "wordmark", "lockup", "mark-only")):
        return (999, name)
    # Prefer deterministic product-truth control frames generated by the
    # current pipeline over older captured screenshots.  This matters most for
    # motion: video models receive only one start frame, so an old UI capture
    # can become the entire story.
    if "motion-start" in str(path).lower() or "sage-motion-start" in name:
        return (-20, name)
    if "sage-capability-proof-reference" in name:
        return (-10, name)
    for index, token in enumerate(_PRODUCT_TRUTH_REFERENCE_NAME_TOKENS):
        if token in name:
            return (index, name)
    return (500, name)


def _reference_candidate_root_rank(brand_dir: Path, path: Path, brand_name: str) -> int:
    """Return a stable root preference for product-truth reference candidates."""
    try:
        resolved = path.resolve()
        local = brand_dir.resolve()
        if resolved == local or local in resolved.parents:
            return 0
        from .runtime_paths import REPO_ROOT

        repo_brand = (REPO_ROOT / "brands" / brand_name).resolve() if brand_name else None
        if repo_brand and (resolved == repo_brand or repo_brand in resolved.parents):
            return 2
    except Exception:
        pass
    return 1


def _find_existing_product_truth_reference_paths(brand_dir: Path, brand_name: str) -> list[Path]:
    candidates: list[Path] = []
    for root in _reference_candidate_roots(brand_dir, brand_name):
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_IMAGE_EXTS:
                continue
            name = path.name.lower()
            if not any(token in name for token in _PRODUCT_TRUTH_REFERENCE_NAME_TOKENS):
                continue
            if any(token in name for token in ("logo", "wordmark", "lockup", "mark-only")):
                continue
            candidates.append(path.resolve())
    candidates = sorted(
        candidates,
        key=lambda path: (
            _reference_candidate_root_rank(brand_dir, path, brand_name),
            *_reference_candidate_score(path),
        ),
    )
    out: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def _font(size: int, *, bold: bool = False):
    try:
        from PIL import ImageFont
    except Exception:  # pragma: no cover - PIL import guard
        return None

    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Georgia Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
    ]
    for candidate in candidates:
        try:
            if candidate and Path(candidate).exists():
                return ImageFont.truetype(candidate, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _draw_label(draw, xy: tuple[int, int], text: str, *, fill: str, size: int, bold: bool = False) -> None:
    font = _font(size, bold=bold)
    draw.text(xy, text, fill=fill, font=font)


def ensure_sage_motion_start_frame_reference(
    brand_dir: Path,
    *,
    plan: dict | None = None,
    workflow_id: str = "",
) -> Path | None:
    """Create a fresh, current start-frame reference for Sage motion work.

    Stingers and feature animations should not inherit old UI screenshots or a
    logo tile as the first video frame.  This deterministic frame gives the
    video model one current product-truth scene: a library/manifest selects a
    capability, installs it into a thin agent harness, and the agent completes
    work.  It is a generated control frame, not campaign artwork.
    """
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return None

    plan = plan if isinstance(plan, dict) else {}
    seed_text = " ".join(
        str(part or "").strip()
        for part in [
            workflow_id,
            plan.get("product_truth_expression"),
            plan.get("prompt_seed"),
            plan.get("purpose"),
            plan.get("target_surface"),
        ]
        if str(part or "").strip()
    )
    digest = hashlib.sha1(seed_text.encode("utf-8", errors="ignore")).hexdigest()[:12] if seed_text else "current"
    out_dir = brand_dir / "references" / "_auto" / "motion-start"
    out_path = out_dir / f"sage-motion-start-{digest}.png"
    if out_path.exists():
        return out_path.resolve()

    out_dir.mkdir(parents=True, exist_ok=True)
    width, height = 1536, 864
    palette = {
        "cream": "#f4ebd9",
        "paper": "#fff8ea",
        "charcoal": "#2a231a",
        "dark": "#14110d",
        "rust": "#c67b5c",
        "sage": "#9caf99",
        "line": "#d9c7ad",
        "muted": "#604c3d",
        "green": "#7f946f",
    }
    image = Image.new("RGB", (width, height), palette["cream"])
    draw = ImageDraw.Draw(image)

    # Outer field and header.  Keep the Sage word as a tiny provenance seal;
    # the start frame is about capability adoption, not a logo reveal.
    draw.rounded_rectangle((52, 52, width - 52, height - 52), radius=52, fill=palette["paper"], outline=palette["charcoal"], width=4)
    _draw_label(draw, (94, 94), "Steer the Default", fill=palette["charcoal"], size=54, bold=True)
    _draw_label(draw, (98, 158), "skill layer for AI agents · fresh motion start frame", fill=palette["muted"], size=26)
    draw.rounded_rectangle((1320, 96, 1438, 148), radius=22, fill=palette["rust"], outline=palette["rust"], width=2)
    _draw_label(draw, (1354, 106), "Sage", fill=palette["paper"], size=24, bold=True)

    # Left: current library/manifest source object.
    manifest_box = (112, 250, 502, 680)
    draw.rounded_rectangle(manifest_box, radius=36, fill="#fbefd7", outline=palette["line"], width=3)
    _draw_label(draw, (150, 286), "source library", fill=palette["charcoal"], size=30, bold=True)
    _draw_label(draw, (150, 326), "manifest selects one default", fill=palette["muted"], size=22)
    rows = [
        ("Prompt", "curated"),
        ("Skill", "reusable"),
        ("Behavior", "selected"),
        ("MCP tool", "available"),
    ]
    y = 378
    for label, state in rows:
        fill = "#ffffff" if label != "Behavior" else "#f3e3cc"
        outline = palette["line"] if label != "Behavior" else palette["rust"]
        draw.rounded_rectangle((150, y, 462, y + 58), radius=18, fill=fill, outline=outline, width=3 if label == "Behavior" else 2)
        draw.rectangle((172, y + 17, 196, y + 41), fill=palette["rust"] if label == "Behavior" else palette["sage"])
        _draw_label(draw, (216, y + 12), label, fill=palette["charcoal"], size=22, bold=True)
        _draw_label(draw, (346, y + 15), state, fill=palette["muted"], size=18)
        y += 72

    # Center: switchboard / control-room routing grid.  Draw several routes so
    # the selected capability does not collapse into a single glowing bulb.
    board = (566, 250, 966, 680)
    draw.rounded_rectangle(board, radius=40, fill="#f7ead4", outline=palette["charcoal"], width=3)
    _draw_label(draw, (606, 286), "capability switchboard", fill=palette["charcoal"], size=28, bold=True)
    route_ys = [380, 450, 520, 590]
    for idx, ry in enumerate(route_ys):
        color = palette["rust"] if idx == 2 else palette["line"]
        width_line = 8 if idx == 2 else 4
        draw.line((612, ry, 920, ry), fill=color, width=width_line)
        for x in (656, 748, 840):
            radius = 14 if idx == 2 else 10
            draw.ellipse((x - radius, ry - radius, x + radius, ry + radius), fill=color, outline=palette["charcoal"] if idx == 2 else color, width=2)
    draw.rounded_rectangle((690, 612, 842, 650), radius=18, fill=palette["rust"], outline=palette["rust"], width=2)
    _draw_label(draw, (718, 620), "default", fill=palette["paper"], size=20, bold=True)

    # Selected route to agent runtime.
    draw.line((966, 520, 1076, 520), fill=palette["rust"], width=8)
    draw.polygon([(1076, 520), (1044, 500), (1044, 540)], fill=palette["rust"])

    # Right: thin harness / agent completing work.
    runtime = (1088, 250, 1424, 680)
    draw.rounded_rectangle(runtime, radius=38, fill=palette["dark"], outline=palette["charcoal"], width=3)
    _draw_label(draw, (1128, 288), "thin agent harness", fill=palette["paper"], size=28, bold=True)
    draw.rounded_rectangle((1128, 356, 1384, 466), radius=24, fill="#2b2d2f", outline="#4c4740", width=2)
    _draw_label(draw, (1152, 382), "Behavior installed", fill=palette["paper"], size=24, bold=True)
    _draw_label(draw, (1152, 420), "agent can now finish work", fill="#e6d8c6", size=20)
    draw.rounded_rectangle((1128, 510, 1384, 614), radius=24, fill="#f3e3cc", outline=palette["sage"], width=3)
    draw.ellipse((1158, 538, 1206, 586), fill=palette["green"], outline=palette["charcoal"], width=2)
    _draw_label(draw, (1170, 543), "✓", fill=palette["paper"], size=30, bold=True)
    _draw_label(draw, (1224, 538), "visible output", fill=palette["charcoal"], size=24, bold=True)
    _draw_label(draw, (1224, 572), "completed task", fill=palette["muted"], size=20)

    # Footer provenance for reviewers/generators.
    _draw_label(
        draw,
        (96, 742),
        "Reference contract: library → selected capability → agent use. No old screenshots, no centered logo, no light-bulb idea icon.",
        fill=palette["muted"],
        size=22,
    )

    image.save(out_path)
    return out_path.resolve()


def ensure_sage_capability_proof_reference(brand_dir: Path) -> Path | None:
    """Create a deterministic proof-reference card for Sage capability work.

    This is a reference/control artifact, not generated campaign art. It keeps
    reference mode anchored in real Sage capability nouns when no manifest /
    skill / MCP-tool proof asset has been captured yet.
    """
    out_dir = brand_dir / "references" / "_auto"
    out_path = out_dir / "sage-capability-proof-reference.png"
    if out_path.exists():
        return out_path.resolve()
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return None

    out_dir.mkdir(parents=True, exist_ok=True)
    width, height = 1400, 900
    palette = {
        "cream": "#f4ebd9",
        "paper": "#fff8ea",
        "charcoal": "#2a231a",
        "rust": "#c67b5c",
        "sage": "#9caf99",
        "line": "#d9c7ad",
    }
    image = Image.new("RGB", (width, height), palette["cream"])
    draw = ImageDraw.Draw(image)

    title_font = _font(52, bold=True)
    label_font = _font(32, bold=True)
    body_font = _font(26)
    mono_font = _font(24)

    draw.rounded_rectangle((70, 70, 1330, 830), radius=48, fill=palette["paper"], outline=palette["charcoal"], width=4)
    draw.text((115, 118), "Sage library manifest", fill=palette["charcoal"], font=title_font)
    draw.text((118, 184), "Trusted reusable capabilities for agent runtimes", fill=palette["charcoal"], font=body_font)

    manifest_box = (115, 260, 595, 665)
    runtime_box = (845, 260, 1285, 665)
    draw.rounded_rectangle(manifest_box, radius=32, fill="#fbefd7", outline=palette["line"], width=3)
    draw.rounded_rectangle(runtime_box, radius=32, fill="#f3e3cc", outline=palette["line"], width=3)
    draw.text((155, 300), "library manifest", fill=palette["charcoal"], font=label_font)
    rows = [
        ("skill card", "Reusable agent procedure"),
        ("MCP tool card", "Callable capability surface"),
        ("workflow card", "Multi-step controller plan"),
    ]
    y = 375
    for label, desc in rows:
        draw.rounded_rectangle((155, y, 555, y + 68), radius=18, fill="#ffffff", outline=palette["line"], width=2)
        draw.rectangle((172, y + 18, 198, y + 50), fill=palette["rust"])
        draw.text((220, y + 12), label, fill=palette["charcoal"], font=mono_font)
        draw.text((220, y + 39), desc, fill="#604c3d", font=body_font)
        y += 88

    # Routed capability arrows.
    for y in (390, 478, 566):
        draw.line((610, y, 830, y), fill=palette["rust"], width=6)
        draw.polygon([(830, y), (800, y - 18), (800, y + 18)], fill=palette["rust"])

    draw.text((895, 300), "agent runtime", fill=palette["charcoal"], font=label_font)
    draw.rounded_rectangle((895, 380, 1235, 555), radius=28, fill="#2b2d2f", outline=palette["charcoal"], width=2)
    draw.text((932, 430), "install capabilities", fill="#fff8ea", font=label_font)
    draw.text((934, 488), "skills • prompts • MCP tools", fill="#e6d8c6", font=body_font)
    draw.rounded_rectangle((895, 590, 1235, 638), radius=22, fill=palette["sage"], outline=palette["sage"], width=2)
    draw.text((930, 598), "governed + versioned", fill=palette["charcoal"], font=body_font)

    draw.rounded_rectangle((112, 720, 510, 772), radius=24, fill=palette["charcoal"])
    draw.text((145, 731), "reference proof — not logo-only", fill=palette["paper"], font=body_font)
    draw.text((1145, 724), "Sage", fill=palette["rust"], font=title_font)

    image.save(out_path)
    return out_path.resolve()


def resolve_product_truth_reference_paths(
    brand_dir: Path | None,
    identity: dict,
    *,
    limit: int = 1,
    create_fallback: bool = True,
    material_type: str = "",
    generation_mode: str = "",
    plan: dict | None = None,
    workflow_id: str = "",
    fresh_motion_frame: bool = False,
) -> list[Path]:
    if brand_dir is None:
        return []
    brand_name = _brand_name_from_identity(identity, brand_dir)
    material_key = role_pack_material_key(material_type) or str(material_type or "").strip().lower().replace("-", "_")
    wants_fresh_motion_frame = bool(
        fresh_motion_frame
        or (brand_name == "sage" and (material_key == "feature_animation" or str(generation_mode or "").lower() == "video"))
    )
    if wants_fresh_motion_frame and brand_name == "sage" and create_fallback:
        fresh = ensure_sage_motion_start_frame_reference(
            brand_dir,
            plan=plan,
            workflow_id=workflow_id,
        )
        if fresh:
            return [fresh]
    if create_fallback and brand_name == "sage":
        # Ensure the local deterministic proof exists before searching so
        # stale repo-level screenshots do not beat the current control asset.
        ensure_sage_capability_proof_reference(brand_dir)
    found = _find_existing_product_truth_reference_paths(brand_dir, brand_name)
    if not found and create_fallback and brand_name == "sage":
        fallback = ensure_sage_capability_proof_reference(brand_dir)
        if fallback:
            found = [fallback]
    return found[: max(0, int(limit or 1))]


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
