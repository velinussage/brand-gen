"""Launch video producer — single-command multi-shot launch film pipeline.

Given a brief JSON describing shots + a timeline, this module:
  1. Generates each video shot via brand-gen's existing derive-video pipeline
     (scratchpad → execute_generation_scratchpad) so every clip lands in the
     manifest with proper lineage (source_version, workflow_id, tag).
  2. Assembles typography cards (if referenced) via a small PIL helper.
  3. Stitches everything via ffmpeg into a single final mp4.
  4. Registers the final mp4 in the manifest as its own version so launch
     deliverables are first-class artifacts (not /tmp/ orphans).

Brief JSON schema (minimal):

    {
      "title": "sage launch v3",
      "shots": [
        {
          "source_version": "v100",
          "prompt": "...motion prompt...",
          "duration": 5,
          "tag": "launch-v3-bowls",
          "model": "seedance-2-pro",
          "aspect_ratio": "16:9"
        },
        ...
      ],
      "typography_cards_dir": "/abs/or/brand/relative/cards/",
      "timeline": [
        {"kind": "video_tag", "tag": "launch-v3-bowls",    "duration": 7},
        {"kind": "video_tag", "tag": "launch-v3-artisan",  "duration": 8},
        {"kind": "image",     "path": "flash-taste.png",   "duration": 5},
        {"kind": "image",     "path": "ec-1-new-layer.png","duration": 5},
        ...
      ],
      "output_name": "launch-announcement-v3.mp4",
      "xfade_duration": 0.4
    }

Each `timeline` segment becomes one normalized ffmpeg segment; they're concatenated
with 0.4s xfades (or whatever is specified) in a single final mp4.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from .runtime import *  # noqa: F401,F403 — brings in SUPPORTED_IMAGE_EXTS, get_brand_dir, load_brand_memory, load_manifest, save_manifest, persist_generation_scratchpad_to_blackboard, resolve_workflow_id, save_generation_scratchpad, MATERIAL_CONFIG
from .run_ledger import append_run_event
from .generation_flow import execute_generation_scratchpad
from .seedance_validation import validate_seedance_prompt
from .custom_scratchpad import load_custom_scratchpad_markdown


def _build_derive_scratchpad(
    *,
    brand_dir: Path,
    manifest: dict,
    source_version: str,
    prompt: str,
    model: str,
    aspect_ratio: str,
    duration: int | None,
    tag: str,
    material_type: str = "short-video",
    profile: dict,
    identity: dict,
    profile_path: Path,
    identity_path: Path,
) -> dict:
    """Replicates the scratchpad structure that cmd_derive_video builds."""
    source_entry = (manifest.get("versions") or {}).get(source_version) or {}
    if not source_entry:
        raise SystemExit(f"source version '{source_version}' not found in manifest")
    image_paths = [
        brand_dir / name
        for name in (source_entry.get("files") or [])
        if Path(name).suffix.lower() in SUPPORTED_IMAGE_EXTS and (brand_dir / name).exists()
    ]
    if not image_paths:
        raise SystemExit(f"source version '{source_version}' has no available image file")

    config = MATERIAL_CONFIG.get(material_type) or {}
    workflow_id = resolve_workflow_id({})
    payload = {
        "schema_type": "generation_scratchpad",
        "schema_version": 1,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "brand_dir": str(brand_dir),
        "workflow_id": workflow_id,
        "source_version": source_version,
        "branch_id": workflow_id,
        "parent_branch_id": source_entry.get("branch_id") or source_entry.get("workflow_id") or "",
        "branch_status": "active",
        "material_type": material_type,
        "tag": tag or material_type,
        "workflow_mode": source_entry.get("mode") or "hybrid",
        "generation_mode": "video",
        "profile_path": str(profile_path),
        "identity_path": str(identity_path),
        "raw_prompt": prompt,
        "effective_prompt": prompt,
        "execution_prompt": prompt,
        "prompt_context": {
            "brand_prelude": "",
            "material_prompt_snippet": "",
            "reference_role_pack_snippet": "",
            "inspiration_doctrine": "",
            "reference_role_pack": [],
            "token_block": "",
            "token_block_fragments": [],
        },
        "prompt_review": {},
        "checks": {"blocking": [], "warnings": []},
        "reference_context": {
            "passed_reference_paths": [str(image_paths[0])],
            "all_context_refs": [str(image_paths[0])],
        },
        "selected_reference_ids": list(source_entry.get("selected_reference_ids") or []),
        "selected_inspiration_ids": list(source_entry.get("selected_inspiration_ids") or []),
        "derivative_mode": "generated_mockup_scene",
        "execution": {
            "model": model,
            "aspect_ratio": aspect_ratio,
            "duration": duration,
            "motion_reference": None,
            "negative_prompt": None,
            "make_gif": False,
        },
    }
    output_path = save_generation_scratchpad(brand_dir, payload, label=f"{source_version}-launch-{tag}")
    persist_generation_scratchpad_to_blackboard(brand_dir, profile, identity, payload, output_path=output_path, workflow_id=workflow_id)
    append_run_event(
        brand_dir,
        workflow_id,
        stage="scratchpad",
        event_type="launch_video_scratchpad_built",
        material_type=material_type,
        mode=payload.get("workflow_mode") or "",
        model=model,
        source_version=source_version,
        status="ok",
        data={"output_path": str(output_path), "tag": tag},
    )
    payload["_scratchpad_path"] = str(output_path)
    return payload


def _find_clip_by_tag(manifest: dict, tag: str) -> tuple[str, Path] | None:
    """Return (version_id, absolute_file_path) for the latest short-video with this tag."""
    versions = manifest.get("versions") or {}
    candidates = [
        (k, v) for k, v in versions.items()
        if v.get("tag") == tag and v.get("material_type") == "short-video"
        and (v.get("files") or [""])[0]
    ]
    if not candidates:
        return None
    # Pick the latest by version number
    candidates.sort(key=lambda kv: int(kv[0][1:]) if kv[0][1:].isdigit() else 0)
    v_id, v_entry = candidates[-1]
    return v_id, Path(v_entry["files"][0])


def _run(cmd: list[str], log_path: Path | None = None) -> None:
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "wb") as f:
            subprocess.run(cmd, check=True, stdout=f, stderr=subprocess.STDOUT)
    else:
        subprocess.run(cmd, check=True)


def _normalize_video(src: Path, dst: Path, duration: float, cream_hex: str = "0xf4ebd9") -> None:
    vf = (
        f"scale=1920:1080:force_original_aspect_ratio=decrease,"
        f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color={cream_hex},"
        f"setsar=1,fps=30,tpad=stop_mode=clone:stop_duration=15"
    )
    _run([
        "ffmpeg", "-y", "-i", str(src), "-an",
        "-vf", vf,
        "-t", str(duration),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19", "-preset", "medium",
        str(dst),
    ])


def _normalize_image(src: Path, dst: Path, duration: float) -> None:
    _run([
        "ffmpeg", "-y", "-loop", "1", "-i", str(src), "-t", str(duration),
        "-vf", "scale=1920:1080,setsar=1,fps=30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19", "-preset", "medium",
        str(dst),
    ])


def _xfade_concat(segments: list[Path], durations: list[float], xfade_d: float, dst: Path) -> None:
    # Build filter_complex with cumulative xfade offsets.
    # For N segments, N-1 xfade filters; offset for xfade #i = (sum of durations[0..i]) - xfade_d * (i+1)
    # Simpler: cumulative end of running video minus xfade_d per iteration.
    inputs = []
    for s in segments:
        inputs.extend(["-i", str(s)])
    filter_parts = []
    prev_label = "[0:v]"
    cum = durations[0]
    for i in range(1, len(segments)):
        offset = cum - xfade_d
        out_label = f"[v{i}]" if i < len(segments) - 1 else "[vout]"
        filter_parts.append(
            f"{prev_label}[{i}:v]xfade=transition=fade:duration={xfade_d}:offset={offset:.3f}{out_label}"
        )
        prev_label = out_label
        cum = cum + durations[i] - xfade_d
    filter_complex = ";".join(filter_parts)
    _run([
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium", "-r", "30",
        "-movflags", "+faststart",
        str(dst),
    ])


def _assert_motion_grammar_present(brand_dir: Path) -> None:
    """Before firing a launch film, confirm the brand has established its motion
    grammar. Without it the cinematographer agent has nothing to anchor on and
    we end up generating whatever the underlying model's defaults happen to be.
    """
    md = load_custom_scratchpad_markdown(brand_dir)
    if not md or "## Motion grammar" not in md:
        raise SystemExit(
            "launch_producer refuses to run: no `## Motion grammar` section in "
            f"{brand_dir / 'custom-scratchpad.md'}. Run the brand-philosopher "
            "agent with direction hint 'establish motion grammar' first."
        )


def _assert_shots_pass_validation(shots: list[dict]) -> None:
    """Run the seven-rule seedance validator on every shot prompt. Reject the
    whole brief if any shot fails — cheaper to fix the brief than to burn
    credits on a doomed generation.
    """
    failures: list[str] = []
    for shot in shots:
        prompt = str(shot.get("prompt") or "").strip()
        if not prompt:
            failures.append(f"  tag={shot.get('tag', '?')}: empty prompt")
            continue
        result = validate_seedance_prompt(
            prompt,
            duration_seconds=float(shot.get("duration") or 5),
        )
        if not result.ok:
            failures.append(f"  tag={shot.get('tag', '?')}:\n" + result.report())
    if failures:
        raise SystemExit(
            "launch_producer refuses to run: shot prompts failed seedance "
            "shot-design validation. Delegate to brand-cinematographer and "
            "re-submit.\n" + "\n".join(failures)
        )


def create_video(brief_path: Path, *, verbose: bool = True, skip_validation: bool = False) -> dict:
    """Run the full launch-video pipeline from a brief JSON. Returns result summary dict."""
    brief = json.loads(brief_path.read_text())
    brand_dir = get_brand_dir()
    manifest = load_manifest(brand_dir)
    profile_path, identity_path, profile, identity = load_brand_memory(brand_dir, None, None)

    shots = brief.get("shots", [])
    if not skip_validation:
        _assert_motion_grammar_present(brand_dir)
        _assert_shots_pass_validation(shots)

    # ---- 1. Generate each shot (skip if already produced by tag) ---------
    produced: dict[str, Path] = {}  # tag -> absolute mp4 path
    for shot in shots:
        tag = shot["tag"]
        found = _find_clip_by_tag(manifest, tag)
        if found:
            v_id, rel_path = found
            abs_path = brand_dir / rel_path
            if abs_path.exists() and abs_path.stat().st_size > 50_000:
                if verbose:
                    print(f"[skip] shot {tag} already exists at {v_id} ({rel_path.name})")
                produced[tag] = abs_path
                continue

        if verbose:
            print(f"[generate] {tag} from source {shot['source_version']} ({shot.get('model', 'seedance-2-pro')})")
        payload = _build_derive_scratchpad(
            brand_dir=brand_dir,
            manifest=manifest,
            source_version=shot["source_version"],
            prompt=shot["prompt"],
            model=shot.get("model", "seedance-2-pro"),
            aspect_ratio=shot.get("aspect_ratio", "16:9"),
            duration=shot.get("duration", 5),
            tag=tag,
            profile=profile,
            identity=identity,
            profile_path=profile_path,
            identity_path=identity_path,
        )
        version_id = execute_generation_scratchpad(payload, workflow_id=payload["workflow_id"])
        # Refresh manifest after write
        manifest = load_manifest(brand_dir)
        entry = (manifest.get("versions") or {}).get(version_id, {})
        files = entry.get("files") or []
        if not files:
            raise SystemExit(f"shot {tag} did not produce a file")
        produced[tag] = brand_dir / files[0]
        if verbose:
            print(f"  → {version_id} ({files[0]})")

    # ---- 2. Resolve timeline ---------------------------------------------
    timeline = brief.get("timeline", [])
    if not timeline:
        raise SystemExit("brief has no timeline")

    typo_dir = Path(brief.get("typography_cards_dir", str(brand_dir / "launch_cards"))).expanduser()
    work_dir = brand_dir / "launch-build"
    work_dir.mkdir(parents=True, exist_ok=True)

    segments: list[Path] = []
    durations: list[float] = []
    for i, seg in enumerate(timeline):
        idx = f"{i:02d}"
        dur = float(seg["duration"])
        durations.append(dur)
        out = work_dir / f"seg-{idx}.mp4"
        kind = seg["kind"]
        if kind == "video_tag":
            src = produced.get(seg["tag"])
            if src is None or not src.exists():
                raise SystemExit(f"timeline segment {idx} references missing tag '{seg['tag']}'")
            if verbose:
                print(f"[norm video] seg-{idx} {seg['tag']} -> {dur}s")
            _normalize_video(src, out, dur)
        elif kind == "image":
            candidate = Path(seg["path"]).expanduser()
            if not candidate.is_absolute():
                # Resolve relative to typography_cards_dir first, then brand_dir
                for base in (typo_dir, brand_dir):
                    probe = base / seg["path"]
                    if probe.exists():
                        candidate = probe
                        break
            if not candidate.exists():
                raise SystemExit(f"timeline segment {idx} references missing image '{seg['path']}'")
            if verbose:
                print(f"[norm image] seg-{idx} {candidate.name} -> {dur}s")
            _normalize_image(candidate, out, dur)
        else:
            raise SystemExit(f"unknown timeline kind: {kind}")
        segments.append(out)

    # ---- 3. Stitch -------------------------------------------------------
    xfade_d = float(brief.get("xfade_duration", 0.4))
    output_name = brief.get("output_name", "launch-announcement.mp4")
    final_out = work_dir / output_name
    if verbose:
        print(f"[stitch] {len(segments)} segments, {xfade_d}s xfades → {output_name}")
    _xfade_concat(segments, durations, xfade_d, final_out)

    # Copy to brand root so it's easy to find
    deployed = brand_dir / output_name
    shutil.copy(final_out, deployed)

    # ---- 4. Register in manifest ----------------------------------------
    manifest = load_manifest(brand_dir)
    next_v = 1 + max(
        (int(k[1:]) for k in manifest["versions"] if k.startswith("v") and k[1:].isdigit()),
        default=0,
    )
    v_id = f"v{next_v:03d}"
    manifest["versions"][v_id] = {
        "material_type": "launch-video",
        "model": "launch-producer+seedance-2-pro",
        "files": [output_name],
        "aspect_ratio": "16:9",
        "mode": "launch",
        "tag": brief.get("title", "launch-video"),
        "notes": f"Full launch video from brief {brief_path.name}. {len(shots)} shots + typography timeline.",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    save_manifest(brand_dir, manifest)

    return {
        "version_id": v_id,
        "output_path": str(deployed),
        "shots": list(produced.keys()),
        "timeline_length": sum(durations) - xfade_d * (len(durations) - 1),
    }
