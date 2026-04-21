from __future__ import annotations

from ..runtime import *
from ..runtime_models import recommend_text_model
from ..material_planning import *
from ..agent_review import build_agent_visual_review_packet
from ..generation_flow import *
from ..learnings_memory import promote_blackboard_lessons_to_learnings
from ..pipeline_qa import write_pipeline_qa_report
from ..run_ledger import append_run_event
from ..session_summary import *
from ..media_board import *

def cmd_critique_rubric(args):
    """Return the critique rubric + image path for the calling agent to evaluate."""
    brand_dir = get_brand_dir()
    manifest = load_manifest()
    version_id = args.version
    try:
        rubric = build_agent_visual_review_packet(brand_dir, version_id, manifest=manifest)
    except SystemExit as exc:
        print(json.dumps({"error": str(exc)}))
        sys.exit(1)
    print(json.dumps(rubric, indent=2))


def cmd_submit_critique(args):
    """Accept agent-provided critique JSON for a version."""
    brand_dir = get_brand_dir()
    manifest = load_manifest()
    version_id = args.version
    entry = manifest["versions"].get(version_id)
    if not entry:
        print(json.dumps({"error": f"Version {version_id} not found"}))
        sys.exit(1)

    # Parse critique from file or inline
    critique_input = args.critique_json
    if Path(critique_input).exists():
        vlm_result = json.loads(Path(critique_input).read_text())
    else:
        vlm_result = json.loads(critique_input)

    # Normalize
    vlm_result.setdefault("approved", not bool(vlm_result.get("p1")))
    vlm_result.setdefault("p1", [])
    vlm_result.setdefault("p2", [])
    vlm_result.setdefault("p3", [])
    vlm_result.setdefault("clean", [])
    vlm_result.setdefault("refinement_suggestion", "")
    vlm_result["vlm_available"] = True
    vlm_result["vlm_provider"] = "agent"

    # Save
    vlm_path = brand_dir / "reviews" / f"{version_id}-vlm-critique.json"
    vlm_path.parent.mkdir(parents=True, exist_ok=True)
    vlm_path.write_text(json.dumps(vlm_result, indent=2) + "\n")
    manifest["versions"][version_id]["vlm_critique_path"] = str(vlm_path)
    manifest["versions"][version_id]["vlm_critique"] = {
        "approved": vlm_result.get("approved", False),
        "p1_count": len(vlm_result.get("p1") or []),
        "p2_count": len(vlm_result.get("p2") or []),
        "palette_match": vlm_result.get("palette_match", 0),
        "logo_visible": vlm_result.get("logo_visible", False),
        "text_accuracy": vlm_result.get("text_accuracy", 1.0),
        "text_issues": list(vlm_result.get("text_issues") or []),
        "vlm_available": True,
        "provider": vlm_result.get("vlm_provider", "agent"),
    }
    manifest["versions"][version_id]["visual_review_status"] = "approved" if vlm_result.get("approved", False) else "needs_refinement"
    manifest["versions"][version_id]["visual_review_provider"] = vlm_result.get("vlm_provider", "agent")
    save_manifest(manifest)
    try:
        _, auto_review_path = write_pipeline_qa_report(brand_dir, version_id)
        manifest = load_manifest()
        if version_id in (manifest.get("versions") or {}):
            manifest["versions"][version_id]["auto_review_path"] = str(auto_review_path)
            manifest["versions"][version_id]["auto_review_kind"] = "pipeline_qa"
            save_manifest(manifest)
    except Exception as exc:
        print(f"WARNING: failed to refresh pipeline QA for {version_id}: {exc}", file=sys.stderr)
    append_run_event(
        brand_dir,
        entry.get("workflow_id") or "",
        stage="review",
        event_type="vlm_critique_saved",
        attempt_id=version_id,
        material_type=entry.get("material_type") or "",
        mode=entry.get("mode") or "",
        model=entry.get("model") or "",
        provider=vlm_result.get("vlm_provider") or "agent",
        output_version=version_id,
        status="approved" if vlm_result.get("approved") else "needs_refinement",
        data={"vlm_critique_path": str(vlm_path), "p1": list(vlm_result.get("p1") or []), "p2_count": len(vlm_result.get("p2") or [])},
    )

    # Update blackboard + learning loop
    _, _, profile, identity = load_brand_memory(brand_dir, None, None)
    bb = load_blackboard(brand_dir, profile, identity)
    bb = update_blackboard_learning_summary(
        bb,
        material_type=entry.get("material_type") or "",
        version_id=version_id,
        entry=manifest["versions"][version_id],
        source="submit_critique",
        notes=vlm_result.get("refinement_suggestion") or "",
        score=manifest["versions"][version_id].get("score"),
        status=manifest["versions"][version_id].get("status") or "",
        critique=vlm_result,
    )
    append_blackboard_decision(
        bb,
        agent="critic_agent",
        decision=f"Agent critique of {version_id}: {'approved' if vlm_result.get('approved') else 'needs refinement'} "
                 f"(P1: {len(vlm_result.get('p1') or [])}, palette: {vlm_result.get('palette_match', 'n/a')})",
        confidence=0.9,
        severity="P1" if vlm_result.get("p1") else ("P2" if vlm_result.get("p2") else None),
        data={"vlm_critique_path": str(vlm_path), "approved": vlm_result.get("approved", False)},
    )
    save_blackboard(brand_dir, bb)
    promote_blackboard_lessons_to_learnings(brand_dir, board=bb, material_type=entry.get("material_type") or "")

    model_rec = recommend_text_model(
        vlm_result,
        entry.get("model", ""),
        entry.get("material_type", ""),
        bool(entry.get("reference_images")),
    )
    print(json.dumps({
        "version": version_id,
        "approved": vlm_result.get("approved", False),
        "p1_count": len(vlm_result.get("p1") or []),
        "p2_count": len(vlm_result.get("p2") or []),
        "critique_path": str(vlm_path),
        "model_recommendation": model_rec,
    }, indent=2))

def cmd_feedback(args):
    manifest = load_manifest()
    brand_dir = get_brand_dir()
    vid = args.version
    if vid not in manifest["versions"]:
        print(f"ERROR: {vid} not in manifest. Run 'bootstrap' first?", file=sys.stderr)
        sys.exit(1)
    entry = manifest["versions"][vid]
    if args.score is not None:
        entry["score"] = args.score
    if args.notes:
        entry["notes"] = (entry["notes"] + "\n" if entry.get("notes") else "") + args.notes
    if args.status:
        entry["status"] = args.status
    if args.prompt:
        entry["prompt"] = args.prompt
    if args.status == "favorite" and vid not in manifest.get("reference_versions", []):
        manifest.setdefault("reference_versions", []).append(vid)
    if args.lock:
        for frag in args.lock:
            if frag not in manifest.get("locked_fragments", []):
                manifest.setdefault("locked_fragments", []).append(frag)
    save_manifest(manifest)
    memory = load_iteration_memory(brand_dir)
    memory = capture_feedback_into_iteration_memory(memory, vid, entry, args.notes, args.score, args.status)
    save_iteration_memory(brand_dir, memory)
    append_run_event(
        brand_dir,
        entry.get("workflow_id") or "",
        stage="feedback",
        event_type="feedback_recorded",
        attempt_id=vid,
        material_type=entry.get("material_type") or "",
        mode=entry.get("mode") or "",
        output_version=vid,
        status=entry.get("status") or "",
        notes=args.notes or "",
        data={"score": entry.get("score"), "status": entry.get("status") or "", "locked_fragments": list(args.lock or [])},
    )
    _, _, profile, identity = load_brand_memory(brand_dir, None, None)
    bb = load_blackboard(brand_dir, profile, identity)
    bb = update_blackboard_learning_summary(
        bb,
        material_type=entry.get("material_type") or "",
        version_id=vid,
        entry=entry,
        source="feedback",
        notes=args.notes or "",
        score=entry.get("score"),
        status=entry.get("status") or "",
    )
    append_blackboard_decision(
        bb,
        agent="brand_director",
        decision=f"Recorded feedback for {vid}: score {entry.get('score') if entry.get('score') is not None else 'n/a'} / status {entry.get('status') or 'none'}.",
        confidence=0.82,
        severity="P1" if entry.get("status") == "rejected" else ("P3" if entry.get("status") == "favorite" else None),
        data={"score": entry.get("score"), "status": entry.get("status") or "", "notes": args.notes or ""},
        workflow_id=entry.get("workflow_id") or "",
    )
    save_blackboard(brand_dir, bb)
    promote_blackboard_lessons_to_learnings(brand_dir, board=bb, material_type=entry.get("material_type") or "")
    # M3: disagreement logging — if there's both an agent score and a user
    # score, compute delta + bucket, partition, and append to the
    # disagreement dataset. Failures are non-fatal — feedback is the user-
    # facing operation and must complete even if scoring plumbing breaks.
    try:
        _maybe_log_disagreement(brand_dir, vid, entry, args)
    except Exception as exc:
        # Never fail the user's feedback because of a scoring-side bug
        print(f"disagreement_log_warning: {exc}", file=sys.stderr)
    star = "★" * (entry.get("score") or 0) + "☆" * (5 - (entry.get("score") or 0))
    status_icon = {"favorite": "♥", "rejected": "✗"}.get(entry.get("status"), "")
    print(f"{vid} {star} {status_icon} - updated")


def _maybe_log_disagreement(brand_dir: Path, vid: str, entry: dict, args) -> None:
    """Append to the disagreement dataset if both agent and user scores exist.

    Extracts the agent score from the most recent v2 critique if present
    (rubric_version field), otherwise falls through to the v1 4-axis
    rubric mean if that's what was submitted. v1 critiques don't carry
    a clean integer "overall" score — this function skips v1 records
    rather than invent one.
    """
    user_score = entry.get("score")
    if user_score is None:
        return
    vlm_critique = entry.get("vlm_critique") or {}
    agent_score = _extract_agent_score(brand_dir, vid, vlm_critique)
    if agent_score is None:
        return
    from ..scoring.dataset import (
        append_disagreement,
        compute_partition,
        agreement_bucket as _bucket,
    )
    delta = abs(int(agent_score) - int(user_score))
    partition_tag = compute_partition(vid)
    record = {
        "version_id": vid,
        "material_type": entry.get("material_type") or "",
        "mode": entry.get("mode") or "",
        "model": entry.get("model") or "",
        "agent_score": int(agent_score),
        "user_score": int(user_score),
        "delta": delta,
        "agreement_bucket": _bucket(delta),
        "partition_tag": partition_tag,
        "user_status": entry.get("status") or "",
        "user_notes": args.notes or "",
        "rubric_version": vlm_critique.get("rubric_version") or "",
        "scorer_version": vlm_critique.get("scorer_version") or "",
        "vlm_provider": vlm_critique.get("provider") or vlm_critique.get("vlm_provider") or "",
    }
    append_disagreement(brand_dir, record)
    append_run_event(
        brand_dir,
        entry.get("workflow_id") or "",
        stage="scoring",
        event_type="scorer_disagreement",
        attempt_id=vid,
        material_type=entry.get("material_type") or "",
        mode=entry.get("mode") or "",
        output_version=vid,
        status=record["agreement_bucket"],
        notes=f"delta={delta} agent={agent_score} user={user_score}",
        data={
            "agent_score": record["agent_score"],
            "user_score": record["user_score"],
            "delta": delta,
            "agreement_bucket": record["agreement_bucket"],
            "partition_tag": partition_tag,
        },
    )


def _extract_agent_score(brand_dir: Path, vid: str, vlm_critique: dict) -> int | None:
    """Extract an integer 1-5 agent score from a critique payload.

    v2 packets carry an explicit overall decision encoded as an int.
    v1 packets use the 4-axis mean — we skip those (no clean integer;
    a simulated mean would distort kappa calculations).
    """
    if not isinstance(vlm_critique, dict) or not vlm_critique:
        return None
    # v2 packet: explicit overall score if present
    overall = vlm_critique.get("overall_score") or vlm_critique.get("agent_overall_score")
    if overall is not None:
        try:
            value = int(overall)
            if 1 <= value <= 5:
                return value
        except (TypeError, ValueError):
            return None
    # v2 packet with min-biased aggregation: compute from axis_scores
    axis_scores = vlm_critique.get("axis_scores") or {}
    if isinstance(axis_scores, dict) and axis_scores:
        try:
            min_score = min(int(v) for v in axis_scores.values())
            if 1 <= min_score <= 5:
                return min_score
        except (TypeError, ValueError):
            pass
    # v1 packets — no clean integer; skip
    return None

def _load_version_prompt(vid: str, version: dict, brand_dir: Path) -> str:
    """Load prompt text from sidecar file, falling back to manifest entry."""
    if version.get("prompt"):
        return version["prompt"]
    sidecar = brand_dir / f"{vid}.prompts.json"
    if sidecar.exists():
        try:
            data = json.loads(sidecar.read_text())
            return data.get("prompt", "")
        except (json.JSONDecodeError, OSError):
            pass
    return ""


def cmd_evolve(args):
    manifest = load_manifest()
    brand_dir = get_brand_dir()
    scored = [(k, v) for k, v in manifest["versions"].items() if v.get("score") and (_load_version_prompt(k, v, brand_dir))]
    if not scored:
        print("No scored versions with prompts. Score some versions first.")
        sys.exit(1)
    scored.sort(key=lambda x: -(x[1]["score"] or 0))
    print("=== Brand Prompt Evolution Analysis ===\n")
    print("Top scoring versions:")
    for vid, version in scored[:5]:
        stars = "★" * version["score"]
        prompt = _load_version_prompt(vid, version, brand_dir)
        print(f"  {vid} ({stars}) [{version.get('material_type','')}]: \"{prompt[:100]}{'...' if len(prompt) > 100 else ''}\"")
    low = [x for x in scored if x[1]["score"] <= 2]
    if low:
        print("\nLow scoring (avoid these patterns):")
        for vid, version in low[:3]:
            prompt = _load_version_prompt(vid, version, brand_dir)
            print(f"  {vid} ({'★' * version['score']}): \"{prompt[:80]}\"")
            if version.get("notes"):
                print(f"    Notes: {version['notes'][:100]}")
    if manifest.get("locked_fragments"):
        print("\nLocked fragments (keep these):")
        for frag in manifest["locked_fragments"]:
            print(f"  - {frag}")
    print("\nUse 'feedback VERSION --lock \"fragment\"' to lock good prompt fragments.")

def cmd_validate_set(args):
    payload = load_json_file(Path(args.set).expanduser().resolve())
    report = validate_set_manifest_dict(payload)
    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(f"Set validation: {'ok' if report['ok'] else 'needs work'}")
        print(f"Score: {report['score']}/{report['max_score']}")
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

def cmd_review_brand(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    reviews_dir = brand_dir / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    output = Path(args.output).expanduser() if args.output else reviews_dir / f"{args.version or 'latest'}-review.md"
    cmd = ["--brand-dir", str(brand_dir.resolve()), "--output", str(output.resolve())]
    if args.version:
        cmd += ["--version", args.version]
    run_child_script(BUILD_REVIEW_PACKET_PY, cmd)
    if sys.platform == "darwin" and args.open:
        subprocess.run(["open", str(output)], check=False)
