from __future__ import annotations

from ..runtime import *
from ..material_planning import *
from ..generation_flow import *
from ..session_summary import *
from ..media_board import *

def cmd_extract_brand(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    output_json = Path(args.output_json).expanduser() if args.output_json else brand_dir / "brand-profile.json"
    output_markdown = Path(args.output_markdown).expanduser() if args.output_markdown else brand_dir / "brand-profile.md"
    identity_json = Path(args.output_identity_json).expanduser() if args.output_identity_json else brand_dir / "brand-identity.json"
    identity_markdown = Path(args.output_identity_markdown).expanduser() if args.output_identity_markdown else brand_dir / "brand-identity.md"
    cmd = [
        "--project-root", str(Path(args.project_root).expanduser().resolve()),
        "--output-json", str(output_json.resolve()),
        "--output-markdown", str(output_markdown.resolve()),
    ]
    if args.brand_name:
        cmd += ["--brand-name", args.brand_name]
    if args.homepage_url:
        cmd += ["--homepage-url", args.homepage_url]
    if args.notes_file:
        cmd += ["--notes-file", str(Path(args.notes_file).expanduser().resolve())]
    if args.reference_dir:
        cmd += ["--reference-dir", str(Path(args.reference_dir).expanduser().resolve())]
    if args.design_tokens_json:
        cmd += ["--design-tokens-json", str(Path(args.design_tokens_json).expanduser().resolve())]
    if args.design_memory_path:
        cmd += ["--design-memory-path", str(Path(args.design_memory_path).expanduser().resolve())]
    run_child_script(EXTRACT_BRAND_PY, cmd)

    build_cmd = [
        "--profile", str(output_json.resolve()),
        "--output-json", str(identity_json.resolve()),
        "--output-markdown", str(identity_markdown.resolve()),
    ]
    run_child_script(BUILD_IDENTITY_PY, build_cmd)
    if getattr(args, "consolidate_inspiration", False) or getattr(args, "inspiration_image", None):
        payload = consolidate_inspiration_memory(
            brand_dir,
            images=list(getattr(args, "inspiration_image", None) or []),
            env=build_env(),
        )
        save_inspiration_memory(brand_dir, payload)

def cmd_build_identity(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    profile = Path(args.profile).expanduser() if args.profile else brand_dir / "brand-profile.json"
    output_json = Path(args.output_json).expanduser() if args.output_json else brand_dir / "brand-identity.json"
    output_markdown = Path(args.output_markdown).expanduser() if args.output_markdown else brand_dir / "brand-identity.md"
    cmd = [
        "--profile", str(profile.resolve()),
        "--output-json", str(output_json.resolve()),
        "--output-markdown", str(output_markdown.resolve()),
    ]
    run_child_script(BUILD_IDENTITY_PY, cmd)

def cmd_describe_brand(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    profile = Path(args.profile).expanduser() if args.profile else brand_dir / "brand-profile.json"
    output = Path(args.output).expanduser() if args.output else brand_dir / "brand-description-prompts.md"
    cmd = ["--profile", str(profile.resolve()), "--output", str(output.resolve())]
    if args.identity:
        cmd += ["--identity", str(Path(args.identity).expanduser().resolve())]
    run_child_script(DESCRIBE_BRAND_PY, cmd)

def cmd_show_identity(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    profile_path, identity_path, profile, identity = load_brand_memory(brand_dir, args.profile, args.identity)
    summary = summarize_identity(profile, identity)
    if args.format == "json":
        print(json.dumps({
            "files": {"profile": str(profile_path), "identity": str(identity_path)},
            "summary": summary,
        }, indent=2))
        return

    print("Brand identity summary\n")
    print(f"Brand: {summary['brand_name'] or 'n/a'}")
    print(f"Summary: {summary['summary'] or 'n/a'}")
    print(f"Homepage: {summary['homepage_url'] or 'n/a'}")
    print(f"Profile: {profile_path}")
    print(f"Identity: {identity_path}")
    print()
    print(f"Tone words: {', '.join(summary['tone_words']) or 'n/a'}")
    print(f"Brand anchors: {', '.join(summary['brand_anchors']) or 'n/a'}")
    print(f"Palette direction: {', '.join(summary['palette_direction']) or 'n/a'}")
    print(f"Typography cues: {', '.join(summary['typography_cues']) or 'n/a'}")
    font_roles = summary.get("typography_roles") or {}
    if font_roles:
        print(f"Typography roles: {', '.join(f'{v} ({k})' for k, v in font_roles.items())}")
    else:
        print("Typography roles: n/a (run extract-brand to detect)")
    print(f"Shape language: {', '.join(summary['shape_language']) or 'n/a'}")
    print(f"Approved graphic devices: {', '.join(summary['approved_graphic_devices']) or 'n/a'}")
    print(f"Forbidden elements: {', '.join(summary['forbidden_elements']) or 'n/a'}")
    print(f"Semantic palette roles: {', '.join(summary['semantic_palette_roles']) or 'n/a'}")
    print(f"Component cues: {', '.join(summary['component_cues']) or 'n/a'}")
    print(f"Framework cues: {', '.join(summary['framework_cues']) or 'n/a'}")
    print(f"Spacing scale: {', '.join(str(item) for item in summary['spacing_scale']) or 'n/a'}")
    print(f"Design-memory source: {summary['design_memory_source'] or 'n/a'}")
    print(f"Design-memory principles: {', '.join(summary['design_memory_principles'][:6]) or 'n/a'}")
    print(f"Design-memory components: {', '.join(summary['design_memory_components'][:6]) or 'n/a'}")
    print(f"Material prompt snippets: {', '.join(summary['material_prompt_snippet_keys']) or 'n/a'}")
    print(f"Material set templates: {', '.join(summary['material_set_template_keys']) or 'n/a'}")
    print(f"Inspiration translation rule: {summary['inspiration_translation_rule'] or 'n/a'}")
    print(f"Non-interface rule: {summary['non_interface_rule'] or 'n/a'}")
    print(f"Copy rule: {summary['copy_rule'] or 'n/a'}")
    print(f"Has imported tokens: {'yes' if summary['token_sources']['has_tokens'] else 'no'}")
    if args.show_prelude:
        print("\nGlobal brand guardrail prelude:\n")
        print(summary["prompt_prelude"] or "n/a")

def cmd_validate_identity(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    profile_path, identity_path, profile, identity = load_brand_memory(brand_dir, args.profile, args.identity)
    report = validate_identity_summary(profile_path, identity_path, profile, identity)

    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print("Brand identity validation\n")
        print(f"Status: {'ok' if report['ok'] else 'needs work'}")
        print(f"Score: {report['score']}/{report['max_score']}")
        print(f"Profile: {profile_path}")
        print(f"Identity: {identity_path}\n")
        print("Checks:")
        for key, passed in report["checks"].items():
            print(f"- {key}: {'pass' if passed else 'missing'}")
        if report["errors"]:
            print("\nErrors:")
            for item in report["errors"]:
                print(f"- {item}")
        if report["warnings"]:
            print("\nWarnings:")
            for item in report["warnings"]:
                print(f"- {item}")
    if args.strict and (report["errors"] or report["warnings"]):
        sys.exit(1)


def cmd_parse_design_memory(args):
    cmd = ["parse", "--path", args.path, "--format", args.format]
    if args.output_json:
        cmd += ["--output-json", args.output_json]
    run_child_script(DESIGN_MEMORY_LITE_PY, cmd)


def cmd_extract_css_variables(args):
    cmd = ["extract-css", "--path", args.path, "--format", args.format, "--max-files", str(args.max_files)]
    if args.output_json:
        cmd += ["--output-json", args.output_json]
    run_child_script(DESIGN_MEMORY_LITE_PY, cmd)


def cmd_diff_design_memory(args):
    cmd = ["diff", "--before", args.before, "--after", args.after, "--format", args.format]
    if args.output_json:
        cmd += ["--output-json", args.output_json]
    run_child_script(DESIGN_MEMORY_LITE_PY, cmd)


def cmd_export_design_tokens(args):
    """Generate design tokens from the active brand's identity and write them
    in one of four formats: css, tailwind, json, or w3c.

    Runs a WCAG audit before emitting and reports violations in the JSON
    response. Errors abort the write unless --skip-audit is passed.
    """
    from ..design_tokens import build_tokens, wcag_audit, emit, EXPORTERS

    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    profile_path, identity_path, profile, identity = load_brand_memory(
        brand_dir, args.profile, args.identity
    )

    fmt = (args.output_format or "css").strip().lower()
    if fmt not in EXPORTERS:
        print(json.dumps({
            "status": "error",
            "error": f"unknown --output-format {fmt!r}; known: {sorted(EXPORTERS)}",
        }, indent=2))
        sys.exit(2)

    tokens = build_tokens(identity or profile or {})
    audit = wcag_audit(tokens)

    if audit.errors and not getattr(args, "skip_audit", False):
        print(json.dumps({
            "status": "error",
            "error": "WCAG audit failed — palette not shippable. Re-run with --skip-audit to override.",
            "errors": audit.errors,
            "warnings": audit.warnings,
            "checks": audit.checks,
        }, indent=2))
        sys.exit(1)

    output = emit(tokens, fmt)

    default_ext = {"css": "css", "tailwind": "js", "json": "json", "w3c": "json"}[fmt]
    default_name = f"design-tokens.{default_ext}"
    out_path = Path(args.out).expanduser() if args.out else brand_dir / "design-tokens" / default_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(output)

    response = {
        "status": "ok" if audit.ok else "ok_with_warnings",
        "format": fmt,
        "output_path": str(out_path.resolve()),
        "bytes_written": len(output),
        "profile_path": str(profile_path) if profile_path else "",
        "identity_path": str(identity_path) if identity_path else "",
        "wcag": {
            "ok": audit.ok,
            "errors": audit.errors,
            "warnings": audit.warnings,
            "checks": audit.checks,
        },
        "tokens_summary": {
            "palette_groups": [
                k for k in (tokens.get("color") or {}).keys()
                if k not in ("semantic", "semantic-dark")
            ],
            "font_size_steps": list((tokens.get("typography") or {}).get("fontSize", {}).keys()),
            "spacing_steps": list((tokens.get("spacing") or {}).keys()),
        },
    }

    if args.format == "json":
        print(json.dumps(response, indent=2))
    else:
        print(f"Exported {fmt} design tokens → {out_path}")
        print(f"  bytes: {len(output)}")
        print(f"  wcag: {'pass' if audit.ok else 'warnings/errors'}")
        for line in audit.report().splitlines():
            print(f"  {line}")
