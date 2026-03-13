#!/usr/bin/env python3
"""
Logo iteration wrapper — structured feedback loop for multi-version logo design.

Usage:
  logo_iterate.py bootstrap                          Scan existing files into manifest
  logo_iterate.py generate -p "prompt" [opts]        Generate + auto-version + manifest
  logo_iterate.py feedback VERSION --score N [opts]  Record feedback for a version
  logo_iterate.py show [VERSION]                     Show manifest or version detail
  logo_iterate.py compare V1 V2 [V3...]              Generate HTML comparison board
  logo_iterate.py evolve                             Analyze prompt patterns from feedback
  logo_iterate.py inspire [CATEGORY]                 Browse logosystem.co for inspiration

Manifest: <LOGO_DIR>/manifest.json
Output:   <LOGO_DIR>/

Environment:
  LOGO_DIR         Override output directory (default: $SCREENSHOTS_DIR/logo-redesigns)
  SCREENSHOTS_DIR  Base screenshots directory
"""

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
ENV_CANDIDATES = [REPO_ROOT / ".env", Path.home() / ".claude" / ".env"]
GENERATE_PY = SCRIPT_DIR / "generate.py"
SUPPORTED_IMAGE_EXTS = {".png", ".webp", ".svg", ".jpg", ".jpeg", ".gif", ".bmp"}


def load_env_values():
    data = {}
    for path in reversed(ENV_CANDIDATES):
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def build_env():
    env = dict(os.environ)
    env.update(load_env_values())
    return env


for _key, _value in load_env_values().items():
    os.environ.setdefault(_key, _value)


def get_logo_dir():
    if os.environ.get("LOGO_DIR"):
        return Path(os.environ["LOGO_DIR"]).expanduser()
    base = os.environ.get("SCREENSHOTS_DIR", ".")
    return Path(base).expanduser() / "logo-redesigns"


def get_manifest_path():
    return get_logo_dir() / "manifest.json"


def load_manifest():
    p = get_manifest_path()
    if p.exists():
        return json.loads(p.read_text())
    return {"versions": {}, "locked_fragments": [], "reference_versions": []}


def save_manifest(m):
    get_manifest_path().write_text(json.dumps(m, indent=2) + "\n")


def normalize_image_args(images):
    if not images:
        return []
    if isinstance(images, str):
        return [images]
    flattened = []
    for image in images:
        if isinstance(image, (list, tuple)):
            flattened.extend(image)
        else:
            flattened.append(image)
    return flattened


def expand_reference_paths(images, reference_dir=None):
    refs = []
    for image in normalize_image_args(images):
        path = Path(image).expanduser()
        if not path.exists():
            print(f"ERROR: Reference image not found: {image}", file=sys.stderr)
            sys.exit(1)
        if path.suffix.lower() not in SUPPORTED_IMAGE_EXTS:
            print(f"ERROR: Unsupported reference image type: {image}", file=sys.stderr)
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
            if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTS
        )
        if not dir_refs:
            print(
                f"ERROR: No supported reference images found in: {reference_dir}",
                file=sys.stderr,
            )
            sys.exit(1)
        refs.extend(dir_refs)

    deduped = []
    seen = set()
    for ref in refs:
        key = str(ref)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ref)
    return deduped


def resolve_generation_mode(requested_mode, reference_paths):
    if requested_mode != "auto":
        return requested_mode
    return "reference" if reference_paths else "inspiration"


def stage_reference_assets(version_id, reference_paths, logo_dir):
    if not reference_paths:
        return []
    references_dir = logo_dir / "references"
    references_dir.mkdir(parents=True, exist_ok=True)
    staged = []
    for idx, source in enumerate(reference_paths, start=1):
        source = Path(source)
        dest_name = f"{version_id}-ref-{idx:02d}{source.suffix.lower()}"
        dest = references_dir / dest_name
        shutil.copy2(source, dest)
        staged.append(str(Path("references") / dest_name))
    return staged


def next_version_num(m):
    nums = []
    for k in m["versions"]:
        match = re.match(r"v(\d+)", k)
        if match:
            nums.append(int(match.group(1)))
    # Also scan files on disk for versions not in manifest
    for f in get_logo_dir().glob("v*"):
        match = re.match(r"v(\d+)", f.stem)
        if match:
            nums.append(int(match.group(1)))
    return max(nums, default=0) + 1


# ── Bootstrap ──────────────────────────────────────────────────────────────

def cmd_bootstrap(args):
    """Scan existing logo files into manifest."""
    m = load_manifest()
    logo_dir = get_logo_dir()
    logo_dir.mkdir(parents=True, exist_ok=True)
    added = 0

    for f in sorted(logo_dir.iterdir()):
        match = re.match(r"(v\d+)", f.stem)
        if not match or f.suffix.lower() not in (".png", ".webp", ".svg", ".jpg"):
            continue
        vid = match.group(1)
        if vid in m["versions"]:
            # Add file to existing version if not already tracked
            entry = m["versions"][vid]
            if f.name not in entry.get("files", []):
                entry.setdefault("files", []).append(f.name)
            continue

        m["versions"][vid] = {
            "prompt": "",
            "model": _guess_model(f.name),
            "aspect_ratio": "",
            "tag": _guess_tag(f.name),
            "files": [f.name],
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S",
                                       time.localtime(f.stat().st_mtime)),
            "score": None,
            "notes": "",
            "status": None,
        }
        added += 1

    save_manifest(m)
    total = len(m["versions"])
    print(f"Bootstrap complete: {added} new versions added, {total} total in manifest")


def _guess_model(filename):
    fn = filename.lower()
    if "recraft" in fn:
        if "svg" in fn:
            return "recraft-v4-svg"
        return "recraft-v4"
    if "flux" in fn:
        return "flux-pro"
    if "ideogram" in fn:
        return "ideogram"
    return ""


def _guess_tag(filename):
    # Strip version prefix and extension, use rest as tag
    stem = re.sub(r"^v\d+-?", "", Path(filename).stem)
    return stem.replace("-", " ").replace("_", " ").strip()


# ── Generate ───────────────────────────────────────────────────────────────

def cmd_generate(args):
    """Generate a logo, auto-version, log to manifest, auto-convert webp→png."""
    m = load_manifest()
    vnum = next_version_num(m)
    vid = f"v{vnum}"
    tag = args.tag or "logo"
    slug = tag.replace(" ", "-").lower()

    model = args.model or "recraft-v4"
    logo_dir = get_logo_dir()
    logo_dir.mkdir(parents=True, exist_ok=True)
    reference_paths = expand_reference_paths(args.image, args.reference_dir)
    mode = resolve_generation_mode(args.mode, reference_paths)

    if mode in {"reference", "hybrid"} and not reference_paths:
        print(
            f"ERROR: Mode '{mode}' requires at least one reference image or --reference-dir.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Determine output extension from model config
    models = json.loads((SCRIPT_DIR / "models.json").read_text())
    model_config = models.get("image", {}).get(model, {})
    ext = model_config.get("output_format", "webp")
    out_file = logo_dir / f"{vid}-{slug}.{ext}"

    # Build generate.py command
    cmd = [
        sys.executable, str(GENERATE_PY), "image",
        "-m", model,
        "-p", args.prompt,
        "-o", str(out_file),
    ]
    if args.aspect_ratio:
        cmd += ["--aspect-ratio", args.aspect_ratio]
    for ref in reference_paths:
        cmd += ["-i", str(ref)]
    if args.preset:
        cmd += ["--preset", args.preset]
    if args.style:
        cmd += ["--style", args.style]

    env = build_env()

    print(f"Generating {vid} ({model}, {args.aspect_ratio or 'default'}, mode={mode})...")
    if reference_paths:
        print(f"Using {len(reference_paths)} reference image(s).")
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(1)

    files = [out_file.name]
    staged_refs = stage_reference_assets(vid, reference_paths, logo_dir)

    # Auto-convert webp → png via sips (macOS)
    if ext == "webp" and sys.platform == "darwin":
        png_file = out_file.with_suffix(".png")
        conv = subprocess.run(
            ["sips", "-s", "format", "png", str(out_file), "--out", str(png_file)],
            capture_output=True, text=True,
        )
        if conv.returncode == 0:
            files.append(png_file.name)
            print(f"Converted: {png_file.name}")

    # Log to manifest
    m["versions"][vid] = {
        "prompt": args.prompt,
        "model": model,
        "mode": mode,
        "aspect_ratio": args.aspect_ratio or "",
        "tag": tag,
        "files": files,
        "reference_images": staged_refs,
        "reference_count": len(staged_refs),
        "reference_dir": str(Path(args.reference_dir).expanduser().resolve()) if args.reference_dir else "",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "score": None,
        "notes": "",
        "status": None,
    }
    save_manifest(m)
    print(f"\nLogged as {vid} in manifest. Use 'feedback {vid} --score N' after review.")
    if staged_refs:
        print(f"Staged references: {', '.join(staged_refs)}")
    # Print the PNG path for easy viewing
    png = [f for f in files if f.endswith(".png")]
    if png:
        print(f"View: {logo_dir / png[0]}")
    else:
        print(f"View: {out_file}")


# ── Feedback ───────────────────────────────────────────────────────────────

def cmd_feedback(args):
    """Record feedback for a version."""
    m = load_manifest()
    vid = args.version
    if vid not in m["versions"]:
        print(f"ERROR: {vid} not in manifest. Run 'bootstrap' first?", file=sys.stderr)
        sys.exit(1)

    entry = m["versions"][vid]
    if args.score is not None:
        entry["score"] = args.score
    if args.notes:
        if entry["notes"]:
            entry["notes"] += f"\n{args.notes}"
        else:
            entry["notes"] = args.notes
    if args.status:
        entry["status"] = args.status
    if args.prompt:
        entry["prompt"] = args.prompt

    # Update reference_versions for favorites
    if args.status == "favorite" and vid not in m.get("reference_versions", []):
        m.setdefault("reference_versions", []).append(vid)

    # Update locked fragments
    if args.lock:
        for frag in args.lock:
            if frag not in m.get("locked_fragments", []):
                m.setdefault("locked_fragments", []).append(frag)

    save_manifest(m)
    star = "★" * (entry["score"] or 0) + "☆" * (5 - (entry["score"] or 0))
    status_icon = {"favorite": "♥", "rejected": "✗"}.get(entry["status"], "")
    print(f"{vid} {star} {status_icon} — updated")


# ── Show ───────────────────────────────────────────────────────────────────

def cmd_show(args):
    """Display manifest overview or version detail."""
    m = load_manifest()
    versions = m["versions"]

    if args.version:
        v = versions.get(args.version)
        if not v:
            print(f"Not found: {args.version}")
            sys.exit(1)
        print(json.dumps({args.version: v}, indent=2))
        return

    # Filter
    items = list(versions.items())
    if args.favorites:
        items = [(k, v) for k, v in items if v.get("status") == "favorite"]
    if args.top:
        items = [(k, v) for k, v in items if v.get("score")]
        items.sort(key=lambda x: -(x[1].get("score") or 0))
        items = items[: args.top]

    if not items:
        print("No versions match filter.")
        return

    # Table output
    print(f"{'VER':<8} {'SCORE':<8} {'STATUS':<10} {'MODE':<12} {'REFS':<6} {'MODEL':<14} {'TAG':<18} {'PROMPT':<32}")
    print("-" * 120)
    for vid, v in sorted(items, key=lambda x: _version_sort_key(x[0])):
        score = "★" * (v.get("score") or 0) if v.get("score") else "—"
        status = v.get("status") or ""
        mode = v.get("mode") or ""
        refs = str(v.get("reference_count") or 0)
        model = v.get("model") or ""
        tag = (v.get("tag") or "")[:18]
        prompt = (v.get("prompt") or "")[:32]
        print(f"{vid:<8} {score:<8} {status:<10} {mode:<12} {refs:<6} {model:<14} {tag:<18} {prompt}")

    # Summary
    total = len(versions)
    scored = sum(1 for v in versions.values() if v.get("score"))
    favs = sum(1 for v in versions.values() if v.get("status") == "favorite")
    print(f"\n{total} versions, {scored} scored, {favs} favorites")

    if m.get("locked_fragments"):
        print(f"\nLocked fragments: {', '.join(m['locked_fragments'])}")
    if m.get("reference_versions"):
        print(f"Reference versions: {', '.join(m['reference_versions'])}")


def _version_sort_key(vid):
    match = re.match(r"v(\d+)", vid)
    return int(match.group(1)) if match else 0


# ── Compare ────────────────────────────────────────────────────────────────

def cmd_compare(args):
    """Generate HTML comparison board for selected versions."""
    m = load_manifest()
    logo_dir = get_logo_dir()

    if args.favorites:
        vids = [k for k, v in m["versions"].items() if v.get("status") == "favorite"]
    elif args.top:
        scored = [(k, v) for k, v in m["versions"].items() if v.get("score")]
        scored.sort(key=lambda x: -(x[1].get("score") or 0))
        vids = [k for k, _ in scored[: args.top]]
    else:
        vids = args.versions

    if not vids:
        print("No versions to compare. Specify versions or use --favorites/--top N")
        sys.exit(1)

    cards_html = []
    for vid in sorted(vids, key=_version_sort_key):
        v = m["versions"].get(vid)
        if not v:
            print(f"WARNING: {vid} not in manifest, skipping", file=sys.stderr)
            continue

        # Find best image file (prefer PNG)
        img_file = None
        for f in v.get("files", []):
            fp = logo_dir / f
            if fp.exists():
                if f.endswith(".png") or img_file is None:
                    img_file = fp

        img_tag = ""
        if img_file and img_file.exists():
            mime = "image/png" if img_file.suffix == ".png" else "image/webp"
            b64 = base64.b64encode(img_file.read_bytes()).decode()
            img_tag = f'<img src="data:{mime};base64,{b64}" alt="{vid}">'
        else:
            img_tag = f'<div class="no-img">No image</div>'

        score = v.get("score")
        stars = ("★" * score + "☆" * (5 - score)) if score else "unscored"
        status = v.get("status") or ""
        css_class = f"card {status}" if status else "card"
        prompt = (v.get("prompt") or "—").replace("<", "&lt;").replace(">", "&gt;")
        notes = (v.get("notes") or "").replace("<", "&lt;").replace(">", "&gt;")
        model = v.get("model") or ""
        ar = v.get("aspect_ratio") or ""

        cards_html.append(f"""
    <div class="{css_class}">
      {img_tag}
      <div class="meta">
        <div class="version">{vid} <span class="score">{stars}</span></div>
        <div class="info">{model} {ar}</div>
        <div class="prompt">{prompt}</div>
        {"<div class='notes'>" + notes + "</div>" if notes else ""}
      </div>
    </div>""")

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Logo Comparison</title>
<style>
  body {{ font-family: system-ui, -apple-system, sans-serif; background: #1a1a1a; color: #eee; margin: 2rem; }}
  h1 {{ font-size: 1.5rem; font-weight: 600; margin-bottom: 1.5rem; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 1.5rem; }}
  .card {{ background: #2a2a2a; border-radius: 12px; overflow: hidden; transition: transform 0.15s; }}
  .card:hover {{ transform: scale(1.02); }}
  .card img {{ width: 100%; display: block; cursor: zoom-in; }}
  .card img:active {{ position: fixed; top: 5vh; left: 5vw; width: 90vw; height: 90vh; object-fit: contain; z-index: 100; background: #000; border-radius: 0; }}
  .no-img {{ height: 200px; display: flex; align-items: center; justify-content: center; background: #333; color: #666; }}
  .meta {{ padding: 1rem; }}
  .version {{ font-size: 1.1rem; font-weight: 700; }}
  .score {{ color: #f5a623; font-size: 0.95rem; }}
  .info {{ font-size: 0.8rem; color: #888; margin-top: 0.25rem; }}
  .prompt {{ font-size: 0.82rem; color: #aaa; margin-top: 0.5rem; line-height: 1.4; max-height: 4.2em; overflow: hidden; }}
  .notes {{ font-size: 0.82rem; color: #8f8; margin-top: 0.5rem; font-style: italic; }}
  .card.favorite {{ border: 2px solid #f5a623; }}
  .card.rejected {{ opacity: 0.4; }}
</style></head>
<body>
<h1>Logo Comparison — {len(vids)} versions</h1>
<div class="grid">{"".join(cards_html)}
</div>
</body></html>"""

    out = logo_dir / "compare.html"
    if args.output:
        out = Path(args.output)
    out.write_text(html)
    print(f"Comparison board: {out} ({len(cards_html)} versions)")
    if sys.platform == "darwin":
        subprocess.run(["open", str(out)], check=False)


# ── Evolve ─────────────────────────────────────────────────────────────────

def cmd_evolve(args):
    """Analyze prompt patterns across scored versions."""
    m = load_manifest()

    scored = [(k, v) for k, v in m["versions"].items()
              if v.get("score") and v.get("prompt")]
    if not scored:
        print("No scored versions with prompts. Score some versions first.")
        sys.exit(1)

    scored.sort(key=lambda x: -(x[1]["score"] or 0))

    print("=== Prompt Evolution Analysis ===\n")

    # Top versions
    print("Top scoring versions:")
    for vid, v in scored[:5]:
        stars = "★" * v["score"]
        print(f"  {vid} ({stars}): \"{v['prompt'][:80]}...\"" if len(v["prompt"]) > 80
              else f"  {vid} ({stars}): \"{v['prompt']}\"")

    # Bottom versions (what to avoid)
    low = [x for x in scored if x[1]["score"] <= 2]
    if low:
        print("\nLow scoring (avoid these patterns):")
        for vid, v in low[:3]:
            stars = "★" * v["score"]
            notes = v.get("notes", "")
            print(f"  {vid} ({stars}): \"{v['prompt'][:60]}\"")
            if notes:
                print(f"    Notes: {notes[:80]}")

    # Locked fragments
    if m.get("locked_fragments"):
        print(f"\nLocked fragments (keep these):")
        for frag in m["locked_fragments"]:
            print(f"  ✓ {frag}")

    # Common words in top prompts vs low prompts
    top_prompts = " ".join(v["prompt"] for _, v in scored[:5])
    low_prompts = " ".join(v["prompt"] for _, v in low[:3]) if low else ""

    top_words = set(re.findall(r'\b\w{4,}\b', top_prompts.lower()))
    low_words = set(re.findall(r'\b\w{4,}\b', low_prompts.lower()))

    good_words = top_words - low_words - {"with", "that", "from", "this", "into"}
    bad_words = low_words - top_words - {"with", "that", "from", "this", "into"}

    if good_words:
        print(f"\nWords in TOP prompts (use more): {', '.join(sorted(good_words)[:15])}")
    if bad_words:
        print(f"Words in LOW prompts (avoid): {', '.join(sorted(bad_words)[:10])}")

    # Feedback summary
    all_notes = [(k, v.get("notes", "")) for k, v in m["versions"].items() if v.get("notes")]
    if all_notes:
        print(f"\nFeedback history ({len(all_notes)} entries):")
        for vid, notes in all_notes[-5:]:
            score = m["versions"][vid].get("score")
            s = f"({score}/5)" if score else ""
            print(f"  {vid} {s}: {notes[:80]}")

    print("\n--- Use 'feedback VERSION --lock \"fragment\"' to lock good prompt fragments ---")


# ── Inspire ────────────────────────────────────────────────────────────────

INSPIRE_URLS = {
    "symbol": "https://logosystem.co/symbol",
    "wordmark": "https://logosystem.co/wordmark",
    "symbol-text": "https://logosystem.co/symbol-and-text",
    "brown": "https://logosystem.co/color/brown",
    "beige": "https://logosystem.co/color/beige",
    "black": "https://logosystem.co/color/black",
    "all": "https://logosystem.co/",
}


def cmd_inspire(args):
    """Open logosystem.co for logo design inspiration and list saved screenshots."""
    logo_dir = get_logo_dir()
    inspo_dir = logo_dir / "inspiration"
    inspo_dir.mkdir(parents=True, exist_ok=True)

    category = (args.category or "symbol").lower()
    url = args.url or INSPIRE_URLS.get(category, INSPIRE_URLS["symbol"])

    if args.list_only:
        # Just list existing inspiration screenshots
        files = sorted(inspo_dir.glob("*"))
        if not files:
            print(f"No inspiration screenshots in {inspo_dir}")
            print(f"Browse {url} and save screenshots there.")
            return
        print(f"Inspiration screenshots ({len(files)}):")
        for f in files:
            print(f"  {f.name}")
        return

    print(f"Opening {url}")
    print(f"Save screenshots to: {inspo_dir}/")
    print()
    print("Tips:")
    print("  - Content is lazy-loaded — scroll before screenshotting")
    print("  - For automated capture, prefer: python3 scripts/collect_inspiration.py --category <name> --open-folder")
    print("  - For non-Logo-System pages, use: python3 scripts/collect_inspiration.py --url <page> --label <name>")
    print("  - Look for: clean geometric marks, pillar/column motifs, flat vector")
    print(f"  - Categories: {', '.join(INSPIRE_URLS.keys())}")

    if sys.platform == "darwin":
        subprocess.run(["open", url], check=False)


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Logo iteration wrapper with structured feedback loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # bootstrap
    sub.add_parser("bootstrap", help="Scan existing files into manifest")

    # generate
    gen = sub.add_parser("generate", aliases=["gen", "g"], help="Generate a new version")
    gen.add_argument("-p", "--prompt", required=True, help="Generation prompt")
    gen.add_argument("-m", "--model", default="recraft-v4", help="Model alias")
    gen.add_argument("--aspect-ratio", "-ar", help="Aspect ratio (e.g., 1:1, 16:9)")
    gen.add_argument("--tag", "-t", help="Short tag for filename (e.g., 'icon', 'banner')")
    gen.add_argument("--mode", choices=["auto", "reference", "inspiration", "hybrid"],
                     default="auto", help="Workflow mode. Auto becomes reference when refs are supplied, otherwise inspiration.")
    gen.add_argument("-i", "--image", action="append",
                     help="Reference image path. Repeat for multiple reference images.")
    gen.add_argument("--reference-dir",
                     help="Directory of approved reference images to include in the generation.")
    gen.add_argument("--preset", help="Prompt preset")
    gen.add_argument("--style", help="Recraft style")

    # feedback
    fb = sub.add_parser("feedback", aliases=["fb", "f"], help="Record feedback")
    fb.add_argument("version", help="Version ID (e.g., v90)")
    fb.add_argument("--score", "-s", type=int, choices=range(1, 6), help="Score 1-5")
    fb.add_argument("--notes", "-n", help="Feedback notes")
    fb.add_argument("--status", choices=["favorite", "rejected"], help="Mark status")
    fb.add_argument("--lock", nargs="+", help="Lock prompt fragments")
    fb.add_argument("--prompt", "-p", help="Backfill prompt text")

    # show
    sh = sub.add_parser("show", aliases=["s"], help="Show manifest")
    sh.add_argument("version", nargs="?", help="Specific version to show")
    sh.add_argument("--favorites", action="store_true", help="Only favorites")
    sh.add_argument("--top", type=int, help="Top N by score")

    # compare
    cmp = sub.add_parser("compare", aliases=["cmp", "c"], help="HTML comparison board")
    cmp.add_argument("versions", nargs="*", help="Versions to compare")
    cmp.add_argument("--favorites", action="store_true", help="Compare all favorites")
    cmp.add_argument("--top", type=int, help="Compare top N")
    cmp.add_argument("--output", "-o", help="Output HTML path")

    # evolve
    sub.add_parser("evolve", aliases=["ev", "e"], help="Analyze prompt patterns")

    # inspire
    ins = sub.add_parser("inspire", aliases=["insp", "i"], help="Browse logo inspiration")
    ins.add_argument("category", nargs="?", default="symbol",
                     help=f"Category: {', '.join(INSPIRE_URLS.keys())}")
    ins.add_argument("--url", help="Open a custom inspiration URL instead of a built-in category")
    ins.add_argument("--label", help="Optional label for external inspiration captures")
    ins.add_argument("--list", dest="list_only", action="store_true",
                     help="Just list saved inspiration screenshots")

    args = parser.parse_args()
    cmd_map = {
        "bootstrap": cmd_bootstrap,
        "generate": cmd_generate, "gen": cmd_generate, "g": cmd_generate,
        "feedback": cmd_feedback, "fb": cmd_feedback, "f": cmd_feedback,
        "show": cmd_show, "s": cmd_show,
        "compare": cmd_compare, "cmp": cmd_compare, "c": cmd_compare,
        "evolve": cmd_evolve, "ev": cmd_evolve, "e": cmd_evolve,
        "inspire": cmd_inspire, "insp": cmd_inspire, "i": cmd_inspire,
    }
    cmd_map[args.command](args)


if __name__ == "__main__":
    main()
