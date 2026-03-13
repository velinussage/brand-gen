#!/usr/bin/env python3
"""
Unified image and video generation via Replicate API.
Zero external dependencies — stdlib only.

Usage:
  python3 generate.py image -m flux-pro -p "Mountain at sunset, golden hour"
  python3 generate.py video -m kling -p "Gentle head nod" -i photo.png
  python3 generate.py image -m flux-schnell -p "Logo design" --preset logo
  python3 generate.py image -m nano-banana-2 -p "Refine this logo" -i logo.png -i moodboard.png
  python3 generate.py image -m runway-gen4-image -p "Use @brand for subject truth and @composition for layout" -i logo.png --reference-tag brand -i poster-ref.png --reference-tag composition
  python3 generate.py video -m kling-v2.6-motion-control -p "Use the video only for motion attitude" -i logo.png --motion-reference motion.mp4
  python3 generate.py image --list-models
  python3 generate.py video --list-models
"""

import argparse
import base64
import json
import os
import socket
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
ENV_CANDIDATES = [REPO_ROOT / ".env", Path.home() / ".claude" / ".env"]
MODELS = json.loads((SCRIPT_DIR / "models.json").read_text())
PRESETS = json.loads((SCRIPT_DIR / "presets.json").read_text())

API_BASE = "https://api.replicate.com/v1"


def load_env_into_process():
    """Load repo-local .env first, then ~/.claude/.env as fallback."""
    merged = {}
    for path in reversed(ENV_CANDIDATES):
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            merged[key.strip()] = value.strip().strip('\"').strip("'")
    for key, value in merged.items():
        os.environ.setdefault(key, value)


def check_token():
    """Validate REPLICATE_API_TOKEN is set."""
    load_env_into_process()
    token = os.environ.get("REPLICATE_API_TOKEN", "")
    if not token:
        print("ERROR: REPLICATE_API_TOKEN not set.", file=sys.stderr)
        print("Add it to ./.env (repo root) or ~/.claude/.env, or export it in your shell.", file=sys.stderr)
        sys.exit(1)
    return token


def load_image(path):
    """Load image file as data URI for Replicate API."""
    p = Path(path)
    if not p.exists():
        print(f"ERROR: Image not found: {path}", file=sys.stderr)
        sys.exit(1)
    mime_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
    }
    mime = mime_map.get(p.suffix.lower(), "image/png")
    b64 = base64.b64encode(p.read_bytes()).decode()
    return f"data:{mime};base64,{b64}"


def load_media(path, media_kind="image"):
    """Load image/video file as data URI for Replicate API."""
    p = Path(path)
    if not p.exists():
        print(f"ERROR: {media_kind.title()} not found: {path}", file=sys.stderr)
        sys.exit(1)
    mime_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
        ".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm",
        ".m4v": "video/x-m4v",
    }
    mime = mime_map.get(p.suffix.lower())
    if not mime:
        guessed = "video/" if media_kind == "video" else "image/"
        mime = guessed + "octet-stream"
    b64 = base64.b64encode(p.read_bytes()).decode()
    return f"data:{mime};base64,{b64}"


def normalize_image_args(images):
    """Normalize one-or-many --image values into a flat list."""
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


def normalize_reference_tags(tags, count):
    """Normalize optional reference tags to match image count."""
    if not count:
        return []
    flattened = []
    for tag in tags or []:
        if isinstance(tag, (list, tuple)):
            flattened.extend(tag)
        else:
            flattened.append(tag)
    normalized = []
    for idx in range(count):
        raw = flattened[idx] if idx < len(flattened) else f"ref{idx+1}"
        tag = "".join(ch for ch in str(raw) if ch.isalnum())
        if not tag:
            tag = f"ref{idx+1}"
        if not tag[0].isalpha():
            tag = f"r{tag}"
        if len(tag) < 3:
            tag = (tag + "ref")[:3]
        normalized.append(tag[:15])
    return normalized


def apply_preset(prompt, mode, preset_name):
    """Apply a prompt preset (prefix/suffix/negative)."""
    presets = PRESETS.get(mode, {})
    if preset_name not in presets:
        available = ", ".join(presets.keys())
        print(f"WARNING: Unknown preset '{preset_name}'. Available: {available}",
              file=sys.stderr)
        return prompt, None
    preset = presets[preset_name]
    parts = []
    if preset.get("prefix"):
        parts.append(preset["prefix"])
    parts.append(prompt)
    if preset.get("suffix"):
        parts.append(preset["suffix"])
    return " ".join(parts), preset.get("negative")


def create_prediction(token, model_id, input_data, wait=True):
    """POST to Replicate predictions API."""
    url = f"{API_BASE}/models/{model_id}/predictions"
    payload = json.dumps({"input": input_data}).encode()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    if wait:
        headers["Prefer"] = "wait"

    req = urllib.request.Request(url, data=payload, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read())
    except (TimeoutError, socket.timeout):
        if wait:
            print("WARNING: Initial create_prediction wait timed out; retrying in async mode and polling.", file=sys.stderr)
            return create_prediction(token, model_id, input_data, wait=False)
        print("ERROR: Prediction request timed out.", file=sys.stderr)
        sys.exit(1)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            detail = json.loads(body).get("detail", body)
        except json.JSONDecodeError:
            detail = body
        print(f"ERROR ({e.code}): {detail}", file=sys.stderr)
        sys.exit(1)


def poll_prediction(token, url, timeout=600):
    """Poll prediction URL until terminal state."""
    start = time.time()
    retries = 0
    while time.time() - start < timeout:
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {token}"
        })
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                retries += 1
                if retries > 5:
                    print("ERROR: Rate limited too many times", file=sys.stderr)
                    sys.exit(1)
                time.sleep(min(2 ** retries, 30))
                continue
            raise

        status = data.get("status")
        if status == "succeeded":
            return data
        if status in ("failed", "canceled"):
            err = data.get("error", status)
            print(f"ERROR: Prediction {status}: {err}", file=sys.stderr)
            sys.exit(1)

        logs = data.get("logs", "")
        if logs:
            last_line = logs.strip().split("\n")[-1]
            print(f"  ... {last_line[:80]}", end="\r")
        time.sleep(3)

    print("\nERROR: Prediction timed out", file=sys.stderr)
    sys.exit(1)


def download_file(url, output_path):
    """Download file from URL."""
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        Path(output_path).write_bytes(resp.read())
    size_kb = Path(output_path).stat().st_size / 1024
    if size_kb < 1024:
        print(f"Saved: {output_path} ({size_kb:.1f} KB)")
    else:
        print(f"Saved: {output_path} ({size_kb / 1024:.1f} MB)")


def get_output_url(prediction):
    """Extract output URL from prediction result."""
    output = prediction.get("output")
    if isinstance(output, list) and output:
        return output[0]
    if isinstance(output, str):
        return output
    return None


def resolve_model(mode, alias):
    """Look up model config by alias."""
    models = MODELS.get(mode, {})
    if alias not in models:
        available = ", ".join(models.keys())
        print(f"ERROR: Unknown {mode} model '{alias}'.", file=sys.stderr)
        print(f"Available: {available}", file=sys.stderr)
        sys.exit(1)
    return models[alias]


def build_input(model_config, args, mode):
    """Build model-specific input dict."""
    input_data = {}
    field_map = model_config.get("field_map", {})
    defaults = model_config.get("defaults", {})

    # Prompt (with optional preset)
    prompt = args.prompt
    preset_negative = None
    if args.preset:
        prompt, preset_negative = apply_preset(prompt, mode, args.preset)
    input_data["prompt"] = prompt

    # Negative prompt
    neg = args.negative_prompt or preset_negative
    if neg:
        neg_field = field_map.get("negative_prompt", "negative_prompt")
        input_data[neg_field] = neg

    # Input image(s)
    images = normalize_image_args(args.image)
    if images:
        if mode == "image":
            img_field = field_map.get("image")
        else:
            img_field = field_map.get("start_image")
        if not img_field:
            print(
                f"ERROR: Model '{args.model}' does not advertise reference-image support.",
                file=sys.stderr,
            )
            print(
                "Try model 'nano-banana-2' for reference or multi-reference logo variation.",
                file=sys.stderr,
            )
            sys.exit(1)
        max_refs = model_config.get("max_reference_images")
        if max_refs and len(images) > max_refs:
            print(
                f"ERROR: Model '{args.model}' supports at most {max_refs} reference image(s).",
                file=sys.stderr,
            )
            sys.exit(1)
        data_uris = [load_media(image, "image") for image in images]
        if img_field in {"image_input", "reference_images"}:
            input_data[img_field] = data_uris
            tag_field = field_map.get("image_tags")
            if tag_field:
                input_data[tag_field] = normalize_reference_tags(getattr(args, "reference_tag", None), len(data_uris))
        else:
            if len(data_uris) > 1:
                print(
                    f"ERROR: Model '{args.model}' only supports one reference image.",
                    file=sys.stderr,
                )
                print(
                    "Use one --image or switch to 'nano-banana-2' for multi-reference input.",
                    file=sys.stderr,
                )
                sys.exit(1)
            input_data[img_field] = data_uris[0]

    motion_reference = getattr(args, "motion_reference", None)
    motion_field = field_map.get("motion_reference")
    requires_motion_reference = bool(model_config.get("requires_motion_reference"))
    if motion_reference:
        if not motion_field:
            print(
                f"ERROR: Model '{args.model}' does not advertise motion-reference support.",
                file=sys.stderr,
            )
            sys.exit(1)
        input_data[motion_field] = load_media(motion_reference, "video")
    elif requires_motion_reference:
        print(
            f"ERROR: Model '{args.model}' requires --motion-reference.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Dimensions
    if args.width:
        input_data[field_map.get("width", "width")] = args.width
    if args.height:
        input_data[field_map.get("height", "height")] = args.height
    if args.aspect_ratio:
        input_data[field_map.get("aspect_ratio", "aspect_ratio")] = args.aspect_ratio
    if getattr(args, "resolution", None) and (field_map.get("resolution") or "resolution" in defaults):
        input_data[field_map.get("resolution", "resolution")] = args.resolution

    # Generation params
    if args.guidance_scale is not None:
        gs_field = field_map.get("guidance_scale", "guidance_scale")
        input_data[gs_field] = args.guidance_scale
    if args.steps is not None:
        steps_field = field_map.get("steps", "num_inference_steps")
        input_data[steps_field] = args.steps
    if args.seed is not None:
        input_data["seed"] = args.seed

    # Video-specific
    if mode == "video" and args.duration and (field_map.get("duration") or "duration" in defaults):
        dur_field = field_map.get("duration", "duration")
        input_data[dur_field] = args.duration
    if mode == "video" and getattr(args, "motion_mode", None) and field_map.get("motion_mode"):
        mm_field = field_map.get("motion_mode", "mode")
        input_data[mm_field] = args.motion_mode
    if mode == "video" and getattr(args, "character_orientation", None) and field_map.get("character_orientation"):
        co_field = field_map.get("character_orientation", "character_orientation")
        input_data[co_field] = args.character_orientation
    if mode == "video" and getattr(args, "keep_original_sound", False) and field_map.get("keep_original_sound"):
        kos_field = field_map.get("keep_original_sound", "keep_original_sound")
        input_data[kos_field] = True

    # Apply defaults for unset fields
    for key, val in defaults.items():
        if key not in input_data:
            input_data[key] = val

    return input_data


def list_models(mode):
    """Print available models for a mode."""
    models = MODELS.get(mode, {})
    if not models:
        print(f"No {mode} models configured.")
        return

    print(f"\n  {'Alias':<18} {'Cost':<16} Best For")
    print("  " + "-" * 68)
    for alias, config in models.items():
        cost = config.get("cost", "varies")
        best = config.get("best_for", "")
        print(f"  {alias:<18} ${cost:<14} {best}")

    presets = PRESETS.get(mode, {})
    if presets:
        print(f"\n  Presets: {', '.join(presets.keys())}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Generate images and videos via Replicate API",
        epilog=(
            "Examples:\n"
            "  %(prog)s image -m flux-pro -p 'Mountain at sunset, golden hour'\n"
            "  %(prog)s video -m kling -p 'Gentle head nod' -i photo.png\n"
            "  %(prog)s image -m flux-schnell -p 'Logo' --preset logo\n"
            "  %(prog)s image -m nano-banana-2 -p 'Refine this logo' -i logo.png -i moodboard.png\n"
            "  %(prog)s image -m runway-gen4-image -p 'Use @brand for subject truth and @composition for layout' -i logo.png --reference-tag brand -i poster.png --reference-tag composition\n"
            "  %(prog)s video -m kling-v2.6-motion-control -p 'Use the video only for reveal pacing' -i logo.png --motion-reference reveal.mp4\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("mode", choices=["image", "video"],
                        help="Generation mode")
    parser.add_argument("--model", "-m",
                        help="Model alias (e.g., flux-pro, kling)")
    parser.add_argument("--prompt", "-p",
                        help="Generation prompt")
    parser.add_argument("--negative-prompt", "-n",
                        help="Negative prompt")
    parser.add_argument("--image", "-i", action="append",
                        help="Input image path. Repeat for multiple references when the model supports it.")
    parser.add_argument("--reference-tag", action="append",
                        help="Optional tag for each reference image (for models like runway-gen4-image). Repeat in the same order as --image.")
    parser.add_argument("--motion-reference",
                        help="Reference video path for motion-control models.")
    parser.add_argument("--output", "-o",
                        help="Output file path")
    parser.add_argument("--preset",
                        help="Prompt preset (e.g., portrait, cinematic)")
    parser.add_argument("--width", type=int,
                        help="Output width in pixels")
    parser.add_argument("--height", type=int,
                        help="Output height in pixels")
    parser.add_argument("--aspect-ratio", "-ar",
                        help="Aspect ratio (e.g., 16:9, 1:1)")
    parser.add_argument("--resolution",
                        help="Model-specific resolution hint such as 720p or 1080p")
    parser.add_argument("--duration", "-d", type=int,
                        help="Video duration in seconds")
    parser.add_argument("--motion-mode", choices=["std", "pro"],
                        help="Quality mode for compatible motion-control models")
    parser.add_argument("--character-orientation", choices=["image", "video"],
                        help="Orientation behavior for compatible motion-control models")
    parser.add_argument("--keep-original-sound", action="store_true",
                        help="Keep audio from the motion reference video when supported")
    parser.add_argument("--guidance-scale", "-g", type=float,
                        help="Guidance scale")
    parser.add_argument("--steps", type=int,
                        help="Inference steps (image only)")
    parser.add_argument("--seed", type=int,
                        help="Random seed for reproducibility")
    parser.add_argument("--list-models", "-l", action="store_true",
                        help="List available models")

    args = parser.parse_args()

    if args.list_models:
        list_models(args.mode)
        return

    if not args.model:
        parser.error("--model is required (use --list-models to see options)")
    if not args.prompt:
        parser.error("--prompt is required")

    token = check_token()
    model_config = resolve_model(args.mode, args.model)
    input_data = build_input(model_config, args, args.mode)

    # Default output path
    if not args.output:
        ts = time.strftime("%Y%m%d_%H%M%S")
        ext = model_config.get("output_format",
                               "png" if args.mode == "image" else "mp4")
        args.output = f"{args.mode}_{args.model}_{ts}.{ext}"

    replicate_id = model_config["replicate_id"]
    cost = model_config.get("cost", "?")
    print(f"Model: {replicate_id} (${cost})")
    prompt_preview = input_data["prompt"][:100]
    if len(input_data["prompt"]) > 100:
        prompt_preview += "..."
    print(f"Prompt: {prompt_preview}")
    images = normalize_image_args(args.image)
    if images:
        if len(images) == 1:
            print(f"Input: {images[0]}")
        else:
            print(f"Inputs ({len(images)}): {', '.join(images)}")
    if getattr(args, "reference_tag", None):
        print(f"Reference tags: {', '.join(normalize_reference_tags(args.reference_tag, len(images)))}")
    if getattr(args, "motion_reference", None):
        print(f"Motion reference: {args.motion_reference}")
    print("Generating...")

    prediction = create_prediction(token, replicate_id, input_data)

    # Poll if Prefer: wait didn't complete it
    if prediction.get("status") != "succeeded":
        poll_url = prediction.get("urls", {}).get("get")
        if not poll_url:
            print("ERROR: No prediction URL returned", file=sys.stderr)
            sys.exit(1)
        prediction = poll_prediction(token, poll_url)

    output_url = get_output_url(prediction)
    if not output_url:
        print("ERROR: No output in prediction result", file=sys.stderr)
        print(json.dumps(prediction, indent=2), file=sys.stderr)
        sys.exit(1)

    download_file(output_url, args.output)
    print(f"Cost: ~${cost}")


if __name__ == "__main__":
    main()
