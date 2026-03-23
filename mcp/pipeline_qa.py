from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .critique_policy import normalize_critique_policy
from .material_planning import evaluate_policy_setup_risks
from .reference_analysis import reference_analysis_confidence, reference_analysis_mode
from .runtime_brand import load_brand_memory
from .runtime_io import dedupe_keep_order, load_json_file
from .runtime_models import MATERIAL_BRAND_POLICIES, role_pack_material_key
from .runtime_support import version_sort_key as _version_sort_key


VISUAL_REVIEW_NOTE = (
    "This report is deterministic pipeline QA only. It does not claim the generated image "
    "was visually reviewed. Use the separate critique tools for agent/VLM image review."
)


def _load_manifest(brand_dir: Path) -> dict:
    path = brand_dir / "manifest.json"
    if not path.exists():
        raise SystemExit(f"Manifest not found: {path}")
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise SystemExit(f"Invalid manifest: {path}")
    value.setdefault("versions", {})
    return value

def _resolve_version(manifest: dict, requested: str | None) -> str:
    if requested:
        if requested not in (manifest.get("versions") or {}):
            raise SystemExit(f"Version not found in manifest: {requested}")
        return requested
    versions = sorted((manifest.get("versions") or {}).keys(), key=_version_sort_key)
    if not versions:
        raise SystemExit("No versions in manifest")
    return versions[-1]


def _resolve_path(value: str | None, *, brand_dir: Path) -> Path | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (brand_dir / raw).resolve()
    return path


def _load_generation_context(brand_dir: Path, version_id: str, entry: dict) -> dict[str, Any]:
    scratchpad_path = _resolve_path(entry.get("generation_scratchpad"), brand_dir=brand_dir)
    scratchpad = load_json_file(scratchpad_path)
    sidecar = load_json_file(brand_dir / f"{version_id}.prompts.json")
    prompt_context = scratchpad.get("prompt_context") or {}
    prompt_review = scratchpad.get("prompt_review") or sidecar.get("prompt_review") or {}
    reference_analysis = (
        prompt_context.get("reference_analysis")
        or scratchpad.get("reference_analysis")
        or sidecar.get("reference_analysis")
        or {}
    )
    plan = scratchpad.get("plan") or {}
    critique = scratchpad.get("plan_critique") or {}
    return {
        "scratchpad_path": scratchpad_path,
        "scratchpad": scratchpad,
        "sidecar": sidecar,
        "prompt_context": prompt_context,
        "prompt_review": prompt_review,
        "reference_analysis": reference_analysis,
        "plan": plan,
        "critique": critique,
    }


def _resolve_reference_analysis_signals(scratchpad: dict, prompt_context: dict, reference_analysis: dict) -> tuple[str, str]:
    mode = (
        str(scratchpad.get("reference_analysis_mode") or "")
        or str(prompt_context.get("reference_analysis_mode") or "")
        or str(reference_analysis.get("reference_analysis_mode") or "")
    )
    confidence = (
        str(scratchpad.get("reference_analysis_confidence") or "")
        or str(prompt_context.get("reference_analysis_confidence") or "")
        or str(reference_analysis.get("reference_analysis_confidence") or "")
    )
    if not mode:
        mode = reference_analysis_mode(reference_analysis)
    if not confidence:
        confidence = reference_analysis_confidence(reference_analysis)
    return mode, confidence


def _build_findings(brand_dir: Path, version_id: str, entry: dict, context: dict[str, Any]) -> dict[str, Any]:
    scratchpad = context["scratchpad"]
    prompt_context = context["prompt_context"]
    prompt_review = context["prompt_review"]
    reference_analysis = context["reference_analysis"]
    plan = context["plan"]
    critique = context["critique"]
    saved_visual_critique = entry.get("vlm_critique") or {}
    saved_visual_critique_path = str(entry.get("vlm_critique_path") or "").strip()
    agent_review_packet_path = str(entry.get("agent_review_path") or "").strip()

    material_type = entry.get("material_type") or scratchpad.get("material_type") or plan.get("material_type") or ""
    material_key = role_pack_material_key(material_type) or material_type.replace("-", "_")
    brand_policy = plan.get("brand_anchor_policy") or MATERIAL_BRAND_POLICIES.get(material_key, {})
    reference_ctx = scratchpad.get("reference_context") or {}
    authoritative_refs = list(
        reference_ctx.get("authoritative_reference_paths")
        or reference_ctx.get("model_transport_reference_paths")
        or reference_ctx.get("passed_reference_paths")
        or []
    )
    model_transport_refs = list(
        reference_ctx.get("model_transport_reference_paths")
        or reference_ctx.get("passed_reference_paths")
        or []
    )
    base_image_reference_path = str(reference_ctx.get("base_image_reference_path") or "").strip()
    selected_roles = prompt_context.get("reference_role_pack") or []
    selected_role_names = [str(item.get("role") or "").strip() for item in selected_roles if str(item.get("role") or "").strip()]
    role_assignment_warnings = dedupe_keep_order(
        [
            str(item).strip()
            for item in (
                list(prompt_context.get("reference_role_assignment_warnings") or [])
                + list(((plan.get("role_pack") or {}).get("role_assignment_warnings") or []))
            )
            if str(item).strip()
        ]
    )

    profile_path = scratchpad.get("profile_path") or None
    identity_path = scratchpad.get("identity_path") or None
    _, _, profile, identity = load_brand_memory(brand_dir, profile_path, identity_path)
    profile_assets = (
        (identity.get("brand_assets") or {})
        if isinstance(identity, dict) and (identity.get("brand_assets") or {})
        else ((profile.get("brand_assets") or {}) if isinstance(profile, dict) else {})
    )
    approved_assets = [str(profile_assets.get(key) or "").strip() for key in ("icon", "wordmark", "lockup")]

    blocking: list[str] = []
    prompt_failures: list[str] = []
    reference_limitations: list[str] = []
    policy_setup_risks: list[str] = []
    clean: list[str] = []

    plan_validation = critique.get("plan_validation") or {}
    blocking.extend(str(item) for item in (plan_validation.get("errors") or []) if str(item).strip())
    blocking.extend(str(item) for item in ((critique.get("checks") or {}).get("blocking") or []) if str(item).strip())
    blocking.extend(str(item) for item in ((scratchpad.get("checks") or {}).get("blocking") or []) if str(item).strip())
    blocking = dedupe_keep_order(blocking)
    critique_policy = normalize_critique_policy(
        scratchpad.get("critique_policy") if isinstance(scratchpad.get("critique_policy"), dict) else scratchpad,
        default_mode="strict",
        entrypoint="pipeline_qa",
        blocking=blocking,
    )

    prompt_failures.extend(str(item) for item in (prompt_review.get("issues") or []) if str(item).strip())
    prompt_failures = dedupe_keep_order(prompt_failures)

    ref_mode, ref_confidence = _resolve_reference_analysis_signals(scratchpad, prompt_context, reference_analysis)
    if ref_mode == "unavailable":
        reference_limitations.append("No reference-analysis payload was attached to the generation scratchpad.")
    elif ref_mode == "deterministic_only":
        reference_limitations.append(
            "Reference analysis ran in deterministic-only mode; reference-role alignment and transferable-mechanics guidance are approximate."
        )
    if ref_confidence in {"low", "medium"} and reference_analysis:
        reference_limitations.append(f"Reference-analysis confidence is {ref_confidence}.")
    reference_limitations.extend(str(item) for item in (reference_analysis.get("warnings") or []) if str(item).strip())
    reference_limitations = dedupe_keep_order(reference_limitations)

    policy_setup_risks.extend(
        evaluate_policy_setup_risks(
            material_type,
            brand_policy=brand_policy,
            selected_roles=selected_roles,
            approved_assets=approved_assets,
            passed_reference_paths=authoritative_refs,
            raw_prompt=(
                scratchpad.get("raw_prompt")
                or entry.get("raw_prompt")
                or (prompt_review.get("resolved_prompt") or "")
            ),
            has_base_image=bool(((scratchpad.get("execution") or {}).get("base_image"))),
            render_backend=scratchpad.get("render_backend") or entry.get("render_backend") or "",
            source_url=scratchpad.get("source_url") or entry.get("source_url") or "",
            entity_type=scratchpad.get("entity_type") or entry.get("entity_type") or "",
            selected_surface_strategy=scratchpad.get("selected_surface_strategy") or ((scratchpad.get("plan") or {}).get("selected_surface_strategy") or ""),
        )
    )
    policy_setup_risks.extend(role_assignment_warnings)
    policy_setup_risks = dedupe_keep_order(policy_setup_risks)

    if not blocking:
        clean.append("No blocking pipeline or policy failures were present in the saved scratchpad metadata.")
    if authoritative_refs:
        clean.append(f"Generation included {len(authoritative_refs)} authoritative reference asset(s).")
        if not model_transport_refs and base_image_reference_path:
            clean.append("No auxiliary image refs were passed via -i because the base image carried product truth directly.")
        elif model_transport_refs:
            clean.append(f"Generation passed {len(model_transport_refs)} auxiliary image reference asset(s) via model transport.")
    if not prompt_failures:
        clean.append("Prompt review found no deterministic prompt-quality failures.")
    if reference_analysis and ref_mode == "vlm_augmented":
        clean.append("Reference analysis included at least one VLM-augmented observation.")
    clean = dedupe_keep_order(clean)

    if blocking:
        next_refinement = blocking[0]
    elif prompt_failures:
        next_refinement = prompt_failures[0]
    elif policy_setup_risks:
        next_refinement = policy_setup_risks[0]
    elif reference_limitations:
        next_refinement = reference_limitations[0]
    else:
        next_refinement = "No deterministic pipeline issues found. Run critique-rubric / submit-critique for visual review before treating this as approved."

    proceeded_despite_blocking = bool(blocking)
    if proceeded_despite_blocking:
        bypass_reason = str(critique_policy.get("bypass_reason") or "").strip()
        if critique_policy.get("bypass_recorded") or not critique_policy.get("blocks_generation", True):
            detail = (
                f"Generation proceeded under an explicitly recorded bypass ({bypass_reason})."
                if bypass_reason
                else "Generation proceeded under an explicitly recorded bypass."
            )
        else:
            detail = (
                "Generation produced an artifact even though blocking critique/scratchpad issues are still present in saved metadata. "
                "Treat this result as a bypassed run until the blocking items are resolved."
            )
        policy_setup_risks.insert(0, detail)
        policy_setup_risks = dedupe_keep_order(policy_setup_risks)

    status = "clean"
    if blocking:
        status = "blocked"
    elif prompt_failures or reference_limitations or policy_setup_risks:
        status = "needs_attention"

    return {
        "version": version_id,
        "status": status,
        "material_type": material_type,
        "material_key": material_key,
        "workflow_mode": scratchpad.get("workflow_mode") or entry.get("mode") or "",
        "model": entry.get("model") or (scratchpad.get("execution") or {}).get("model") or "",
        "critique_mode": critique_policy.get("critique_mode") or "strict",
        "blocking_policy": critique_policy.get("blocking_policy") or "block_generation",
        "bypass_recorded": bool(critique_policy.get("bypass_recorded")),
        "bypass_reason": critique_policy.get("bypass_reason") or "",
        "reference_analysis_mode": ref_mode,
        "reference_analysis_confidence": ref_confidence,
        "proceeded_despite_blocking": proceeded_despite_blocking,
        "visual_review_performed": bool(saved_visual_critique_path),
        "visual_review_provider": str(saved_visual_critique.get("provider") or ""),
        "visual_review_path": saved_visual_critique_path,
        "visual_review_pending": bool(agent_review_packet_path and not saved_visual_critique_path),
        "agent_review_packet_path": agent_review_packet_path,
        "blocking": blocking,
        "prompt_failures": prompt_failures,
        "reference_limitations": reference_limitations,
        "policy_setup_risks": policy_setup_risks,
        "clean": clean,
        "next_refinement": next_refinement,
        "scratchpad_path": str(context["scratchpad_path"] or ""),
        "auto_review_kind": "pipeline_qa",
    }


def render_pipeline_qa_report(report: dict[str, Any]) -> str:
    def section(title: str, items: list[str]) -> list[str]:
        lines = [f"## {title}"]
        if items:
            lines.extend(f"- {item}" for item in items)
        else:
            lines.append("- None.")
        lines.append("")
        return lines

    lines = [
        f"# Pipeline QA report — {report.get('version')}",
        "",
        "## Summary",
        f"- Status: {report.get('status', 'n/a')}",
        f"- Material type: {report.get('material_type') or 'n/a'}",
        f"- Workflow mode: {report.get('workflow_mode') or 'n/a'}",
        f"- Model: {report.get('model') or 'n/a'}",
        f"- Critique mode: {report.get('critique_mode') or 'strict'}",
        f"- Blocking policy: {report.get('blocking_policy') or 'block_generation'}",
        f"- Recorded bypass: {'yes' if report.get('bypass_recorded') else 'no'}",
        f"- Separate visual critique: {'yes' if report.get('visual_review_performed') else 'no'}",
        f"- Reference-analysis mode: {report.get('reference_analysis_mode') or 'unavailable'}",
        f"- Reference-analysis confidence: {report.get('reference_analysis_confidence') or 'low'}",
        f"- Scratchpad: {report.get('scratchpad_path') or 'n/a'}",
        "",
        "## Scope note",
        f"- {VISUAL_REVIEW_NOTE}",
        (
            f"- Separate visual critique artifact: {report.get('visual_review_provider') or 'unknown provider'} at {report.get('visual_review_path')}"
            if report.get("visual_review_performed")
            else (
                f"- Agent review packet is ready at {report.get('agent_review_packet_path')}; an agent still needs to inspect the image and submit critique JSON."
                if report.get("visual_review_pending")
                else "- No separate visual critique artifact is attached to this version yet."
            )
        ),
        "",
    ]
    lines += section("Blocking pipeline/policy failures", list(report.get("blocking") or []))
    lines += section("Prompt-quality failures", list(report.get("prompt_failures") or []))
    lines += section("Reference-analysis confidence limitations", list(report.get("reference_limitations") or []))
    lines += section("Policy-vs-setup risks", list(report.get("policy_setup_risks") or []))
    lines += section("Clean passes", list(report.get("clean") or []))
    lines += [
        "## Next refinement",
        f"- {report.get('next_refinement') or 'No next step recorded.'}",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_pipeline_qa_report(brand_dir: Path, version_id: str | None = None) -> tuple[dict[str, Any], str]:
    brand_dir = Path(brand_dir).expanduser().resolve()
    manifest = _load_manifest(brand_dir)
    resolved_version = _resolve_version(manifest, version_id)
    entry = (manifest.get("versions") or {}).get(resolved_version) or {}
    context = _load_generation_context(brand_dir, resolved_version, entry)
    report = _build_findings(brand_dir, resolved_version, entry, context)
    return report, render_pipeline_qa_report(report)


def write_pipeline_qa_report(brand_dir: Path, version_id: str | None = None, *, output: Path | None = None) -> tuple[dict[str, Any], Path]:
    report, markdown = build_pipeline_qa_report(brand_dir, version_id)
    out_path = Path(output).expanduser().resolve() if output else Path(brand_dir).expanduser().resolve() / "reviews" / f"{report['version']}-auto-review.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown)
    return report, out_path
