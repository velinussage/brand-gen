from __future__ import annotations

import argparse
import json
from typing import Any, Callable

CliBuilder = Callable[..., None]


def _add_subparser(sub: argparse._SubParsersAction, spec: Any) -> argparse.ArgumentParser:
    kwargs = {"help": spec.help}
    if getattr(spec, "aliases", ()):
        kwargs["aliases"] = list(spec.aliases)
    return sub.add_parser(spec.name, **kwargs)


def noop_cli_builder(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    return None


def build_bootstrap_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    return None


def build_types_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    return None


def build_init_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--brand-name", help="Brand key to initialize / activate")
    parser.add_argument("--brand-gen-dir", help="Override .brand-gen location")
    parser.add_argument("--legacy-brand-dir", help="Optional legacy brand-materials directory to migrate")


def build_create_brand_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--name", required=True, help="Brand display name")
    parser.add_argument("--description", help="Short plain-language description of the brand or product")
    parser.add_argument("--tone", action="append", help="Comma-separated tone words; repeat for multiple groups")
    parser.add_argument("--palette", action="append", help="Comma-separated palette values (e.g. #1A6B6B,#C85A2A)")
    parser.add_argument("--keywords", action="append", help="Comma-separated brand/product keywords")
    parser.add_argument("--homepage-url", help="Optional homepage URL")
    parser.add_argument("--voice-description", help="Optional short description of the desired brand voice")
    parser.add_argument("--value-prop", action="append", help="Approved value proposition; repeatable")
    parser.add_argument("--inspiration-image", action="append", help="Inspiration image path to consolidate after brand creation; repeat as needed")
    parser.add_argument("--consolidate-inspiration", action="store_true", help="Run the standalone inspiration-memory consolidation post-step after brand creation")
    parser.add_argument("--brand-gen-dir", help="Override .brand-gen location")


def build_start_testing_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--session-name", help="Session key; defaults to a slug from the working name or timestamp")
    parser.add_argument("--working-name", help="Temporary working brand name for this session")
    parser.add_argument("--brand", help="Optional saved brand to seed the session from")
    parser.add_argument("--goal", help="What this test session is trying to learn or generate")
    parser.add_argument("--brand-gen-dir", help="Override .brand-gen location")


def build_use_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("brand", nargs="?", help="Brand key to activate")
    parser.add_argument("--list", dest="list_only", action="store_true", help="List available brands instead")
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_list_brands_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_extract_brand_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--project-root", default=".", help="Codebase or docs root to inspect")
    parser.add_argument("--brand-name", help="Optional explicit brand name")
    parser.add_argument("--homepage-url", help="Optional homepage URL to record")
    parser.add_argument("--notes-file", help="Optional text file with extra notes")
    parser.add_argument("--reference-dir", help="Optional reference asset directory to include as brand anchors")
    parser.add_argument("--design-tokens-json", help="Optional dembrandt-style design tokens JSON to merge into the profile")
    parser.add_argument("--design-memory-path", help="Optional .design-memory folder or project root containing one; defaults to <project-root>/.design-memory when present")
    parser.add_argument("--inspiration-image", action="append", help="Inspiration image path to consolidate after extraction; repeat as needed")
    parser.add_argument("--consolidate-inspiration", action="store_true", help="Run the standalone inspiration-memory consolidation post-step after extraction")
    parser.add_argument("--output-json", help="Optional output path for the JSON profile")
    parser.add_argument("--output-markdown", help="Optional output path for the Markdown profile")
    parser.add_argument("--output-identity-json", help="Optional output path for brand-identity.json")
    parser.add_argument("--output-identity-markdown", help="Optional output path for brand-identity.md")


def build_build_identity_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--profile", help="Path to brand-profile.json")
    parser.add_argument("--output-json", help="Output path for brand-identity.json")
    parser.add_argument("--output-markdown", help="Output path for brand-identity.md")


def build_describe_brand_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--profile", help="Path to brand-profile.json")
    parser.add_argument("--identity", help="Optional path to brand-identity.json")
    parser.add_argument("--output", help="Output path for the Markdown prompt file")


def build_show_identity_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--profile", help="Optional path to brand-profile.json")
    parser.add_argument("--identity", help="Optional path to brand-identity.json")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--show-prelude", action="store_true", help="Include the full brand guardrail prompt prelude")


def build_show_blackboard_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--profile", help="Optional path to brand-profile.json")
    parser.add_argument("--identity", help="Optional path to brand-identity.json")
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_show_session_summary_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--profile", help="Optional path to brand-profile.json")
    parser.add_argument("--identity", help="Optional path to brand-identity.json")
    parser.add_argument("--limit", type=int, default=5, help="How many recent versions/notes to show")
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_context_snapshot_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--profile", help="Optional path to brand-profile.json")
    parser.add_argument("--identity", help="Optional path to brand-identity.json")
    parser.add_argument("--limit", type=int, default=5, help="How many recent items to inspect when deriving snapshot pointers")
    parser.add_argument("--format", choices=["text", "json"], default="json")


def build_capabilities_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--format", choices=["text", "json"], default="json")


def build_list_aesthetic_capsules_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--material-type", help="Optional material type filter")
    parser.add_argument("--format", choices=["text", "json"], default="json")


def build_suggest_aesthetic_directions_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--material-type", help="Optional material type filter")
    parser.add_argument("--style-handle", default="", help="Optional user style shorthand to bias the branch set")
    parser.add_argument("--count", type=int, default=3, help="How many moodboard branches to return (1-5)")
    parser.add_argument("--format", choices=["text", "json"], default="json")


def build_promote_aesthetic_learning_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--capsule-id", help="Aesthetic capsule id to like/dislike")
    parser.add_argument("--material-type", help="Optional material type context")
    parser.add_argument("--sentiment", choices=["like", "dislike"], default="like")
    parser.add_argument("--note", default="", help="Why this aesthetic worked or failed")
    parser.add_argument("--format", choices=["json", "text"], default="json")


def build_workspace_status_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--profile", help="Optional path to brand-profile.json")
    parser.add_argument("--identity", help="Optional path to brand-identity.json")
    parser.add_argument("--format", choices=["text", "json"], default="json")


def build_improvement_questions_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--profile", help="Optional path to brand-profile.json")
    parser.add_argument("--identity", help="Optional path to brand-identity.json")
    parser.add_argument("--limit", type=int, default=3, help="Max questions to return")
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_show_workflow_lineage_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--workflow-id", required=True, help="Workflow id to inspect")
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_list_runs_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument(
        "--status",
        choices=["in_progress", "blocked", "awaiting_review", "completed"],
        help="Filter by derived run status",
    )
    parser.add_argument("--material-type", help="Filter by material type")
    parser.add_argument("--limit", type=int, default=20, help="Max runs to return (default 20)")
    parser.add_argument("--format", choices=["text", "json"], default="json")


def build_get_run_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--run-id", required=True, help="Workflow id (aka run_id) to project")
    parser.add_argument("--format", choices=["text", "json"], default="json")


def build_run_list_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--status", help="Filter by campaign run status")
    parser.add_argument("--material-type", help="Filter by material type")
    parser.add_argument("--limit", type=int, default=20, help="Max runs to return (default 20)")
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_run_show_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--run-id", required=True, help="Campaign run ID or workflow ID to show")
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_run_replay_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--run-id", required=True, help="Campaign run ID or workflow ID to replay")
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_rebuild_run_index_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--format", choices=["text", "json"], default="text")


def _add_run_or_path_args(parser: argparse.ArgumentParser, *, path_help: str) -> None:
    parser.add_argument("--run-id", help="Workflow id (aka run_id); fetches the most recent matching artifact")
    parser.add_argument("--path", help=path_help)
    parser.add_argument("--format", choices=["json"], default="json")


def build_get_plan_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    _add_run_or_path_args(parser, path_help="Explicit plan-draft JSON path (overrides --run-id)")


def build_get_critique_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    _add_run_or_path_args(parser, path_help="Explicit plan-critique JSON path (overrides --run-id)")


def build_get_scratchpad_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    _add_run_or_path_args(parser, path_help="Explicit generation-scratchpad JSON path (overrides --run-id)")


def build_get_review_packet_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--version-id", required=True, help="Version id (e.g., v7)")
    parser.add_argument("--format", choices=["json"], default="json")


def build_get_version_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--version-id", required=True, help="Version id (e.g., v7)")
    parser.add_argument("--format", choices=["json"], default="json")


def build_compare_versions_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--a", required=True, help="First version id")
    parser.add_argument("--b", required=True, help="Second version id")
    parser.add_argument("--format", choices=["json"], default="json")


def build_switch_brand_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--brand-key", required=True, help="Brand key slug to activate")
    parser.add_argument("--format", choices=["json", "text"], default="json")


def build_migrate_material_taxonomy_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--brand-dir", help="Optional workspace root to migrate. Defaults to the active brand/session workspace.")
    parser.add_argument("--all-saved", action="store_true", help="Migrate all discovered saved-brand workspaces under ./brands and .brand-gen/brands.")
    parser.add_argument("--include-sessions", action="store_true", help="When used with --all-saved, also include .brand-gen testing sessions.")
    parser.add_argument("--apply", action="store_true", help="Write migrated material types back to disk. Default is dry run.")
    parser.add_argument("--format", choices=["json", "text"], default="text")


def build_report_material_taxonomy_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--brand-dir", help="Optional workspace root to inspect. Defaults to the active brand/session workspace.")
    parser.add_argument("--all-saved", action="store_true", help="Report deprecated material-type usage across all discovered saved-brand workspaces under ./brands and .brand-gen/brands.")
    parser.add_argument("--include-sessions", action="store_true", help="When used with --all-saved, also include .brand-gen testing sessions.")
    parser.add_argument("--format", choices=["json", "text"], default="text")


def build_get_pending_reviews_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--limit", type=int, default=20, help="Max pending reviews to return (default 20)")
    parser.add_argument("--format", choices=["json"], default="json")


def build_get_policy_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--format", choices=["json"], default="json")


def build_set_policy_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument(
        "--policy-class",
        required=True,
        choices=["read_only", "local_mutation", "costly_generation", "publish_external"],
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["allow", "require_approval", "deny"],
    )
    parser.add_argument("--format", choices=["json"], default="json")


def build_approve_action_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--pending-id", help="Pending approval id to mark approved")
    parser.add_argument("--tool", help="Tool name to pre-approve (mints + resolves a new pending_id)")
    parser.add_argument("--args-summary", help="Short description of the args being pre-approved")
    parser.add_argument("--requested-by", help="Who requested the approval (operator default)")
    parser.add_argument("--reason", help="Free-text justification")
    parser.add_argument("--format", choices=["json"], default="json")


def build_reject_action_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--pending-id", required=True, help="Pending approval id to reject")
    parser.add_argument("--reason", help="Why the action was rejected")
    parser.add_argument("--format", choices=["json"], default="json")


def build_show_reference_analysis_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--profile", help="Optional path to brand-profile.json")
    parser.add_argument("--identity", help="Optional path to brand-identity.json")
    parser.add_argument("--refresh-reference-analysis", action="store_true", help="Recompute cached reference analysis before showing it")
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_prompts_list_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--format", choices=["text", "json"], default="json")


def build_prompts_get_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("name", help="Prompt-relative resource path under prompts/ (e.g. replicate/image-workflow.md)")
    parser.add_argument("--format", choices=["text", "json"], default="json")


def build_source_knowledge_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--query", default="", help="Optional keyword query over configured brand source markdown")
    parser.add_argument("--limit", type=int, default=8, help="Maximum matching markdown excerpts to return")
    parser.add_argument("--max-chars", type=int, default=900, help="Maximum characters per excerpt")
    parser.add_argument("--profile", help="Optional path to brand-profile.json")
    parser.add_argument("--identity", help="Optional path to brand-identity.json")
    parser.add_argument("--format", choices=["text", "json"], default="json")


def build_reference_rubric_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--profile", help="Optional path to brand-profile.json")
    parser.add_argument("--identity", help="Optional path to brand-identity.json")
    parser.add_argument("--material-type", help="Material type context for analysis")
    parser.add_argument("--format", choices=["text", "json"], default="json")


def build_submit_reference_analysis_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--analysis-json", required=True, help="Path to reference analysis JSON file")
    parser.add_argument("--profile", help="Optional path to brand-profile.json")
    parser.add_argument("--identity", help="Optional path to brand-identity.json")
    parser.add_argument("--format", choices=["text", "json"], default="json")


def build_route_request_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--material-type", help="Target material type if known")
    parser.add_argument("--goal", help="What this artifact or set should accomplish")
    parser.add_argument("--request", help="Freeform request text or brief")
    parser.add_argument("--motion-reference", help="Optional motion reference path to bias routing toward motion")
    parser.add_argument("--set-scope", action="store_true", help="Treat this as a multi-material set request")
    parser.add_argument("--route", help="Agent-selected route key (skip automatic routing)")
    parser.add_argument("--profile", help="Optional path to brand-profile.json")
    parser.add_argument("--identity", help="Optional path to brand-identity.json")
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_resolve_prompt_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("-p", "--prompt", help="Base prompt body")
    parser.add_argument("--plan", help="Optional material plan JSON generated by plan-material")
    parser.add_argument("--profile", help="Optional path to brand-profile.json")
    parser.add_argument("--identity", help="Optional path to brand-identity.json")
    parser.add_argument("--material-type", help="Optional material type to tailor inspiration doctrine loading")
    parser.add_argument("--mode", choices=["auto", "reference", "inspiration", "hybrid"], default="auto", help="Optional workflow mode to inspect material-specific snippet variants")
    parser.add_argument("--disable-brand-guardrails", action="store_true", help="Skip automatic brand guardrail prelude injection")
    parser.add_argument("--refresh-reference-analysis", action="store_true", help="Recompute cached reference analysis before resolving the prompt")
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_review_prompt_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("-p", "--prompt", help="Base prompt body")
    parser.add_argument("--plan", help="Optional material plan JSON generated by plan-material")
    parser.add_argument("--profile", help="Optional path to brand-profile.json")
    parser.add_argument("--identity", help="Optional path to brand-identity.json")
    parser.add_argument("--material-type", help="Optional material type to tailor prompt review")
    parser.add_argument("--mode", choices=["auto", "reference", "inspiration", "hybrid"], default="auto", help="Optional workflow mode to inspect material-specific snippet variants")
    parser.add_argument("--disable-brand-guardrails", action="store_true", help="Skip automatic brand guardrail prelude injection")
    parser.add_argument("--refresh-reference-analysis", action="store_true", help="Recompute cached reference analysis before reviewing the prompt")
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_validate_identity_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--profile", help="Optional path to brand-profile.json")
    parser.add_argument("--identity", help="Optional path to brand-identity.json")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if errors or warnings are present")


def build_parse_design_memory_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--path", required=True, help="Path to a .design-memory folder, file inside it, or project root containing one")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--output-json", help="Optional output path for the parsed design-memory summary")


def build_extract_css_variables_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--path", required=True, help="Path to a .design-memory folder, local file, or project root")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--output-json", help="Optional output path for the extracted CSS variables")
    parser.add_argument("--max-files", type=int, default=250, help="Maximum number of files to scan when the input is a directory")


def build_inspiration_status_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--profile", help="Optional path to brand-profile.json")
    parser.add_argument("--identity", help="Optional path to brand-identity.json")
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_show_rubric_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument(
        "--material-type",
        help="Optional material type to focus on (e.g. landing-hero, system-explainer-illustration, illustrated-brand-world)",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_show_disagreements_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--limit", type=int, default=10, help="Max records to return (default 10)")
    parser.add_argument("--material-type", help="Filter by material type")
    parser.add_argument(
        "--bucket",
        choices=["strong_agreement", "mild_disagreement", "strong_disagreement", "calibration_failure"],
        help="Filter by agreement bucket",
    )
    parser.add_argument(
        "--partition-tag",
        choices=["scorer_training", "iteration_memory"],
        help="Filter by partition tag (GEPA training set or iteration-memory side)",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_rebucket_inspiration_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--source", required=True, help="Source key (as stored in inspiration-memory.json)")
    parser.add_argument(
        "--primary",
        choices=["composition", "narrative_system", "rendering_style"],
        help="Primary bucket this source should be assigned to. Sources with a primary_bucket set get a strong scoring bonus during role-pack selection.",
    )
    parser.add_argument(
        "--scores",
        help='Per-bucket weights as JSON, e.g. \'{"composition": 1.0, "narrative_system": 0.3, "rendering_style": 0.0}\'. Overrides --primary when both are set.',
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear primary_bucket and bucket_scores on the source (revert to legacy bucket_hints ranking).",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_scoring_status_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_diff_design_memory_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--before", required=True, help="Earlier .design-memory folder or project root containing one")
    parser.add_argument("--after", required=True, help="Later .design-memory folder or project root containing one")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--output-json", help="Optional output path for the diff report")


def build_export_design_tokens_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument(
        "--output-format",
        choices=["css", "tailwind", "json", "w3c"],
        default="css",
        help="Target format for the exported design tokens",
    )
    parser.add_argument("--profile", help="Optional path to brand-profile.json")
    parser.add_argument("--identity", help="Optional path to brand-identity.json")
    parser.add_argument(
        "--out",
        help="Optional output file path (default: <brand-dir>/design-tokens/design-tokens.{ext})",
    )
    parser.add_argument(
        "--skip-audit",
        action="store_true",
        help="Emit tokens even if the WCAG AA audit surfaces errors",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_extract_inspiration_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--category", help="Filter by category key")
    parser.add_argument("--source", action="append", help="Specific inspiration source key; repeat as needed")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--timeout", type=int, default=120)


def build_consolidate_inspiration_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--image", action="append", help="Explicit inspiration image path; repeat as needed")
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_inspiration_mode_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("state", nargs="?", help="on|off")


def build_shotlist_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--product-name", help="Product name to use in the shotlist")
    parser.add_argument("--goal", help="Optional marketing goal for the shotlist")
    parser.add_argument("--output", help="Output path for the shotlist markdown")


def build_capture_product_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--url", help="Single URL to capture")
    parser.add_argument("--label", help="Label for --url captures")
    parser.add_argument("--cdp", type=int, metavar="PORT", help="Connect to an already-running Chrome via CDP on this port (e.g. 9222). Start Chrome with: /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222")
    parser.add_argument("--shot", action="append", help="Repeatable label=url pair for multiple captures")
    parser.add_argument("--preset", choices=["example-sage"], help="Expand a named preset shotlist instead of specifying --shot/--url manually")
    parser.add_argument("--out-dir", help="Output directory for screenshots")
    parser.add_argument("--count", type=int, default=1, help="How many scroll positions to capture per shot")
    parser.add_argument("--scroll-px", type=int, default=1400)
    parser.add_argument("--session", help="Explicit agent-browser session id")
    parser.add_argument("--open-folder", action="store_true")


def build_explore_brand_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--profile", help="Optional brand-profile.json path")
    parser.add_argument("--brand-name", help="Explicit brand name")
    parser.add_argument("--business", help="Business or product summary")
    parser.add_argument("--audience", help="Target audience summary")
    parser.add_argument("--tone", help="Comma-separated tone words")
    parser.add_argument("--avoid", help="Comma-separated anti-patterns or avoid words")
    parser.add_argument("--product-context", help="Which product surfaces matter and what product truth should anchor the work")
    parser.add_argument("--material", action="append", help="Target material type; repeat as needed")
    parser.add_argument("--source", action="append", help="Preferred curated source key to constrain suggested example sources; repeat as needed")
    parser.add_argument("--top", type=int, default=4, help="How many directions to include")
    parser.add_argument("--output", help="Markdown output path")
    parser.add_argument("--output-json", help="JSON output path")


def build_plan_set_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--template", default="product-core", help="Template key (product-core, launch-core, brand-system-core, social-launch)")
    parser.add_argument("--set-name", help="Optional explicit set slug/name")
    parser.add_argument("--goal", help="What this set should accomplish")
    parser.add_argument("--surface", help="Primary use surface or campaign context")
    parser.add_argument("--mode", choices=["reference", "inspiration", "hybrid"], default="hybrid")
    parser.add_argument("--profile", help="Optional path to brand-profile.json")
    parser.add_argument("--identity", help="Optional path to brand-identity.json")
    parser.add_argument("--output", help="Output path for the set JSON manifest")
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_validate_brand_fit_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--plan", help="Path to a material plan JSON")
    parser.add_argument("--set", help="Path to a set manifest JSON")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--strict", action="store_true")


def build_validate_set_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--set", required=True, help="Path to a set manifest JSON")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--strict", action="store_true")


def build_generate_set_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--set", required=True, help="Path to a set manifest JSON")
    parser.add_argument("--only", action="append", help="Only generate these material types; repeat as needed")
    parser.add_argument("--skip", action="append", help="Skip these material types; repeat as needed")
    parser.add_argument("--model", help="Optional model override passed through to generate")
    parser.add_argument("--aspect-ratio", help="Optional aspect ratio override passed through to generate")
    parser.add_argument("--parallel", action="store_true", help="Generate independent materials in parallel using a thread pool")
    parser.add_argument("--workers", type=int, default=3, help="Max parallel workers when --parallel is set (default: 3, max: 5)")


def build_review_brand_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("version", nargs="?", help="Version to review; defaults to latest")
    parser.add_argument("--output", help="Optional output path for the review markdown")
    parser.add_argument("--open", action="store_true", help="Open the review markdown after writing it")


def build_suggest_role_pack_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--material-type", required=True, help="Material type to inspect (e.g. site-pattern-tile, sticker-family, proof-poster)")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--top", type=int, default=3, help="How many suggestions to show per role")


def build_plan_material_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--material-type", required=True, help="Material type to plan. Prefer the new taxonomy (e.g. system-explainer-illustration, editorial-metaphor-illustration, proof-poster, site-pattern-tile). Deprecated aliases like concept-illustration, campaign-poster, and pattern-system are still accepted.")
    parser.add_argument("--mode", choices=["reference", "inspiration", "hybrid"], default="hybrid", help="Workflow mode for the plan")
    parser.add_argument("--mechanic", help="The one system mechanic or reveal move to emphasize")
    parser.add_argument("--purpose", help="What job this material should do")
    parser.add_argument("--target-surface", help="Where this material will be used")
    parser.add_argument("--product-truth-expression", help="What concrete product truth this material must express")
    parser.add_argument("--abstraction-level", choices=["low", "medium", "high"], help="How abstract this material is allowed to be")
    parser.add_argument("--render-backend", choices=["native", "html"], default="native", help="Rendering backend; use html to plan governed-text share cards")
    parser.add_argument("--source-url", help="Real product/app URL to plan against")
    parser.add_argument("--entity-type", help="Entity type for governed share-card planning")
    parser.add_argument("--design-variance", type=int, default=5, help="Design variance dial (1-10) used when selecting a surface strategy")
    parser.add_argument("--complexity-tier", choices=["simple", "moderate", "dense"], default=None, help="Cap named-elements in the brief: simple (≤2) / moderate (≤4) / dense (unlimited). Default: per-material (simple for illustration-first materials such as system-explainer-illustration or illustrated-brand-world, moderate otherwise).")
    parser.add_argument("--prompt-subject", default=None, help="Concrete subject phrase for the 5-slot template (e.g. 'two hands placing clay pots on a drying board')")
    parser.add_argument("--prompt-style-descriptors", default=None, help="Style descriptors for the 5-slot template (e.g. 'Kodak Portra 400 film grain, charcoal woodcut, hand-inked botanical plate')")
    parser.add_argument("--prompt-lighting", default=None, help="Lighting for the 5-slot template (e.g. 'golden hour raking light, chiaroscuro, diffused north daylight')")
    parser.add_argument("--prompt-camera", default=None, help="Camera/framing for the 5-slot template (e.g. '85mm portrait lens, bird's eye view, 16:9 letterbox')")
    parser.add_argument("--prompt-composition", default=None, help="Explicit composition directive for the 5-slot template; overrides surface-strategy defaults")
    parser.add_argument("--prompt-details", default=None, help="Detail boosters for the 5-slot template (e.g. 'shallow depth of field, warm palette, matte finish')")
    parser.add_argument("--visual-density", type=int, default=None, help="Spatial density dial (1-10): 1-3 Art Gallery (huge negative space, one gesture), 4-7 Daily App (editorial spacing), 8-10 Cockpit (packed data, 1px separators). Default: per-material (4 for illustration-first, 5 otherwise).")
    parser.add_argument("--aesthetic-commitment", choices=["minimal", "maximal", "editorial", "brutalist", "organic", "industrial", "retro_futurist", "playful", "luxury"], default=None, help="Pick one axis extreme rather than hedging with mild adjectives. Required for distinctive output. Commitment (not intensity) separates specific aesthetics from generic premium-AI-brand mood.")
    parser.add_argument("--aesthetic-capsule", default=None, help="Curated aesthetic capsule id or label (e.g. warm-editorial-system-illustration). Overrides automatic capsule selection.")
    parser.add_argument("--style-handle", default=None, help="Human style shorthand to compile into a capsule (e.g. 'ghibli aesthetic' -> safe storybook-animation descriptors).")
    parser.add_argument("--preserve", action="append", help="Thing that must stay fixed; repeat as needed")
    parser.add_argument("--push", action="append", help="Thing that can be pushed or explored; repeat as needed")
    parser.add_argument("--ban", action="append", help="Thing that must not appear; repeat as needed")
    parser.add_argument("--pick", action="append", help="Explicit role pick in the form role=source-key-or-path; repeat as needed")
    parser.add_argument("--prompt-seed", help="Optional explicit prompt seed; otherwise one is generated")
    parser.add_argument("--profile", help="Optional brand-profile.json path")
    parser.add_argument("--identity", help="Optional brand-identity.json path")
    parser.add_argument("--output", help="Optional output path for the plan JSON")
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_plan_draft_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--material-type", required=True, help="Material type to plan. Prefer the new taxonomy (e.g. system-explainer-illustration, editorial-metaphor-illustration, proof-poster, site-pattern-tile). Deprecated aliases like concept-illustration, campaign-poster, and pattern-system are still accepted.")
    parser.add_argument("--mode", choices=["reference", "inspiration", "hybrid"], default="hybrid", help="Workflow mode for the draft")
    parser.add_argument("--mechanic", help="The one system mechanic or reveal move to emphasize")
    parser.add_argument("--purpose", help="What job this material should do")
    parser.add_argument("--target-surface", help="Where this material will be used")
    parser.add_argument("--product-truth-expression", help="What concrete product truth this material must express")
    parser.add_argument("--abstraction-level", choices=["low", "medium", "high"], help="How abstract this material is allowed to be")
    parser.add_argument("--render-backend", choices=["native", "html"], default="native", help="Rendering backend; use html to plan governed-text share cards")
    parser.add_argument("--source-url", help="Real product/app URL to plan against")
    parser.add_argument("--entity-type", help="Entity type for governed share-card planning")
    parser.add_argument("--design-variance", type=int, default=5, help="Design variance dial (1-10) used when selecting a surface strategy")
    parser.add_argument("--complexity-tier", choices=["simple", "moderate", "dense"], default=None, help="Cap named-elements in the brief: simple (≤2) / moderate (≤4) / dense (unlimited). Default: per-material (simple for illustration-first materials such as system-explainer-illustration or illustrated-brand-world, moderate otherwise).")
    parser.add_argument("--prompt-subject", default=None, help="Concrete subject phrase for the 5-slot template (e.g. 'two hands placing clay pots on a drying board')")
    parser.add_argument("--prompt-style-descriptors", default=None, help="Style descriptors for the 5-slot template (e.g. 'Kodak Portra 400 film grain, charcoal woodcut, hand-inked botanical plate')")
    parser.add_argument("--prompt-lighting", default=None, help="Lighting for the 5-slot template (e.g. 'golden hour raking light, chiaroscuro, diffused north daylight')")
    parser.add_argument("--prompt-camera", default=None, help="Camera/framing for the 5-slot template (e.g. '85mm portrait lens, bird's eye view, 16:9 letterbox')")
    parser.add_argument("--prompt-composition", default=None, help="Explicit composition directive for the 5-slot template; overrides surface-strategy defaults")
    parser.add_argument("--prompt-details", default=None, help="Detail boosters for the 5-slot template (e.g. 'shallow depth of field, warm palette, matte finish')")
    parser.add_argument("--visual-density", type=int, default=None, help="Spatial density dial (1-10): 1-3 Art Gallery (huge negative space, one gesture), 4-7 Daily App (editorial spacing), 8-10 Cockpit (packed data, 1px separators). Default: per-material (4 for illustration-first, 5 otherwise).")
    parser.add_argument("--aesthetic-commitment", choices=["minimal", "maximal", "editorial", "brutalist", "organic", "industrial", "retro_futurist", "playful", "luxury"], default=None, help="Pick one axis extreme rather than hedging with mild adjectives. Required for distinctive output. Commitment (not intensity) separates specific aesthetics from generic premium-AI-brand mood.")
    parser.add_argument("--aesthetic-capsule", default=None, help="Curated aesthetic capsule id or label (e.g. warm-editorial-system-illustration). Overrides automatic capsule selection.")
    parser.add_argument("--style-handle", default=None, help="Human style shorthand to compile into a capsule (e.g. 'ghibli aesthetic' -> safe storybook-animation descriptors).")
    parser.add_argument("--preserve", action="append", help="Thing that must stay fixed; repeat as needed")
    parser.add_argument("--push", action="append", help="Thing that can be pushed or explored; repeat as needed")
    parser.add_argument("--ban", action="append", help="Thing that must not appear; repeat as needed")
    parser.add_argument("--pick", action="append", help="Explicit role pick in the form role=source-key-or-path; repeat as needed")
    parser.add_argument("--prompt-seed", help="Optional explicit prompt seed; otherwise one is generated")
    parser.add_argument("--profile", help="Optional brand-profile.json path")
    parser.add_argument("--identity", help="Optional brand-identity.json path")
    parser.add_argument("--output", help="Optional output path for the plan draft JSON")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--base-image", help="Path to an image to edit or overlay on during generation")


def build_critique_plan_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--plan", required=True, help="Path to a material plan JSON or plan-draft JSON")
    parser.add_argument("-p", "--prompt", help="Optional prompt override for the critique pass")
    parser.add_argument("--material-type", help="Optional material type override")
    parser.add_argument("--generation-mode", choices=["auto", "image", "video"], default="auto")
    parser.add_argument("--mode", choices=["auto", "reference", "inspiration", "hybrid"], default="auto")
    parser.add_argument("-m", "--model", help="Optional model override")
    parser.add_argument("--aspect-ratio", "-ar")
    parser.add_argument("--resolution")
    parser.add_argument("--duration", "-d", type=int)
    parser.add_argument("--tag", "-t")
    parser.add_argument("-i", "--image", action="append")
    parser.add_argument("--reference-dir")
    parser.add_argument("--motion-reference")
    parser.add_argument("--motion-mode", choices=["std", "pro"])
    parser.add_argument("--character-orientation", choices=["image", "video"])
    parser.add_argument("--keep-original-sound", action="store_true")
    parser.add_argument("--preset")
    parser.add_argument("--negative-prompt", "-n")
    parser.add_argument("--style")
    parser.add_argument("--make-gif", action="store_true")
    parser.add_argument("--profile")
    parser.add_argument("--identity")
    parser.add_argument("--disable-brand-guardrails", action="store_true")
    parser.add_argument("--critique-mode", choices=["advisory", "strict"], default="advisory", help="Whether this standalone critique should only report issues or also exit non-zero on blocking findings")
    parser.add_argument("--output", help="Optional output path for the plan critique JSON")
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_build_generation_scratchpad_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("-p", "--prompt", help="Generation prompt override")
    parser.add_argument("--plan", required=True, help="Material plan JSON or plan-draft JSON")
    parser.add_argument("--material-type", help="Material type override")
    parser.add_argument("--generation-mode", choices=["auto", "image", "video"], default="auto")
    parser.add_argument("--mode", choices=["auto", "reference", "inspiration", "hybrid"], default="auto")
    parser.add_argument("-m", "--model")
    parser.add_argument("--aspect-ratio", "-ar")
    parser.add_argument("--resolution")
    parser.add_argument("--duration", "-d", type=int)
    parser.add_argument("--source-version", help="Version ID this scratchpad derives from; used for lineage and text-failure learning checks")
    parser.add_argument("--tag", "-t")
    parser.add_argument("-i", "--image", action="append")
    parser.add_argument("--reference-dir")
    parser.add_argument("--motion-reference")
    parser.add_argument("--motion-mode", choices=["std", "pro"])
    parser.add_argument("--character-orientation", choices=["image", "video"])
    parser.add_argument("--keep-original-sound", action="store_true")
    parser.add_argument("--preset")
    parser.add_argument("--negative-prompt", "-n")
    parser.add_argument("--style")
    parser.add_argument("--make-gif", action="store_true")
    parser.add_argument("--profile")
    parser.add_argument("--identity")
    parser.add_argument("--disable-brand-guardrails", action="store_true")
    parser.add_argument("--render-backend", choices=["native", "html"], default="native", help="Rendering backend; use html for structured share-card generation")
    parser.add_argument("--source-url", help="Real product/app URL to extract structured share-card text from")
    parser.add_argument("--entity-type", help="Entity type for HTML share cards (prompt, skill, library, proposal, community, dao, update)")
    parser.add_argument("--headline", help="Explicit share-card headline override")
    parser.add_argument("--subhead", help="Explicit share-card subhead override")
    parser.add_argument("--cta", help="CTA label override for HTML share cards")
    parser.add_argument("--proof-title", help="Explicit proof-module title override")
    parser.add_argument("--proof-excerpt", help="Explicit proof-module excerpt override")
    parser.add_argument("--proof-row", help="Explicit proof-module footer/detail row override")
    parser.add_argument("--proof-meta", action="append", help="Proof metadata row/chip for HTML share cards; repeat as needed")
    parser.add_argument("--proof-crop-path", help="Screenshot crop or product image path used as supporting texture inside the proof module")
    parser.add_argument("--design-variance", type=int, default=5, help="Design variance dial (1-10): 1-3 clean centered, 4-7 editorial asymmetry, 8-10 strong asymmetry")
    parser.add_argument("--complexity-tier", choices=["simple", "moderate", "dense"], default=None, help="Cap named-elements in the brief: simple (≤2) / moderate (≤4) / dense (unlimited). Default: per-material (simple for illustration-first materials such as system-explainer-illustration or illustrated-brand-world, moderate otherwise).")
    parser.add_argument("--prompt-subject", default=None, help="Concrete subject phrase for the 5-slot template (e.g. 'two hands placing clay pots on a drying board')")
    parser.add_argument("--prompt-style-descriptors", default=None, help="Style descriptors for the 5-slot template (e.g. 'Kodak Portra 400 film grain, charcoal woodcut, hand-inked botanical plate')")
    parser.add_argument("--prompt-lighting", default=None, help="Lighting for the 5-slot template (e.g. 'golden hour raking light, chiaroscuro, diffused north daylight')")
    parser.add_argument("--prompt-camera", default=None, help="Camera/framing for the 5-slot template (e.g. '85mm portrait lens, bird's eye view, 16:9 letterbox')")
    parser.add_argument("--prompt-composition", default=None, help="Explicit composition directive for the 5-slot template; overrides surface-strategy defaults")
    parser.add_argument("--prompt-details", default=None, help="Detail boosters for the 5-slot template (e.g. 'shallow depth of field, warm palette, matte finish')")
    parser.add_argument("--visual-density", type=int, default=None, help="Spatial density dial (1-10): 1-3 Art Gallery (huge negative space, one gesture), 4-7 Daily App (editorial spacing), 8-10 Cockpit (packed data, 1px separators). Default: per-material (4 for illustration-first, 5 otherwise).")
    parser.add_argument("--aesthetic-commitment", choices=["minimal", "maximal", "editorial", "brutalist", "organic", "industrial", "retro_futurist", "playful", "luxury"], default=None, help="Pick one axis extreme rather than hedging with mild adjectives. Required for distinctive output. Commitment (not intensity) separates specific aesthetics from generic premium-AI-brand mood.")
    parser.add_argument("--aesthetic-capsule", default=None, help="Curated aesthetic capsule id or label (e.g. warm-editorial-system-illustration). Overrides automatic capsule selection.")
    parser.add_argument("--style-handle", default=None, help="Human style shorthand to compile into a capsule (e.g. 'ghibli aesthetic' -> safe storybook-animation descriptors).")
    parser.add_argument("--layout-spec", type=json.loads, default=None, help='JSON layout spec override, e.g. \'{"columns":2,"alignment":"left"}\'')
    parser.add_argument("--skip-extraction", action="store_true", help="Skip cached reference analysis during scratchpad assembly")
    parser.add_argument("--refresh-reference-analysis", action="store_true", help="Recompute cached reference analysis even if a cache entry exists")
    parser.add_argument("--critique-mode", choices=["advisory", "strict"], default="strict", help="How blocking critique findings should be treated when building the scratchpad")
    parser.add_argument("--allow-blocking", action="store_true", help="Write the scratchpad even if blocking issues remain")
    parser.add_argument("--output", help="Optional output path for the generation scratchpad JSON")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--base-image", help="Path to an image to edit or overlay on during generation")


def build_ideate_material_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--material-type", required=True, help="Material type to ideate")
    parser.add_argument("--mode", choices=["reference", "inspiration", "hybrid"], default="hybrid")
    parser.add_argument("--goal", help="Optional goal for this material")
    parser.add_argument("--use-surface", help="Where this material will appear first")
    parser.add_argument("--concern", help="Main concern or tension to resolve")
    parser.add_argument("--profile", help="Optional brand-profile.json path")
    parser.add_argument("--identity", help="Optional brand-identity.json path")
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_ideate_copy_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--material-type", required=True, help="Material type to ideate copy for")
    parser.add_argument("--goal", help="What this material should accomplish")
    parser.add_argument("--surface", help="Primary surface, channel, or placement")
    parser.add_argument("--profile", help="Optional brand-profile.json path")
    parser.add_argument("--identity", help="Optional brand-identity.json path")
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_ideate_messaging_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--profile", help="Optional brand-profile.json path")
    parser.add_argument("--identity", help="Optional brand-identity.json path")
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_promote_messaging_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--include-copy-notes", action="store_true", help="Also promote iteration messaging/copy notes as messaging insights")
    parser.add_argument("--profile", help="Optional brand-profile.json path")
    parser.add_argument("--identity", help="Optional brand-identity.json path")


def build_update_messaging_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--tagline", help="Set the brand tagline")
    parser.add_argument("--elevator", help="Set the elevator pitch (1-2 sentences)")
    parser.add_argument("--voice-description", help="Set the brand voice description")
    parser.add_argument("--add-value-prop", action="append", help="Add an approved value proposition; repeat for multiple")
    parser.add_argument("--add-headline", action="append", help="Add an approved headline to the copy bank; repeat for multiple")
    parser.add_argument("--add-slogan", action="append", help="Add an approved slogan; repeat for multiple")
    parser.add_argument("--add-subheadline", action="append", help="Add an approved subheadline; repeat for multiple")
    parser.add_argument("--profile", help="Optional brand-profile.json path")
    parser.add_argument("--identity", help="Optional brand-identity.json path")
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_show_iteration_memory_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_update_iteration_memory_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--version", help="Optional version id related to the note")
    parser.add_argument("--material-type", help="Optional material type for material-specific notes")
    parser.add_argument("--kind", choices=["brand", "copy", "messaging", "material"], default="brand")
    parser.add_argument("--note", help="General note to add")
    parser.add_argument("--negative", help="Add a negative example summary")
    parser.add_argument("--positive", help="Add a positive example summary")
    parser.add_argument("--score", type=int)
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_append_forbidden_pattern_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--pattern", required=True, help="Pattern text to ban (for example: 'purple gradients')")
    parser.add_argument("--reason", default="", help="Why this pattern should be banned")
    parser.add_argument("--source-version", default="", help="Version id where this pattern was observed")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    parser.add_argument("--format", choices=["text", "json"], default="json")


def build_promote_learning_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument(
        "--bucket",
        required=True,
        choices=["modelPreferences", "colorInsights", "compositionPatterns", "failurePatterns", "messagingInsights", "audienceInsights"],
        help="Learnings bucket to append to",
    )
    parser.add_argument("--text", required=True, help="Learning text to promote")
    parser.add_argument("--material-type", default="", help="Optional material type context")
    parser.add_argument("--evidence-version", action="append", help="Evidence version id; repeat as needed")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    parser.add_argument("--format", choices=["text", "json"], default="json")


def build_add_aesthetic_capsule_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--id", required=True, help="Capsule id (machine-readable, e.g. 'sage-doric-route-architecture')")
    parser.add_argument("--label", default="", help="Human-readable label")
    parser.add_argument("--safe-handle", default="", help="Compressed style handle phrase the prompt will use")
    parser.add_argument("--internal-handle", action="append", default=[], help="Repeatable: alternate handle/synonym")
    parser.add_argument("--material-type", action="append", default=[], help="Repeatable: material type the capsule applies to")
    parser.add_argument("--use-when", action="append", default=[], help="Repeatable: 'use this capsule when' criterion")
    parser.add_argument("--avoid-when", action="append", default=[], help="Repeatable: 'avoid this capsule when' criterion")
    parser.add_argument("--style-strength-default", default="", help="Default style strength 0.0-1.0")
    parser.add_argument("--medium", default="", help="style_description.medium")
    parser.add_argument("--palette", default="", help="style_description.palette")
    parser.add_argument("--line", default="", help="style_description.line")
    parser.add_argument("--lighting", default="", help="style_description.lighting")
    parser.add_argument("--composition", default="", help="style_description.composition")
    parser.add_argument("--density", default="", help="style_description.density")
    parser.add_argument("--texture", default="", help="style_description.texture")
    parser.add_argument("--motif", action="append", default=[], help="Repeatable: motifs entry")
    parser.add_argument("--positive-term", action="append", default=[], help="Repeatable: positive_prompt_terms entry")
    parser.add_argument("--negative-term", action="append", default=[], help="Repeatable: negative_prompt_terms entry")
    parser.add_argument("--style-axis", action="append", default=[], help="Repeatable: style_axes entry")
    parser.add_argument("--style-role", default="", help="reference_roles.style")
    parser.add_argument("--composition-role", default="", help="reference_roles.composition")
    parser.add_argument("--brand-role", default="", help="reference_roles.brand")
    parser.add_argument("--negative-role", default="", help="reference_roles.negative")
    parser.add_argument("--reason", default="", help="Why this capsule is being added/updated (audit trail)")
    parser.add_argument("--source-version", default="", help="Version id where this capsule was found necessary")
    parser.add_argument("--dry-run", action="store_true", help="Show the resulting capsule without writing")
    parser.add_argument("--format", choices=["text", "json"], default="json")


def build_append_custom_scratchpad_note_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--section", required=True, choices=["global", "motion", "typography", "composition"], help="Scratchpad section to append under")
    parser.add_argument("--text", required=True, help="Bullet text to append")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    parser.add_argument("--force", action="store_true", help="Override read_only_after frontmatter on the target markdown")
    parser.add_argument("--format", choices=["text", "json"], default="json")


def build_contract_status_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--limit-mutations", type=int, default=10, help="How many recent mutation events to show")
    parser.add_argument("--format", choices=["text", "json"], default="json")


def build_render_iteration_memory_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--dry-run", action="store_true", help="Detect drift without writing")
    parser.add_argument("--format", choices=["text", "json"], default="json")


def _build_brand_contract_list_mutator(parser: argparse.ArgumentParser, *, item_help: str) -> None:
    parser.add_argument("--item", required=True, help=item_help)
    parser.add_argument("--reason", default="", help="Why this mutation is being applied (audit trail)")
    parser.add_argument("--source-version", default="", help="Version id where this need was observed")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    parser.add_argument("--format", choices=["text", "json"], default="json")


def build_sage_approved_phrase_add_cli(parser, *, inspire_urls):
    _build_brand_contract_list_mutator(parser, item_help="Approved phrase text to add")


def build_sage_approved_phrase_remove_cli(parser, *, inspire_urls):
    _build_brand_contract_list_mutator(parser, item_help="Approved phrase text to remove")


def build_sage_negative_constraint_add_cli(parser, *, inspire_urls):
    _build_brand_contract_list_mutator(parser, item_help="Negative constraint text to add")


def build_sage_negative_constraint_remove_cli(parser, *, inspire_urls):
    _build_brand_contract_list_mutator(parser, item_help="Negative constraint text to remove")


def build_sage_illustration_concept_add_cli(parser, *, inspire_urls):
    _build_brand_contract_list_mutator(parser, item_help="Illustration concept text to add")


def build_sage_illustration_concept_remove_cli(parser, *, inspire_urls):
    _build_brand_contract_list_mutator(parser, item_help="Illustration concept text to remove")


def build_sage_brand_anchor_source_add_cli(parser, *, inspire_urls):
    _build_brand_contract_list_mutator(parser, item_help="Brand anchor source text to add")


def build_sage_brand_anchor_source_remove_cli(parser, *, inspire_urls):
    _build_brand_contract_list_mutator(parser, item_help="Brand anchor source text to remove")


def build_framing_direction_add_cli(parser, *, inspire_urls):
    parser.add_argument("--id", required=True, help="Stable kebab-case framing-direction id")
    parser.add_argument("--label", default="", help="Human-readable label")
    parser.add_argument("--keyword", action="append", default=[], help="Repeatable: keyword for routing")
    parser.add_argument("--source-cues", default="", help="Source-cues sentence")
    parser.add_argument("--source-priority", default="", help="Numeric or string priority hint")
    parser.add_argument("--directive", default="", help="Prose directive (one sentence)")
    parser.add_argument("--adoption-scene", default="", help="Prose adoption-scene")
    parser.add_argument("--style-anchor", default="", help="Prose style-anchor")
    parser.add_argument("--body-file", default="", help="Path to a markdown file containing directive/adoption_scene/style_anchor sections (overrides individual --directive/--adoption-scene/--style-anchor)")
    parser.add_argument("--reason", default="", help="Why this direction is being added/updated")
    parser.add_argument("--source-version", default="", help="Version id where this direction was found necessary")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--format", choices=["text", "json"], default="json")


def build_framing_direction_remove_cli(parser, *, inspire_urls):
    parser.add_argument("--id", required=True, help="Framing-direction id to remove")
    parser.add_argument("--keep-voice", action="store_true", help="Leave voice/framing/<id>.md on disk; only remove the JSON entry")
    parser.add_argument("--reason", default="", help="Why this direction is being removed")
    parser.add_argument("--source-version", default="", help="Version id where this need was observed")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--format", choices=["text", "json"], default="json")


def _build_kinded_brand_contract_mutator(parser, *, kind_choices, item_help):
    parser.add_argument("--kind", required=True, choices=kind_choices)
    parser.add_argument("--item", required=True, help=item_help)
    parser.add_argument("--reason", default="", help="Why this mutation is being applied")
    parser.add_argument("--source-version", default="", help="Version id where this need was observed")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--format", choices=["text", "json"], default="json")


def build_product_term_add_cli(parser, *, inspire_urls):
    _build_kinded_brand_contract_mutator(parser, kind_choices=["allowed", "banned"], item_help="Product-truth term to add to allowed or banned list")


def build_product_term_remove_cli(parser, *, inspire_urls):
    _build_kinded_brand_contract_mutator(parser, kind_choices=["allowed", "banned"], item_help="Product-truth term to remove from allowed or banned list")


def build_lexicon_token_add_cli(parser, *, inspire_urls):
    _build_kinded_brand_contract_mutator(parser, kind_choices=["capability", "governance_process", "governance_education"], item_help="Lexicon token to add")


def build_lexicon_token_remove_cli(parser, *, inspire_urls):
    _build_kinded_brand_contract_mutator(parser, kind_choices=["capability", "governance_process", "governance_education"], item_help="Lexicon token to remove")


def build_set_motion_grammar_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--director", required=True, help="Director token or motion grammar anchor")
    parser.add_argument("--favored", action="append", help="Favored motion move; repeat as needed")
    parser.add_argument("--banned", action="append", help="Banned motion move; repeat as needed")
    parser.add_argument("--intensity", default="", help="Default motion intensity")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    parser.add_argument("--format", choices=["text", "json"], default="json")


def build_promote_style_policy_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--material-type", required=True, help="Material type this policy governs")
    parser.add_argument("--anchor", action="append", required=True, help="Required style reference version; repeat as needed")
    parser.add_argument("--apply-to", action="append", help="Material types this policy applies to; repeat as needed")
    parser.add_argument("--reference-policy", choices=["single_style_anchor", "rotating_anchor_set"], default="single_style_anchor")
    parser.add_argument("--style-anchor-role", default="style", help="Reference role name for the style anchor")
    parser.add_argument("--text", help="Human-readable policy summary")
    parser.add_argument("--evidence-version", action="append", help="Evidence version id; repeat as needed")
    parser.add_argument("--must-carry-forward", action="append", help="Required carried-forward trait; repeat as needed")
    parser.add_argument("--failure-mode-if-missing", default="", help="Failure mode when this policy is absent")
    parser.add_argument("--model-behavior-note", default="", help="Behavior note explaining why the policy exists")
    parser.add_argument("--correction-note", default="", help="How future planners should apply the policy")
    parser.add_argument("--source", default="typed_mutation_tool", help="Policy provenance label")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    parser.add_argument("--format", choices=["text", "json"], default="json")


def build_update_palette_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--role", required=True, help="Palette role to update (primary, secondary, neutral, accent, etc.)")
    parser.add_argument("--hex", required=True, help="Hex color value (e.g. #B85C38)")
    parser.add_argument("--identity", help="Optional path to brand-identity.json")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    parser.add_argument("--format", choices=["text", "json"], default="json")


def build_update_typography_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--role", required=True, help="Typography role to update (display, body, mono, etc.)")
    parser.add_argument("--family", required=True, help="Font family to assign")
    parser.add_argument("--fallback", default="", help="Optional fallback chain note")
    parser.add_argument("--identity", help="Optional path to brand-identity.json")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    parser.add_argument("--format", choices=["text", "json"], default="json")


def build_update_devices_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--add", action="append", help="Approved graphic device to add; repeat as needed")
    parser.add_argument("--remove", action="append", help="Approved graphic device to remove; repeat as needed")
    parser.add_argument("--identity", help="Optional path to brand-identity.json")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    parser.add_argument("--format", choices=["text", "json"], default="json")


def build_example_sources_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--category", help="Category key filter (e.g. saas-product-specialists)")
    parser.add_argument("--query", help="Search query across source names, notes, and tags")
    parser.add_argument("--format", choices=["table", "json"], default="table")


def build_collect_examples_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--category", help="Category key filter (e.g. premium-branding)")
    parser.add_argument("--query", help="Search query across source names, notes, and tags")
    parser.add_argument("--site", action="append", help="Specific source key to capture; repeat as needed")
    parser.add_argument("--limit", type=int, help="Limit number of captures after filtering")
    parser.add_argument("--out-dir", help="Output directory for example captures")
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--height", type=int, default=1100)
    parser.add_argument("--open-folder", action="store_true")


def build_social_specs_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("format", nargs="?", help="Optional single format filter. New taxonomy examples: proof-poster, site-pattern-tile, system-explainer-illustration. Deprecated filters like campaign-poster, pattern-system, and brand-scene are still listed but marked as deprecated.")
    parser.add_argument("--verbose", action="store_true", help="Include notes and source hints")


def build_generate_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--scratchpad", required=True, help="Path to a generation scratchpad JSON created by build-generation-scratchpad")
    parser.add_argument("--max-iterations", type=int, default=1, help="Max generate→critique→refine loops (1-3, default: 1 = single-shot)")
    parser.add_argument("--internal-vlm-critique", action="store_true", help="Opt into the legacy internal VLM critique/refine loop after generation (deprecated; prefer critique-rubric + submit-critique). Uses OPENROUTER_API_KEY or ANTHROPIC_API_KEY when enabled.")
    parser.add_argument("--skip-vlm", action="store_true", help="Deprecated compatibility flag. Internal VLM critique is off by default unless --internal-vlm-critique is set.")
    parser.add_argument("--vlm-critique", help="Path to agent-provided critique JSON (skips the internal OpenRouter/Anthropic VLM call)")


def build_generate_once_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--scratchpad", required=True, help="Path to a generation scratchpad JSON created by build-generation-scratchpad")
    parser.add_argument("--format", choices=["text", "json"], default="json")
    parser.add_argument("--open", action="store_true", help="Open the generated image after creation")


def build_create_video_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--brief", required=True, help="Path to launch-video brief JSON (shots + timeline)")
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_derive_video_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--source-version", required=True, help="Approved still version to animate (e.g. v012)")
    parser.add_argument("--material-type", choices=["landing-hero", "short-video", "feature-animation", "motion-loop"], default="short-video")
    parser.add_argument("--prompt", help="Optional prompt override for the derivative video")
    parser.add_argument("-m", "--model", help="Optional video model override")
    parser.add_argument("--aspect-ratio", "-ar")
    parser.add_argument("--duration", "-d", type=int)
    parser.add_argument("--tag", "-t")
    parser.add_argument("--motion-reference", help="Optional reference video for motion-control models")
    parser.add_argument("--negative-prompt", "-n")
    parser.add_argument("--make-gif", action="store_true")
    parser.add_argument("--profile", help="Optional brand-profile.json path")
    parser.add_argument("--identity", help="Optional brand-identity.json path")
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_derive_mockup_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--source-version", required=True, help="Approved still version to reinterpret as a generated contextual mockup scene (e.g. v012)")
    parser.add_argument("--material-type", choices=["device-mockup", "lifestyle-mockup", "website-hero-illustration"], default="device-mockup")
    parser.add_argument("--prompt", help="Optional prompt override for the generated mockup scene (not pixel-precise compositing)")
    parser.add_argument("-m", "--model", help="Optional image model override")
    parser.add_argument("--aspect-ratio", "-ar")
    parser.add_argument("--tag", "-t")
    parser.add_argument("--negative-prompt", "-n")
    parser.add_argument("--profile", help="Optional brand-profile.json path")
    parser.add_argument("--identity", help="Optional brand-identity.json path")
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_critique_rubric_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("version", help="Version ID to critique (e.g. v12)")
    parser.add_argument(
        "--dspy-scorer",
        action="store_true",
        help=(
            "Run the v2 DSPy scorer inline and embed axis_scores, axis_rationales, "
            "disqualifier_triggered, and rubric_version into the returned packet. "
            "Requires the scoring extras installed (pip install -e '.[scoring]') and "
            "OPENROUTER_API_KEY (or ANTHROPIC_API_KEY) in .env. When absent, the "
            "packet returns the v1 4-axis rubric as before and the agent does the "
            "actual scoring by hand."
        ),
    )
    parser.add_argument(
        "--scorer-model",
        help=(
            "Override the DSPy scorer LM (LiteLLM model string). "
            "Default openrouter/anthropic/claude-haiku-4.5. Examples: "
            "openrouter/google/gemini-2.5-flash (cheaper), "
            "openrouter/anthropic/claude-sonnet-4.5 (stronger)."
        ),
    )
    parser.add_argument("--format", choices=["text", "json"], default="json")


def build_submit_critique_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    # Accept both --version-id (preferred, matches sibling review verbs) and
    # the legacy positional form. See build_submit_review_cli for rationale.
    parser.add_argument("version", nargs="?", help="Version ID (e.g. v12). Deprecated positional form — prefer --version-id.")
    parser.add_argument("--version-id", dest="version_id", help="Version ID (e.g. v12). Preferred form; matches sibling review verbs.")
    parser.add_argument("--critique-json", required=True, help="Path to critique JSON file or inline JSON string")
    parser.add_argument("--format", choices=["text", "json"], default="json")


def build_submit_review_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    # Historically this command took a positional `version`. Every sibling
    # review verb (get-review-packet, submit-critique via its alias path, the
    # pi-adapter tool schema) uses --version-id. The inconsistency caused
    # repeated subagent failures: the pi tool-registry emits --version-id and
    # argparse rejected it as an unknown option. Accept both. The positional
    # remains optional for backward compat; if neither form is given, we emit
    # a clear error in cmd_submit_review.
    parser.add_argument("version", nargs="?", help="Version ID (e.g. v12). Deprecated positional form — prefer --version-id.")
    parser.add_argument("--version-id", dest="version_id", help="Version ID (e.g. v12). Preferred form; matches sibling review verbs.")
    parser.add_argument("--critique-json", required=True, help="Path to critique JSON file or inline JSON string")
    parser.add_argument("--dry-run", action="store_true", help="Validate and preview without writing")
    parser.add_argument("--format", choices=["text", "json"], default="json")


def _add_pipeline_core_args(parser: argparse.ArgumentParser, *, require_material_type: bool = True) -> None:
    parser.add_argument("--material-type", required=require_material_type, help="Material type to generate")
    parser.add_argument("--mode", choices=["reference", "inspiration", "hybrid"], default="hybrid", help="Workflow mode for the plan")
    parser.add_argument("--tag", "-t", help="Short output tag for the generated asset/version")
    parser.add_argument("--mechanic", help="The one system mechanic or reveal move to emphasize")
    parser.add_argument("--purpose", help="What job this material should do")
    parser.add_argument("--target-surface", help="Where this material will be used")
    parser.add_argument("--product-truth-expression", help="What concrete product truth this material must express")
    parser.add_argument("--abstraction-level", choices=["low", "medium", "high"], help="How abstract this material is allowed to be")
    parser.add_argument("--briefing", help="Creative brief text passed to the plan draft stage")
    parser.add_argument("--audience", help="Target audience summary")
    parser.add_argument("--preserve", action="append", help="Thing that must stay fixed; repeat as needed")
    parser.add_argument("--push", action="append", help="Thing that can be pushed or explored; repeat as needed")
    parser.add_argument("--ban", action="append", help="Thing that must not appear; repeat as needed")
    parser.add_argument("--pick", action="append", help="Explicit role pick in the form role=source-key-or-path; repeat as needed")
    parser.add_argument("--prompt-seed", help="Optional explicit prompt seed; otherwise one is generated")
    parser.add_argument("--goal", help="Optional top-level goal used for routing context")
    parser.add_argument("--request", help="Optional request text used for routing context")
    parser.add_argument("--motion-reference", help="Optional motion reference path for routing or video generation")
    parser.add_argument("--base-image", help="Path to an image to edit or overlay on during generation")
    parser.add_argument("--render-backend", choices=["native", "html"], default="native", help="Rendering backend; use html for structured share-card generation")
    parser.add_argument("--source-url", help="Real product/app URL to extract structured share-card text from")
    parser.add_argument("--entity-type", help="Entity type for HTML share cards (prompt, skill, library, proposal, community, dao, update)")
    parser.add_argument("--headline", help="Explicit share-card headline override")
    parser.add_argument("--subhead", help="Explicit share-card subhead override")
    parser.add_argument("--cta", help="CTA label override for HTML share cards")
    parser.add_argument("--proof-title", help="Explicit proof-module title override")
    parser.add_argument("--proof-excerpt", help="Explicit proof-module excerpt override")
    parser.add_argument("--proof-row", help="Explicit proof-module footer/detail row override")
    parser.add_argument("--proof-meta", action="append", help="Proof metadata row/chip for HTML share cards; repeat as needed")
    parser.add_argument("--proof-crop-path", help="Screenshot crop or product image path used as supporting texture inside the proof module")
    parser.add_argument("--design-variance", type=int, default=5, help="Design variance dial (1-10): 1-3 clean centered, 4-7 editorial asymmetry, 8-10 strong asymmetry")
    parser.add_argument("--complexity-tier", choices=["simple", "moderate", "dense"], default=None, help="Cap named-elements in the brief: simple (≤2) / moderate (≤4) / dense (unlimited). Default: per-material (simple for illustration-first materials such as system-explainer-illustration or illustrated-brand-world, moderate otherwise).")
    parser.add_argument("--prompt-subject", default=None, help="Concrete subject phrase for the 5-slot template (e.g. 'two hands placing clay pots on a drying board')")
    parser.add_argument("--prompt-style-descriptors", default=None, help="Style descriptors for the 5-slot template (e.g. 'Kodak Portra 400 film grain, charcoal woodcut, hand-inked botanical plate')")
    parser.add_argument("--prompt-lighting", default=None, help="Lighting for the 5-slot template (e.g. 'golden hour raking light, chiaroscuro, diffused north daylight')")
    parser.add_argument("--prompt-camera", default=None, help="Camera/framing for the 5-slot template (e.g. '85mm portrait lens, bird's eye view, 16:9 letterbox')")
    parser.add_argument("--prompt-composition", default=None, help="Explicit composition directive for the 5-slot template; overrides surface-strategy defaults")
    parser.add_argument("--prompt-details", default=None, help="Detail boosters for the 5-slot template (e.g. 'shallow depth of field, warm palette, matte finish')")
    parser.add_argument("--visual-density", type=int, default=None, help="Spatial density dial (1-10): 1-3 Art Gallery (huge negative space, one gesture), 4-7 Daily App (editorial spacing), 8-10 Cockpit (packed data, 1px separators). Default: per-material (4 for illustration-first, 5 otherwise).")
    parser.add_argument("--aesthetic-commitment", choices=["minimal", "maximal", "editorial", "brutalist", "organic", "industrial", "retro_futurist", "playful", "luxury"], default=None, help="Pick one axis extreme rather than hedging with mild adjectives. Required for distinctive output. Commitment (not intensity) separates specific aesthetics from generic premium-AI-brand mood.")
    parser.add_argument("--aesthetic-capsule", default=None, help="Curated aesthetic capsule id or label (e.g. warm-editorial-system-illustration). Overrides automatic capsule selection.")
    parser.add_argument("--style-handle", default=None, help="Human style shorthand to compile into a capsule (e.g. 'ghibli aesthetic' -> safe storybook-animation descriptors).")
    parser.add_argument("--layout-spec", type=json.loads, default=None, help='JSON layout spec override, e.g. \'{"columns":2,"alignment":"left"}\'')
    parser.add_argument("--set-scope", action="store_true", help="Route as a set orchestration brief, even though generation remains single-material")
    parser.add_argument("--skip-proof", action="store_true", help="Skip the proof module in HTML share cards")
    parser.add_argument("--dark-mode", action="store_true", help="Use dark background variant for HTML share cards")
    parser.add_argument("--skip-route", action="store_true", help="Skip the routing stage and start at plan-draft")
    parser.add_argument("--critique-mode", choices=["advisory", "strict"], default="strict", help="How blocking critique findings should be treated inside pipeline orchestration")
    parser.add_argument("--allow-blocking", action="store_true", help="Record an explicit bypass and continue even if critique or scratchpad blocking issues remain")
    parser.add_argument("--route", help="Agent-selected route key (skip automatic routing)")
    parser.add_argument("--source-version", help="Version ID to iterate from (e.g. v012); establishes branch lineage")
    parser.add_argument("--profile", help="Optional brand-profile.json path")
    parser.add_argument("--identity", help="Optional brand-identity.json path")


def _add_pipeline_generation_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--max-iterations", type=int, default=1, help="Max generate→VLM-critique→refine loops (1-3)")
    parser.add_argument("--max-retries", type=int, default=1, help="Max quality-gate retries on very low scores (0-2)")
    parser.add_argument("--internal-vlm-critique", action="store_true", help="Opt into the legacy internal VLM critique/refine loop after generation (deprecated; prefer critique-rubric + submit-critique). Uses OPENROUTER_API_KEY or ANTHROPIC_API_KEY when enabled.")
    parser.add_argument("--skip-vlm", action="store_true", help="Deprecated compatibility flag. Internal VLM critique is off by default unless --internal-vlm-critique is set.")


def _add_pipeline_output_args(parser: argparse.ArgumentParser, *, include_open: bool = False) -> None:
    parser.add_argument("--format", choices=["text", "json"], default="json")
    if include_open:
        parser.add_argument("--open", action="store_true", help="Open the generated image after pipeline completes")


def build_prepare_run_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    _add_pipeline_core_args(parser, require_material_type=True)
    _add_pipeline_output_args(parser)


def build_plan_run_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    _add_pipeline_core_args(parser, require_material_type=True)
    parser.add_argument("--workflow-id", help="Existing orchestration run id from prepare-run")
    _add_pipeline_output_args(parser)


def build_validate_run_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--plan-draft", required=True, help="Path to a plan draft JSON produced by plan-run")
    parser.add_argument("--workflow-id", help="Existing orchestration run id")
    parser.add_argument("--critique-mode", choices=["advisory", "strict"], default="strict")
    parser.add_argument("--allow-blocking", action="store_true")
    parser.add_argument("--profile", help="Optional brand-profile.json path")
    parser.add_argument("--identity", help="Optional brand-identity.json path")
    _add_pipeline_output_args(parser)


def build_execute_run_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--plan-draft", required=True, help="Path to a plan draft JSON produced by plan-run")
    parser.add_argument("--critique-path", help="Optional critique JSON path from validate-run")
    parser.add_argument("--workflow-id", help="Existing orchestration run id")
    _add_pipeline_core_args(parser, require_material_type=False)
    _add_pipeline_generation_args(parser)
    _add_pipeline_output_args(parser)


def build_review_run_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--version-id", required=True, help="Generated version id to inspect")
    parser.add_argument("--workflow-id", help="Existing orchestration run id")
    parser.add_argument("--profile", help="Optional brand-profile.json path")
    parser.add_argument("--identity", help="Optional brand-identity.json path")
    _add_pipeline_output_args(parser)


def build_evolve_run_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--version-id", required=True, help="Generated version id to evolve from")
    parser.add_argument("--workflow-id", help="Existing orchestration run id")
    parser.add_argument("--profile", help="Optional brand-profile.json path")
    parser.add_argument("--identity", help="Optional brand-identity.json path")
    _add_pipeline_output_args(parser)


def build_orchestrate_material_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    _add_pipeline_core_args(parser, require_material_type=True)
    _add_pipeline_generation_args(parser)
    parser.add_argument("--bypass-orchestrator", action="store_true", help="Acknowledge that the agent orchestration chain was skipped (silences the advisory warning and records the bypass to the run ledger)")
    parser.add_argument("--bypass-reason", default="", help="One-line reason for bypassing the orchestrator chain; required in practice when --bypass-orchestrator is set")
    _add_pipeline_output_args(parser)


def build_pipeline_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    _add_pipeline_core_args(parser, require_material_type=True)
    _add_pipeline_generation_args(parser)
    parser.add_argument("--bypass-orchestrator", action="store_true", help="Acknowledge that the agent orchestration chain was skipped (silences the advisory warning and records the bypass to the run ledger)")
    parser.add_argument("--bypass-reason", default="", help="One-line reason for bypassing the orchestrator chain; required in practice when --bypass-orchestrator is set")
    _add_pipeline_output_args(parser, include_open=True)


def build_feedback_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("version", help="Version ID (e.g., v12)")
    score_group = parser.add_mutually_exclusive_group()
    score_group.add_argument("--score", "-s", type=int, choices=range(1, 6), help="Score 1-5")
    score_group.add_argument("--reject", action="store_true", help="Record a hard user rejection (stores score=1, decision=reject); requires --notes")
    parser.add_argument("--notes", "-n", help="Feedback notes")
    parser.add_argument("--status", choices=["favorite", "rejected"], help="Mark status")
    parser.add_argument("--lock", nargs="+", help="Lock prompt fragments")
    parser.add_argument("--prompt", "-p", help="Backfill prompt text")


def build_show_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("version", nargs="?", help="Specific version to show")
    parser.add_argument("--favorites", action="store_true", help="Only favorites")
    parser.add_argument("--top", type=int, help="Top N by score")
    parser.add_argument("--latest", type=int, help="Latest N versions by version id")
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_compare_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("versions", nargs="*", help="Versions to compare")
    parser.add_argument("--favorites", action="store_true", help="Compare favorites")
    parser.add_argument("--top", type=int, help="Compare top N")
    parser.add_argument("--latest", type=int, help="Compare latest N versions")
    parser.add_argument("--all", dest="all_versions", action="store_true", help="Compare all historical versions")
    parser.add_argument("--embed", action="store_true", help="Embed images as base64 (portable but larger)")
    parser.add_argument("--output", "-o", help="Output HTML path")


def build_diagnose_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("versions", nargs="+", help="Versions to diagnose (e.g. v14 v15)")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")


def build_evolve_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    return None


def build_inspire_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("category", nargs="?", default="symbol", help=f"Category: {', '.join(inspire_urls.keys())}")
    parser.add_argument("--url", help="Open a custom inspiration URL")
    parser.add_argument("--label", help="Optional label for external inspiration captures")
    parser.add_argument("--list", dest="list_only", action="store_true", help="List saved inspiration assets")
    parser.add_argument("--brand", help="Brand key to configure inspiration sources for")
    parser.add_argument("--sources", action="append", help="Comma-separated inspiration source keys to attach to the brand")
    parser.add_argument("--clear", action="store_true", help="Clear configured inspiration sources for the brand")
    parser.add_argument("--show", action="store_true", help="Show current inspiration configuration for the brand")
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_inspiration_list_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--brand", help="Brand key to inspect configured inspiration sources for")
    parser.add_argument("--category", nargs="?", default="symbol", help=f"Category: {', '.join(inspire_urls.keys())}")
    parser.add_argument("--show-config", action="store_true", help="Show configured indexed inspiration sources instead of captured files")
    parser.add_argument("--format", choices=["text", "json"], default="json")


def build_inspiration_capture_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("category", nargs="?", default="symbol", help=f"Category: {', '.join(inspire_urls.keys())}")
    parser.add_argument("--url", help="Open a custom inspiration URL")
    parser.add_argument("--label", help="Optional label for external inspiration captures")
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--out-dir", help="Output directory for captured inspiration")
    parser.add_argument("--open-folder", action="store_true")
    parser.add_argument("--format", choices=["text", "json"], default="json")


def build_inspiration_configure_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--brand", help="Brand key to configure inspiration sources for")
    parser.add_argument("--sources", action="append", help="Comma-separated inspiration source keys to attach to the brand")
    parser.add_argument("--show", action="store_true", help="Show current inspiration configuration for the brand")
    parser.add_argument("--format", choices=["text", "json"], default="json")


def build_inspiration_clear_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--brand", help="Brand key to clear inspiration sources for")
    parser.add_argument("--format", choices=["text", "json"], default="json")


def build_suggest_layout_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--material-type", required=True, help="Material type to suggest layouts for (e.g. proof-poster, social, illustrated-brand-world)")
    parser.add_argument("--count", type=int, default=4, help="How many layout suggestions to return")
    parser.add_argument("--format", choices=["text", "json"], default="text")


def build_composite_illustration_cli(parser: argparse.ArgumentParser, *, inspire_urls: dict[str, str]) -> None:
    parser.add_argument("--screenshot", required=True, help="Path to the product screenshot image")
    parser.add_argument("--feature", help="Feature to highlight (e.g. 'Library sync and distribution')")
    parser.add_argument("--headline", help="Headline text rendered above the screenshot")
    parser.add_argument("--subhead", help="Optional subheadline text below the headline")
    parser.add_argument("--pattern", help="Optional background pattern image to tile")
    parser.add_argument("--highlight-region", help="Region to highlight in the screenshot as x,y,w,h pixel coords")
    parser.add_argument("--output", default="composite-illustration.png", help="Output file path (default: composite-illustration.png)")
    parser.add_argument("--aspect-ratio", default="16:9", choices=["16:9", "4:3", "1:1", "21:9"], help="Canvas aspect ratio (default: 16:9)")
    parser.add_argument("--logo", help="Optional logo image path; defaults to brand-materials/logo.png")
    parser.add_argument("--dark", action="store_true", help="Use dark (charcoal) background instead of cream")


CLI_BUILDERS: dict[str, CliBuilder] = {
    'bootstrap': build_bootstrap_cli,
    'types': build_types_cli,
    'init': build_init_cli,
    'create-brand': build_create_brand_cli,
    'start-testing': build_start_testing_cli,
    'use': build_use_cli,
    'list-brands': build_list_brands_cli,
    'extract-brand': build_extract_brand_cli,
    'build-identity': build_build_identity_cli,
    'describe-brand': build_describe_brand_cli,
    'show-identity': build_show_identity_cli,
    'show-blackboard': build_show_blackboard_cli,
    'show-session-summary': build_show_session_summary_cli,
    'context-snapshot': build_context_snapshot_cli,
    'capabilities': build_capabilities_cli,
    'list-aesthetic-capsules': build_list_aesthetic_capsules_cli,
    'suggest-aesthetic-directions': build_suggest_aesthetic_directions_cli,
    'promote-aesthetic-learning': build_promote_aesthetic_learning_cli,
    'workspace-status': build_workspace_status_cli,
    'improvement-questions': build_improvement_questions_cli,
    'show-workflow-lineage': build_show_workflow_lineage_cli,
    'list-runs': build_list_runs_cli,
    'get-run': build_get_run_cli,
    'run-list': build_run_list_cli,
    'run-show': build_run_show_cli,
    'run-replay': build_run_replay_cli,
    'rebuild-run-index': build_rebuild_run_index_cli,
    'get-plan': build_get_plan_cli,
    'get-critique': build_get_critique_cli,
    'get-scratchpad': build_get_scratchpad_cli,
    'get-review-packet': build_get_review_packet_cli,
    'get-version': build_get_version_cli,
    'compare-versions': build_compare_versions_cli,
    'switch-brand': build_switch_brand_cli,
    'migrate-material-taxonomy': build_migrate_material_taxonomy_cli,
    'report-material-taxonomy': build_report_material_taxonomy_cli,
    'get-pending-reviews': build_get_pending_reviews_cli,
    'get-policy': build_get_policy_cli,
    'set-policy': build_set_policy_cli,
    'approve-action': build_approve_action_cli,
    'reject-action': build_reject_action_cli,
    'show-reference-analysis': build_show_reference_analysis_cli,
    'prompts-list': build_prompts_list_cli,
    'prompts-get': build_prompts_get_cli,
    'source-knowledge': build_source_knowledge_cli,
    'reference-rubric': build_reference_rubric_cli,
    'submit-reference-analysis': build_submit_reference_analysis_cli,
    'route-request': build_route_request_cli,
    'resolve-prompt': build_resolve_prompt_cli,
    'review-prompt': build_review_prompt_cli,
    'validate-identity': build_validate_identity_cli,
    'parse-design-memory': build_parse_design_memory_cli,
    'extract-css-variables': build_extract_css_variables_cli,
    'diff-design-memory': build_diff_design_memory_cli,
    'export-design-tokens': build_export_design_tokens_cli,
    'inspiration-status': build_inspiration_status_cli,
    'show-rubric': build_show_rubric_cli,
    'show-disagreements': build_show_disagreements_cli,
    'scoring-status': build_scoring_status_cli,
    'rebucket-inspiration': build_rebucket_inspiration_cli,
    'extract-inspiration': build_extract_inspiration_cli,
    'consolidate-inspiration': build_consolidate_inspiration_cli,
    'inspiration-mode': build_inspiration_mode_cli,
    'shotlist': build_shotlist_cli,
    'capture-product': build_capture_product_cli,
    'explore-brand': build_explore_brand_cli,
    'plan-set': build_plan_set_cli,
    'validate-brand-fit': build_validate_brand_fit_cli,
    'validate-set': build_validate_set_cli,
    'generate-set': build_generate_set_cli,
    'review-brand': build_review_brand_cli,
    'suggest-role-pack': build_suggest_role_pack_cli,
    'suggest-layout': build_suggest_layout_cli,
    'plan-material': build_plan_material_cli,
    'plan-draft': build_plan_draft_cli,
    'critique-plan': build_critique_plan_cli,
    'build-generation-scratchpad': build_build_generation_scratchpad_cli,
    'ideate-material': build_ideate_material_cli,
    'ideate-copy': build_ideate_copy_cli,
    'ideate-messaging': build_ideate_messaging_cli,
    'promote-messaging': build_promote_messaging_cli,
    'update-messaging': build_update_messaging_cli,
    'show-iteration-memory': build_show_iteration_memory_cli,
    'update-iteration-memory': build_update_iteration_memory_cli,
    'append-forbidden-pattern': build_append_forbidden_pattern_cli,
    'add-aesthetic-capsule': build_add_aesthetic_capsule_cli,
    'contract-status': build_contract_status_cli,
    'render-iteration-memory': build_render_iteration_memory_cli,
    'sage-approved-phrase-add': build_sage_approved_phrase_add_cli,
    'sage-approved-phrase-remove': build_sage_approved_phrase_remove_cli,
    'sage-negative-constraint-add': build_sage_negative_constraint_add_cli,
    'sage-negative-constraint-remove': build_sage_negative_constraint_remove_cli,
    'sage-illustration-concept-add': build_sage_illustration_concept_add_cli,
    'sage-illustration-concept-remove': build_sage_illustration_concept_remove_cli,
    'sage-brand-anchor-source-add': build_sage_brand_anchor_source_add_cli,
    'sage-brand-anchor-source-remove': build_sage_brand_anchor_source_remove_cli,
    'framing-direction-add': build_framing_direction_add_cli,
    'framing-direction-remove': build_framing_direction_remove_cli,
    'product-term-add': build_product_term_add_cli,
    'product-term-remove': build_product_term_remove_cli,
    'lexicon-token-add': build_lexicon_token_add_cli,
    'lexicon-token-remove': build_lexicon_token_remove_cli,
    'promote-learning': build_promote_learning_cli,
    'append-custom-scratchpad-note': build_append_custom_scratchpad_note_cli,
    'set-motion-grammar': build_set_motion_grammar_cli,
    'promote-style-policy': build_promote_style_policy_cli,
    'update-palette': build_update_palette_cli,
    'update-typography': build_update_typography_cli,
    'update-devices': build_update_devices_cli,
    'example-sources': build_example_sources_cli,
    'collect-examples': build_collect_examples_cli,
    'social-specs': build_social_specs_cli,
    'prepare-run': build_prepare_run_cli,
    'plan-run': build_plan_run_cli,
    'validate-run': build_validate_run_cli,
    'execute-run': build_execute_run_cli,
    'review-run': build_review_run_cli,
    'evolve-run': build_evolve_run_cli,
    'orchestrate-material': build_orchestrate_material_cli,
    'generate-once': build_generate_once_cli,
    'generate': build_generate_cli,
    'derive-mockup': build_derive_mockup_cli,
    'derive-video': build_derive_video_cli,
    'create-video': build_create_video_cli,
    'critique-rubric': build_critique_rubric_cli,
    'submit-critique': build_submit_critique_cli,
    'submit-review': build_submit_review_cli,
    'pipeline': build_pipeline_cli,
    'feedback': build_feedback_cli,
    'show': build_show_cli,
    'compare': build_compare_cli,
    'diagnose': build_diagnose_cli,
    'evolve': build_evolve_cli,
    'inspire': build_inspire_cli,
    'inspiration-list': build_inspiration_list_cli,
    'inspiration-capture': build_inspiration_capture_cli,
    'inspiration-configure': build_inspiration_configure_cli,
    'inspiration-clear': build_inspiration_clear_cli,
    'composite-illustration': build_composite_illustration_cli,
}


def get_cli_builder(name: str) -> CliBuilder:
    return CLI_BUILDERS.get(name, noop_cli_builder)


def build_cli_parser(command_specs: list[Any], *, inspire_urls: dict[str, str], epilog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Brand iteration wrapper for image and motion materials", formatter_class=argparse.RawDescriptionHelpFormatter, epilog=epilog)
    sub = parser.add_subparsers(dest="command", required=True)
    for spec in command_specs:
        subparser = _add_subparser(sub, spec)
        builder = getattr(spec, "cli_builder", None) or get_cli_builder(spec.name)
        builder(subparser, inspire_urls=inspire_urls)
    return parser
